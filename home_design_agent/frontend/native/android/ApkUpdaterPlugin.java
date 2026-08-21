package com.archai.home;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Environment;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

@CapacitorPlugin(name = "ApkUpdater")
public class ApkUpdaterPlugin extends Plugin {

    @PluginMethod
    public void downloadAndInstall(PluginCall call) {
        final String url = call.getString("url");
        if (url == null || url.isEmpty()) {
            call.reject("url is required");
            return;
        }

        final Context context = getContext();
        final File file = new File(context.getCacheDir(), "arch-ai-update.apk");
        call.resolve(new JSObject().put("value", "downloading"));

        Toast.makeText(context, "正在下载更新...", Toast.LENGTH_SHORT).show();

        new Thread(() -> {
            try {
                download(url, file);
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> openInstaller(context, file));
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(context, "下载更新失败，请稍后重试", Toast.LENGTH_LONG).show()
                    );
                }
            }
        }).start();
    }

    private void download(String url, File file) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setInstanceFollowRedirects(true);
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(120000);
        conn.connect();

        InputStream in = conn.getInputStream();
        FileOutputStream out = new FileOutputStream(file);
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
        out.flush();
        out.close();
        in.close();
        conn.disconnect();
    }

    private void openInstaller(Context context, File file) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        Uri uri = FileProvider.getUriForFile(
            context,
            context.getPackageName() + ".fileprovider",
            file
        );
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        context.startActivity(intent);
    }
}
