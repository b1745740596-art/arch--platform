package com.archai.home;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageCapture;
import androidx.camera.core.ImageCaptureException;
import androidx.camera.core.Preview;
import androidx.camera.core.UseCaseGroup;
import androidx.camera.core.ViewPort;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.google.common.util.concurrent.ListenableFuture;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CameraActivity extends AppCompatActivity {
    public static final String EXTRA_PHOTO_PATH = "com.archai.home.camera.PHOTO_PATH";
    public static final String EXTRA_ERROR_CODE = "com.archai.home.camera.ERROR_CODE";
    public static final String EXTRA_ERROR_MESSAGE = "com.archai.home.camera.ERROR_MESSAGE";
    public static final String CAMERA_CACHE_DIR = "captured-images";

    private static final String TAG = "InAppCamera";
    private static final int CAMERA_PERMISSION_REQUEST = 4107;

    private PreviewView previewView;
    private CameraControlView flashButton;
    private CameraControlView switchButton;
    private ShutterView shutterButton;
    private ProcessCameraProvider cameraProvider;
    private CameraSelector cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA;
    private ImageCapture imageCapture;
    private ExecutorService cameraExecutor;
    private boolean usingFrontCamera;
    private boolean flashEnabled;
    private boolean capturing;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        cameraExecutor = Executors.newSingleThreadExecutor();
        configureFullscreenWindow();
        setContentView(createCameraLayout());
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                cancelCapture();
            }
        });

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED) {
            Log.i(TAG, "open result=permission_granted");
            scheduleCameraStart();
        } else {
            Log.i(TAG, "open result=permission_required");
            ActivityCompat.requestPermissions(
                this,
                new String[]{Manifest.permission.CAMERA},
                CAMERA_PERMISSION_REQUEST
            );
        }
    }

    private void configureFullscreenWindow() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            WindowManager.LayoutParams attributes = getWindow().getAttributes();
            attributes.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            getWindow().setAttributes(attributes);
        }
        hideSystemBars();
    }

    private void hideSystemBars() {
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(
            getWindow(),
            getWindow().getDecorView()
        );
        controller.hide(WindowInsetsCompat.Type.systemBars());
        controller.setSystemBarsBehavior(
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        );
    }

    private View createCameraLayout() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        previewView = new PreviewView(this);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        root.addView(
            previewView,
            new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        );

        CameraControlView backButton = new CameraControlView(this, CameraControlView.BACK);
        backButton.setContentDescription("返回");
        backButton.setOnClickListener(view -> cancelCapture());
        root.addView(
            backButton,
            overlayParams(56, 56, Gravity.TOP | Gravity.START, 16, 36, 0, 0)
        );

        flashButton = new CameraControlView(this, CameraControlView.FLASH);
        flashButton.setContentDescription("切换闪光灯");
        flashButton.setVisibility(View.GONE);
        flashButton.setOnClickListener(view -> toggleFlash());
        root.addView(
            flashButton,
            overlayParams(56, 56, Gravity.TOP | Gravity.END, 0, 36, 16, 0)
        );

        shutterButton = new ShutterView(this);
        shutterButton.setContentDescription("拍照");
        shutterButton.setEnabled(false);
        shutterButton.setOnClickListener(view -> capturePhoto());
        root.addView(
            shutterButton,
            overlayParams(86, 86, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL, 0, 0, 0, 34)
        );

        switchButton = new CameraControlView(this, CameraControlView.SWITCH_CAMERA);
        switchButton.setContentDescription("切换前后摄像头");
        switchButton.setVisibility(View.GONE);
        switchButton.setOnClickListener(view -> switchCamera());
        root.addView(
            switchButton,
            overlayParams(58, 58, Gravity.BOTTOM | Gravity.END, 0, 0, 24, 48)
        );

        return root;
    }

    private FrameLayout.LayoutParams overlayParams(
        int widthDp,
        int heightDp,
        int gravity,
        int leftDp,
        int topDp,
        int rightDp,
        int bottomDp
    ) {
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
            dp(widthDp),
            dp(heightDp),
            gravity
        );
        params.setMargins(dp(leftDp), dp(topDp), dp(rightDp), dp(bottomDp));
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void scheduleCameraStart() {
        previewView.post(this::startCamera);
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> providerFuture =
            ProcessCameraProvider.getInstance(this);
        providerFuture.addListener(() -> {
            try {
                cameraProvider = providerFuture.get();
                bindCameraUseCases();
            } catch (Exception error) {
                finishWithError(
                    "CAMERA_OPEN_FAILED",
                    "Unable to initialize the camera",
                    error
                );
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void bindCameraUseCases() {
        if (cameraProvider == null || previewView.getDisplay() == null || isFinishing()) {
            return;
        }

        try {
            int rotation = previewView.getDisplay().getRotation();
            Preview preview = new Preview.Builder()
                .setTargetRotation(rotation)
                .build();
            preview.setSurfaceProvider(previewView.getSurfaceProvider());

            imageCapture = new ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .setFlashMode(flashEnabled ? ImageCapture.FLASH_MODE_ON : ImageCapture.FLASH_MODE_OFF)
                .setTargetRotation(rotation)
                .build();

            UseCaseGroup.Builder useCases = new UseCaseGroup.Builder()
                .addUseCase(preview)
                .addUseCase(imageCapture);
            ViewPort viewPort = previewView.getViewPort();
            if (viewPort != null) {
                useCases.setViewPort(viewPort);
            }

            cameraProvider.unbindAll();
            Camera camera = cameraProvider.bindToLifecycle(
                this,
                cameraSelector,
                useCases.build()
            );
            boolean hasFlash = camera.getCameraInfo().hasFlashUnit();
            flashButton.setVisibility(hasFlash ? View.VISIBLE : View.GONE);
            flashButton.setActive(hasFlash && flashEnabled);
            switchButton.setVisibility(hasFrontAndBackCameras() ? View.VISIBLE : View.GONE);
            shutterButton.setEnabled(true);
            switchButton.setEnabled(true);
            Log.i(
                TAG,
                "bind result=success lens=" + (usingFrontCamera ? "front" : "back")
                    + " previewScale=FILL_CENTER hasFlash=" + hasFlash
            );
        } catch (Exception error) {
            finishWithError("CAMERA_OPEN_FAILED", "Unable to open the camera", error);
        }
    }

    private boolean hasFrontAndBackCameras() {
        try {
            return cameraProvider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA)
                && cameraProvider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA);
        } catch (Exception error) {
            Log.w(TAG, "cameraList result=unavailable", error);
            return false;
        }
    }

    private void toggleFlash() {
        if (imageCapture == null || capturing) {
            return;
        }
        flashEnabled = !flashEnabled;
        imageCapture.setFlashMode(
            flashEnabled ? ImageCapture.FLASH_MODE_ON : ImageCapture.FLASH_MODE_OFF
        );
        flashButton.setActive(flashEnabled);
        Log.i(TAG, "flash result=changed enabled=" + flashEnabled);
    }

    private void switchCamera() {
        if (cameraProvider == null || capturing) {
            return;
        }
        usingFrontCamera = !usingFrontCamera;
        cameraSelector = usingFrontCamera
            ? CameraSelector.DEFAULT_FRONT_CAMERA
            : CameraSelector.DEFAULT_BACK_CAMERA;
        flashEnabled = false;
        shutterButton.setEnabled(false);
        switchButton.setEnabled(false);
        bindCameraUseCases();
    }

    private void capturePhoto() {
        ImageCapture capture = imageCapture;
        if (capture == null || capturing) {
            return;
        }

        File photo;
        try {
            File cameraDir = new File(getCacheDir(), CAMERA_CACHE_DIR);
            if (!cameraDir.exists() && !cameraDir.mkdirs()) {
                throw new IOException("Unable to create camera cache directory");
            }
            photo = File.createTempFile("room-photo-", ".jpg", cameraDir);
        } catch (IOException error) {
            finishWithError("CAPTURE_WRITE_FAILED", "Unable to prepare the photo", error);
            return;
        }

        capturing = true;
        shutterButton.setEnabled(false);
        switchButton.setEnabled(false);
        flashButton.setEnabled(false);
        ImageCapture.OutputFileOptions options = new ImageCapture.OutputFileOptions.Builder(photo)
            .build();
        Log.i(
            TAG,
            "capture input=lens:" + (usingFrontCamera ? "front" : "back")
                + " flash:" + flashEnabled
        );
        capture.takePicture(options, cameraExecutor, new ImageCapture.OnImageSavedCallback() {
            @Override
            public void onImageSaved(ImageCapture.OutputFileResults output) {
                runOnUiThread(() -> finishWithPhoto(photo));
            }

            @Override
            public void onError(ImageCaptureException error) {
                if (photo.exists() && !photo.delete()) {
                    Log.w(TAG, "capture result=cleanup_failed path=" + photo.getAbsolutePath());
                }
                runOnUiThread(() -> finishWithError(
                    "CAPTURE_FAILED",
                    "Unable to capture the photo",
                    error
                ));
            }
        });
    }

    private void finishWithPhoto(File photo) {
        long size = photo.exists() ? photo.length() : 0;
        if (size == 0) {
            if (photo.exists() && !photo.delete()) {
                Log.w(TAG, "capture result=cleanup_failed path=" + photo.getAbsolutePath());
            }
            finishWithError("CAPTURE_EMPTY", "Camera returned an empty photo", null);
            return;
        }

        Intent result = new Intent();
        result.putExtra(EXTRA_PHOTO_PATH, photo.getAbsolutePath());
        Log.i(TAG, "capture result=success sizeBytes=" + size);
        setResult(Activity.RESULT_OK, result);
        finish();
    }

    private void cancelCapture() {
        if (capturing) {
            return;
        }
        Log.i(TAG, "capture result=cancelled");
        setResult(Activity.RESULT_CANCELED);
        finish();
    }

    private void finishWithError(String code, String message, Throwable error) {
        if (error == null) {
            Log.e(TAG, "capture result=error code=" + code + " message=" + message);
        } else {
            Log.e(TAG, "capture result=error code=" + code + " message=" + message, error);
        }
        Intent result = new Intent();
        result.putExtra(EXTRA_ERROR_CODE, code);
        result.putExtra(EXTRA_ERROR_MESSAGE, message);
        setResult(Activity.RESULT_CANCELED, result);
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
        finish();
    }

    @Override
    public void onRequestPermissionsResult(
        int requestCode,
        String[] permissions,
        int[] grantResults
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != CAMERA_PERMISSION_REQUEST) {
            return;
        }
        boolean granted = grantResults.length > 0
            && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        Log.i(TAG, "permission result=" + (granted ? "granted" : "denied"));
        if (granted) {
            scheduleCameraStart();
        } else {
            finishWithError(
                "CAMERA_PERMISSION_DENIED",
                "Camera permission is required to take a photo",
                null
            );
        }
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        previewView.post(() -> {
            if (imageCapture != null && previewView.getDisplay() != null) {
                imageCapture.setTargetRotation(previewView.getDisplay().getRotation());
            }
        });
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemBars();
        }
    }

    @Override
    protected void onDestroy() {
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        if (cameraExecutor != null) {
            cameraExecutor.shutdown();
        }
        super.onDestroy();
    }

    private static class ShutterView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

        ShutterView(CameraActivity context) {
            super(context);
            setClickable(true);
            setFocusable(true);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float centerX = getWidth() / 2f;
            float centerY = getHeight() / 2f;
            float radius = Math.min(getWidth(), getHeight()) / 2f;
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(radius * 0.08f);
            paint.setColor(Color.WHITE);
            paint.setAlpha(isEnabled() ? 255 : 120);
            canvas.drawCircle(centerX, centerY, radius * 0.82f, paint);
            paint.setStyle(Paint.Style.FILL);
            canvas.drawCircle(centerX, centerY, radius * 0.66f, paint);
        }

        @Override
        public void setEnabled(boolean enabled) {
            super.setEnabled(enabled);
            invalidate();
        }
    }

    private static class CameraControlView extends View {
        static final int BACK = 1;
        static final int FLASH = 2;
        static final int SWITCH_CAMERA = 3;

        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final int control;
        private boolean active;

        CameraControlView(CameraActivity context, int control) {
            super(context);
            this.control = control;
            setClickable(true);
            setFocusable(true);
        }

        void setActive(boolean active) {
            this.active = active;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float width = getWidth();
            float height = getHeight();
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.argb(105, 0, 0, 0));
            canvas.drawCircle(width / 2f, height / 2f, Math.min(width, height) * 0.46f, paint);

            paint.setColor(Color.WHITE);
            paint.setAlpha(isEnabled() ? 255 : 120);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeJoin(Paint.Join.ROUND);
            paint.setStrokeWidth(Math.min(width, height) * 0.055f);
            if (control == BACK) {
                drawBack(canvas, width, height);
            } else if (control == FLASH) {
                drawFlash(canvas, width, height);
            } else {
                drawSwitchCamera(canvas, width, height);
            }
        }

        private void drawBack(Canvas canvas, float width, float height) {
            Path path = new Path();
            path.moveTo(width * 0.58f, height * 0.27f);
            path.lineTo(width * 0.34f, height * 0.50f);
            path.lineTo(width * 0.58f, height * 0.73f);
            canvas.drawPath(path, paint);
        }

        private void drawFlash(Canvas canvas, float width, float height) {
            Path bolt = new Path();
            bolt.moveTo(width * 0.56f, height * 0.20f);
            bolt.lineTo(width * 0.35f, height * 0.52f);
            bolt.lineTo(width * 0.50f, height * 0.52f);
            bolt.lineTo(width * 0.43f, height * 0.80f);
            bolt.lineTo(width * 0.67f, height * 0.43f);
            bolt.lineTo(width * 0.51f, height * 0.43f);
            bolt.close();
            paint.setStyle(Paint.Style.FILL);
            canvas.drawPath(bolt, paint);
            if (!active) {
                paint.setStyle(Paint.Style.STROKE);
                paint.setColor(Color.rgb(255, 105, 105));
                canvas.drawLine(width * 0.28f, height * 0.28f, width * 0.72f, height * 0.72f, paint);
            }
        }

        private void drawSwitchCamera(Canvas canvas, float width, float height) {
            RectF arc = new RectF(
                width * 0.25f,
                height * 0.25f,
                width * 0.75f,
                height * 0.75f
            );
            canvas.drawArc(arc, 205f, 205f, false, paint);
            canvas.drawArc(arc, 25f, 205f, false, paint);
            paint.setStyle(Paint.Style.FILL);
            Path upperArrow = new Path();
            upperArrow.moveTo(width * 0.72f, height * 0.23f);
            upperArrow.lineTo(width * 0.72f, height * 0.43f);
            upperArrow.lineTo(width * 0.55f, height * 0.30f);
            upperArrow.close();
            canvas.drawPath(upperArrow, paint);
            Path lowerArrow = new Path();
            lowerArrow.moveTo(width * 0.28f, height * 0.77f);
            lowerArrow.lineTo(width * 0.28f, height * 0.57f);
            lowerArrow.lineTo(width * 0.45f, height * 0.70f);
            lowerArrow.close();
            canvas.drawPath(lowerArrow, paint);
        }
    }
}
