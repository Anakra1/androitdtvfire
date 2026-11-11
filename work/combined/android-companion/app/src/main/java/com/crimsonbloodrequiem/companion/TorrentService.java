package com.crimsonbloodrequiem.companion;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.Proxy;
import java.net.URL;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class TorrentService extends Service {
    public static final String ACTION_START = "com.crimsonbloodrequiem.companion.START";
    public static final String ACTION_STOP = "com.crimsonbloodrequiem.companion.STOP";
    private static final String CHANNEL = "cbr_stream_service";
    private static final int NOTIFICATION_ID = 501;
    private static final int TORRSERVER_PORT = 8766;
    private static final String RELEASE = "MatriX.150";
    private static final Map<String, String> HASHES = new HashMap<>();

    static {
        HASHES.put("arm64", "760f18c6837c7fc1c440726a14e7534e3baca914b780fbc3ec28a38b6158aaf0");
        HASHES.put("arm7", "852e15b8d4739ac94ce0e046bba5c7a929b2ad75f980849cef10c668971ee764");
        HASHES.put("amd64", "b0ffd094e22e09b41e171bc0f06f865bcd8da9e089501e58d65b5dbe79249d54");
        HASHES.put("386", "66d89512f8b8153d90635c9baa03fd543b0a80bc76883d25741ad9e1b778054b");
    }

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private Process engine;
    private volatile boolean stopping;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopEngine();
            stopForeground(true);
            stopSelf(startId);
            return START_NOT_STICKY;
        }

        stopping = false;
        saveStatus("Preparing local torrent player…");
        startForeground(NOTIFICATION_ID, notification("Preparing local torrent player…"));
        worker.execute(() -> {
            try {
                launchEngine();
                setStatus("Ready for Kodi playback · 127.0.0.1:" + TORRSERVER_PORT);
            } catch (Exception error) {
                setStatus("Could not start: " + error.getMessage());
                android.util.Log.e("CBRCompanion", "TorrServer startup failed", error);
                stopSelf(startId);
            }
        });
        return START_STICKY;
    }

    private void launchEngine() throws Exception {
        File data = new File(getFilesDir(), "torrent-engine");
        if (!data.exists() && !data.mkdirs()) throw new IllegalStateException("Cannot create engine folder.");
        File binary = new File(getApplicationInfo().nativeLibraryDir, "libtorrserver.so");
        String expected = HASHES.get(archName());
        if (!binary.isFile() || expected == null || !expected.equals(sha256(binary))) {
            throw new IllegalStateException("Packaged engine is missing or damaged. Reinstall CBR Companion 0.2.0.");
        }
        if (engine != null && engine.isAlive() && isReady()) return;

        if (portBusy()) {
            if (isReady()) return;
            throw new IllegalStateException("Port 8766 is already in use.");
        }

        File storage = new File(data, "data");
        if (!storage.exists() && !storage.mkdirs()) throw new IllegalStateException("Cannot create cache folder.");
        ProcessBuilder builder = new ProcessBuilder(
                binary.getAbsolutePath(), "--ip", "127.0.0.1", "--port", String.valueOf(TORRSERVER_PORT),
                "--path", storage.getAbsolutePath(), "--logpath", "/dev/null", "--weblogpath", "/dev/null");
        builder.directory(storage);
        builder.redirectOutput(new File("/dev/null"));
        builder.redirectError(new File("/dev/null"));
        engine = builder.start();

        long deadline = System.currentTimeMillis() + 20_000L;
        while (!stopping && System.currentTimeMillis() < deadline) {
            if (engine != null && !engine.isAlive()) throw new IllegalStateException("TorrServer stopped while starting.");
            if (isReady()) {
                configureEngine();
                return;
            }
            Thread.sleep(250L);
        }
        stopEngine();
        throw new IllegalStateException("TorrServer did not become ready.");
    }

    private boolean portBusy() {
        try (java.net.Socket socket = new java.net.Socket()) {
            socket.connect(new java.net.InetSocketAddress(InetAddress.getByName("127.0.0.1"), TORRSERVER_PORT), 250);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    private boolean isReady() {
        HttpURLConnection connection = null;
        try {
            connection = connection("http://127.0.0.1:" + TORRSERVER_PORT + "/echo", "GET", 1000);
            if (connection.getResponseCode() != 200) return false;
            byte[] buffer = new byte[128];
            int count = connection.getInputStream().read(buffer);
            return count > 0 && new String(buffer, 0, count, "UTF-8").startsWith("MatriX.");
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private String archName() {
        String[] abis = Build.SUPPORTED_ABIS;
        for (String abi : abis) {
            if ("arm64-v8a".equals(abi)) return "arm64";
            if ("armeabi-v7a".equals(abi)) return "arm7";
            if ("x86_64".equals(abi)) return "amd64";
            if ("x86".equals(abi)) return "386";
        }
        return abis.length == 0 ? "unknown" : abis[0];
    }

    private String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new BufferedInputStream(new java.io.FileInputStream(file))) {
            byte[] buffer = new byte[1024 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) hex.append(String.format("%02x", value & 0xff));
        return hex.toString();
    }

    private void configureEngine() throws Exception {
        JSONObject settings = postJson("/settings", new JSONObject().put("action", "get"));
        settings.put("CacheSize", 128 * 1024 * 1024)
                .put("PreloadCache", 10)
                .put("ReaderReadAHead", 95)
                .put("UseDisk", false)
                .put("DisableUpload", true)
                .put("DisableUPNP", true)
                .put("EnableDLNA", false)
                .put("EnableBonjour", false)
                .put("EnableLPD", false)
                .put("EnableRutorSearch", false)
                .put("EnableTorznabSearch", false)
                .put("TorrentDisconnectTimeout", 60)
                .put("RemoveCacheOnDrop", true)
                .put("RetrackersMode", 0);
        postJson("/settings", new JSONObject().put("action", "set").put("sets", settings));
    }

    private JSONObject postJson(String route, JSONObject body) throws Exception {
        HttpURLConnection connection = null;
        try {
            connection = connection("http://127.0.0.1:" + TORRSERVER_PORT + route, "POST", 10_000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json");
            try (java.io.OutputStream output = connection.getOutputStream()) {
                output.write(body.toString().getBytes("UTF-8"));
            }
            try (InputStream input = connection.getInputStream()) {
                byte[] buffer = new byte[16 * 1024];
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                int count;
                while ((count = input.read(buffer)) != -1) bytes.write(buffer, 0, count);
                String response = new String(bytes.toByteArray(), "UTF-8");
                return response.isEmpty() ? new JSONObject() : new JSONObject(response);
            }
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private HttpURLConnection connection(String address, String method, int timeout) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection(Proxy.NO_PROXY);
        connection.setRequestMethod(method);
        connection.setConnectTimeout(timeout);
        connection.setReadTimeout(timeout);
        connection.setUseCaches(false);
        connection.setInstanceFollowRedirects(true);
        return connection;
    }

    private void stopEngine() {
        stopping = true;
        if (engine != null) {
            engine.destroy();
            try {
                if (!engine.waitFor(3, java.util.concurrent.TimeUnit.SECONDS)) engine.destroyForcibly();
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                engine.destroyForcibly();
            }
            engine = null;
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL, "CBR playback service",
                NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Shows when CBR is preparing or serving a local stream for Kodi.");
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }

    private Notification notification(String text) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent content = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent stop = new Intent(this, TorrentService.class).setAction(ACTION_STOP);
        PendingIntent stopAction = PendingIntent.getService(this, 1, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return builder.setSmallIcon(R.drawable.ic_cbr)
                .setContentTitle("CBR Kodi Companion")
                .setContentText(text)
                .setContentIntent(content)
                .setOngoing(true)
                .addAction(R.drawable.ic_cbr, "Stop", stopAction)
                .build();
    }

    private void updateNotification(String text) {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification(text));
    }

    private void saveStatus(String text) {
        getSharedPreferences("cbr", MODE_PRIVATE).edit().putString("status", text).apply();
    }

    private void setStatus(String text) {
        saveStatus(text);
        updateNotification(text);
    }

    @Override
    public void onDestroy() {
        stopping = true;
        worker.shutdownNow();
        stopEngine();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
