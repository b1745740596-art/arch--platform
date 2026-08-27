package com.archai.home;

import android.app.Activity;
import android.content.Intent;
import android.util.Base64;
import android.util.Log;

import androidx.activity.result.ActivityResult;

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
    private boolean captureInProgress;

    @PluginMethod
    public void capturePhoto(PluginCall call) {
        if (captureInProgress) {
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

        try {
            captureInProgress = true;
            Intent intent = new Intent(activity, CameraActivity.class);
            Log.i(TAG, "capturePhoto result=opening activity=" + CameraActivity.class.getName());
            startActivityForResult(call, intent, "captureResult");
        } catch (Exception error) {
            captureInProgress = false;
            Log.e(TAG, "capturePhoto result=open_failed", error);
            call.reject("Unable to open camera", "CAMERA_OPEN_FAILED", error);
        }
    }

    @ActivityCallback
    private void captureResult(PluginCall call, ActivityResult result) {
        captureInProgress = false;
        if (call == null) {
            Log.e(TAG, "capturePhoto result=orphaned_call");
            return;
        }

        Intent data = result.getData();
        if (result.getResultCode() != Activity.RESULT_OK) {
            String errorCode = data == null
                ? null
                : data.getStringExtra(CameraActivity.EXTRA_ERROR_CODE);
            String errorMessage = data == null
                ? null
                : data.getStringExtra(CameraActivity.EXTRA_ERROR_MESSAGE);
            if (errorCode != null && !errorCode.isEmpty()) {
                String message = errorMessage == null || errorMessage.isEmpty()
                    ? "Camera capture failed"
                    : errorMessage;
                Log.e(TAG, "capturePhoto result=error code=" + errorCode + " message=" + message);
                call.reject(message, errorCode);
                return;
            }

            Log.i(TAG, "capturePhoto result=cancelled resultCode=" + result.getResultCode());
            call.reject("Photo capture was cancelled", "CAPTURE_CANCELLED");
            return;
        }

        String photoPath = data == null
            ? null
            : data.getStringExtra(CameraActivity.EXTRA_PHOTO_PATH);
        File photo = photoPath == null ? null : new File(photoPath);
        boolean expectedPhoto = isExpectedPhoto(photo);
        if (!expectedPhoto || !photo.exists() || photo.length() == 0) {
            Log.e(TAG, "capturePhoto result=empty resultCode=" + result.getResultCode());
            if (expectedPhoto) {
                deletePhoto(photo);
            }
            call.reject("Camera returned an empty photo", "CAPTURE_EMPTY");
            return;
        }

        try {
            long size = photo.length();
            byte[] bytes = readBytes(photo);
            JSObject response = new JSObject();
            response.put("base64", Base64.encodeToString(bytes, Base64.NO_WRAP));
            response.put("mimeType", "image/jpeg");
            response.put("fileName", "camera-" + System.currentTimeMillis() + ".jpg");
            response.put("size", size);
            Log.i(TAG, "capturePhoto result=success sizeBytes=" + size);
            call.resolve(response);
        } catch (Exception error) {
            Log.e(TAG, "capturePhoto result=read_failed path=" + photo.getAbsolutePath(), error);
            call.reject("Unable to read captured photo", "CAPTURE_READ_FAILED", error);
        } finally {
            deletePhoto(photo);
        }
    }

    private boolean isExpectedPhoto(File photo) {
        if (photo == null) {
            return false;
        }
        try {
            File cameraDir = new File(getContext().getCacheDir(), CameraActivity.CAMERA_CACHE_DIR);
            String expectedPrefix = cameraDir.getCanonicalPath() + File.separator;
            return photo.getCanonicalPath().startsWith(expectedPrefix);
        } catch (IOException error) {
            Log.e(TAG, "capturePhoto result=invalid_path path=" + photo.getAbsolutePath(), error);
            return false;
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

    private void deletePhoto(File photo) {
        if (photo != null && photo.exists() && !photo.delete()) {
            Log.w(TAG, "capturePhoto result=cleanup_failed path=" + photo.getAbsolutePath());
        }
    }
}
