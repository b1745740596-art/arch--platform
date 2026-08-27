import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def test_native_plugins_are_registered_before_capacitor_creates_the_bridge():
    source = (BASE_DIR / 'frontend/native/android/MainActivity.java').read_text()
    bridge_creation = source.index('super.onCreate(savedInstanceState);')

    assert source.index('registerPlugin(ApkUpdaterPlugin.class);') < bridge_creation
    assert source.index('registerPlugin(CameraCapturePlugin.class);') < bridge_creation


def test_apk_build_packages_the_camera_plugin():
    workflow = (BASE_DIR.parent / '.github/workflows/build-apk.yml').read_text()

    assert (
        'cp native/android/CameraActivity.java '
        'android/app/src/main/java/com/archai/home/CameraActivity.java'
    ) in workflow
    assert (
        'cp native/android/CameraCapturePlugin.java '
        'android/app/src/main/java/com/archai/home/CameraCapturePlugin.java'
    ) in workflow
    assert 'python3 native/android/configure_camera.py android' in workflow


def test_native_camera_uses_fullscreen_camerax_preview():
    plugin = (BASE_DIR / 'frontend/native/android/CameraCapturePlugin.java').read_text()
    activity = (BASE_DIR / 'frontend/native/android/CameraActivity.java').read_text()
    installer = (BASE_DIR / 'frontend/native/android/configure_camera.py').read_text()

    assert 'new Intent(activity, CameraActivity.class)' in plugin
    assert 'MediaStore.ACTION_IMAGE_CAPTURE' not in plugin
    assert 'PreviewView.ScaleType.FILL_CENTER' in activity
    assert 'WindowCompat.setDecorFitsSystemWindows(getWindow(), false)' in activity
    assert 'UseCaseGroup.Builder' in activity
    assert 'previewView.getViewPort()' in activity
    assert 'android.permission.CAMERA' in installer
    assert 'android:name=".CameraActivity"' in installer
    assert 'androidx.camera:camera-view' in installer


def test_native_camera_does_not_fall_back_to_the_gallery():
    source = (BASE_DIR / 'frontend/src/components/PlanWorkspace.vue').read_text()
    open_camera = source[
        source.index('async function openCamera()') : source.index('function openGallery()')
    ]

    assert open_camera.count('cameraInput.value?.click()') == 1
    assert open_camera.index('if (!nativePlatform)') < open_camera.index(
        'cameraInput.value?.click()'
    )
    assert open_camera.index('cameraInput.value?.click()') < open_camera.index(
        'if (!pluginAvailable)'
    )
    assert "ElMessage.error(t('plan.cameraUnavailable'))" in open_camera


def test_broken_native_updater_can_fall_back_to_the_system_browser():
    release = json.loads((BASE_DIR / 'app_release.json').read_text())
    source = (BASE_DIR / 'frontend/src/stores/appUpdate.js').read_text()

    assert release['external_apk_url'] == (
        'https://github.com/b1745740596-art/arch--platform/'
        'releases/download/apk/app-release.apk'
    )
    assert "Capacitor.isPluginAvailable('ApkUpdater')" in source
    assert 'window.location.assign(fallbackUrl)' in source
