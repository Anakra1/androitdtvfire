package com.crimsonbloodrequiem.companion;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        showControls();
        if (isKodiLaunch(getIntent())) {
            startCompanion();
            finish();
        } else if (isKodiStop(getIntent())) {
            stopCompanion();
            finish();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (status != null) {
            status.setText(getSharedPreferences("cbr", MODE_PRIVATE)
                    .getString("status", "Start the local stream service for Kodi."));
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (isKodiLaunch(intent)) {
            startCompanion();
            finish();
        } else if (isKodiStop(intent)) {
            stopCompanion();
            finish();
        }
    }

    private boolean isKodiLaunch(Intent intent) {
        return intent != null && intent.getData() != null
                && "cbr".equals(intent.getData().getScheme())
                && "start".equals(intent.getData().getHost());
    }

    private boolean isKodiStop(Intent intent) {
        return intent != null && intent.getData() != null
                && "cbr".equals(intent.getData().getScheme())
                && "stop".equals(intent.getData().getHost());
    }

    private void showControls() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        int pad = (int) (28 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);
        layout.setBackgroundColor(0xff12090b);

        TextView title = new TextView(this);
        title.setText("CRIMSON BLOOD REQUIEM");
        title.setTextColor(0xfff5eeee);
        title.setTextSize(25);
        title.setGravity(Gravity.CENTER);
        layout.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView subtitle = new TextView(this);
        subtitle.setText("Kodi torrent playback companion");
        subtitle.setTextColor(0xffd0bfc2);
        subtitle.setTextSize(17);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subParams.topMargin = pad / 3;
        layout.addView(subtitle, subParams);

        status = new TextView(this);
        status.setText("Start the local stream service for Kodi.");
        status.setTextColor(0xffd0bfc2);
        status.setTextSize(16);
        status.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        statusParams.topMargin = pad;
        layout.addView(status, statusParams);

        Button start = new Button(this);
        start.setText("Start playback service");
        start.setOnClickListener(view -> startCompanion());
        layout.addView(start, buttonParams(pad));

        Button stop = new Button(this);
        stop.setText("Stop service");
        stop.setOnClickListener(view -> {
            Intent service = new Intent(this, TorrentService.class)
                    .setAction(TorrentService.ACTION_STOP);
            startService(service);
            status.setText("Stopping local stream service…");
        });
        layout.addView(stop, buttonParams(pad / 2));
        setContentView(layout);
    }

    private LinearLayout.LayoutParams buttonParams(int topMargin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = topMargin;
        return params;
    }

    private void startCompanion() {
        if (status != null) status.setText("Starting local stream service…");
        Intent service = new Intent(this, TorrentService.class)
                .setAction(TorrentService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(service);
        } else {
            startService(service);
        }
    }

    private void stopCompanion() {
        Intent service = new Intent(this, TorrentService.class)
                .setAction(TorrentService.ACTION_STOP);
        startService(service);
    }
}
