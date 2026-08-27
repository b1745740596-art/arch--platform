package com.archai.home;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;

import androidx.activity.result.ActivityResult;
import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

@CapacitorPlugin(name = "CameraCapture")
public class CameraCapturePlugin extends Plugin {
    private static final String TAG = "CameraCapture";
    private File pendingPhoto;
    private Uri pendingPhotoUri;

    @PluginMethod
    public void capturePhoto(PluginCall call) {
        if (pendingPhoto != null) {
            Log.w(TAG, "capturePhoto result=in_progress");
            call.reject("A photo capture is already in progress", "CAPTURE_IN_PROGRESS");
            return;
        }

        Activity activity = getActivity();
        if (activity == null) {
            Log.e(TAG, "capturePhoto result=unavailable reason=activity_null");
            call.reject("Camera is unavailable", "CAMERA_UNAVAILABLE");
            return;
        }

        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);

        try {
            File cameraDir = new File(getContext().getCacheDir(), "captured-images");
            if (!cameraDir.exists() && !cameraDir.mkdirs()) {
                throw new IOException("Unable to create camera cache directory");
            }
            pendingPhoto = File.createTempFile("room-photo-", ".jpg", cameraDir);
            pendingPhotoUri = FileProvider.getUriForFile(
                getContext(),
                getContext().getPackageName() + ".fileprovider",
                pendingPhoto
            );

            intent.putExtra(MediaStore.EXTRA_OUTPUT, pendingPhotoUri);
            intent.setClipData(ClipData.newRawUri("room-photo", pendingPhotoUri));
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);

            startActivityForResult(call, intent, "captureResult");
        } catch (ActivityNotFoundException error) {
            Log.e(TAG, "capturePhoto result=unavailable", error);
            clearPendingPhoto();
            call.reject("No camera app is available", "CAMERA_UNAVAILABLE", error);
        } catch (Exception error) {
            Log.e(TAG, "capturePhoto result=open_failed", error);
            clearPendingPhoto();
            call.reject("Unable to open camera", "CAMERA_OPEN_FAILED", error);
        }
    }

    @ActivityCallback
    private void captureResult(PluginCall call, ActivityResult result) {
        if (call == null) {
            Log.e(TAG, "capturePhoto result=orphaned_call");
            clearPendingPhoto();
            return;
        }
        if (result.getResultCode() != Activity.RESULT_OK) {
            Log.i(TAG, "capturePhoto result=cancelled resultCode=" + result.getResultCode());
            clearPendingPhoto();
            call.reject("Photo capture was cancelled", "CAPTURE_CANCELLED");
            return;
        }
        if (pendingPhoto == null || !pendingPhoto.exists() || pendingPhoto.length() == 0) {
            Log.e(TAG, "capturePhoto result=empty resultCode=" + result.getResultCode());
            clearPendingPhoto();
            call.reject("Camera returned an empty photo", "CAPTURE_EMPTY");
            return;
        }

        try {
            long size = pendingPhoto.length();
            byte[] bytes = readBytes(pendingPhoto);
            JSObject response = new JSObject();
            response.put("base64", Base64.encodeToString(bytes, Base64.NO_WRAP));
            response.put("mimeType", "image/jpeg");
            response.put("fileName", "camera-" + System.currentTimeMillis() + ".jpg");
            response.put("size", size);
            Log.i(TAG, "capturePhoto result=success sizeBytes=" + size);
            call.resolve(response);
        } catch (Exception error) {
            Log.e(TAG, "capturePhoto result=read_failed", error);
            call.reject("Unable to read captured photo", "CAPTURE_READ_FAILED", error);
        } finally {
            clearPendingPhoto();
        }
    }

    private byte[] readBytes(File file) throws IOException {
        try (
            FileInputStream input = new FileInputStream(file);
            ByteArrayOutputStream output = new ByteArrayOutputStream()
        ) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private void clearPendingPhoto() {
        if (pendingPhotoUri != null) {
            getContext().revokeUriPermission(
                pendingPhotoUri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            );
        }
        if (pendingPhoto != null && pendingPhoto.exists()) {
            pendingPhoto.delete();
        }
        pendingPhoto = null;
        pendingPhotoUri = null;
    }
}
