package com.cbr.nativetest;
import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import java.io.*;
public class MainActivity extends Activity {
 static { System.loadLibrary("testshim"); }
 native String startEngine(String library, String data);
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  TextView text = new TextView(this); text.setText("Starting CBR embedded test"); setContentView(text);
  new Thread(() -> {
   String result;
   try {
    File library = new File(getFilesDir(), "libcbrengine.so");
    library.setWritable(true);
    try(InputStream in=getAssets().open("libcbrengine.so"); FileOutputStream out=new FileOutputStream(library)) {
     byte[] buffer=new byte[65536]; int count; while((count=in.read(buffer))!=-1) out.write(buffer,0,count);
    }
    library.setWritable(false);
    result=startEngine(library.getAbsolutePath(),new File(getFilesDir(),"engine-data").getAbsolutePath());
   } catch(Exception error) {result=error.toString();}
   final String message=result; android.util.Log.i("CBRNativeTest", message);
   runOnUiThread(() -> text.setText(message));
  }).start();
 }
}
