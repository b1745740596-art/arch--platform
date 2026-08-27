from pathlib import Path
import sys


CAMERA_DEPENDENCIES = '''    def cameraXVersion = "1.3.4"
    implementation "androidx.camera:camera-core:$cameraXVersion"
    implementation "androidx.camera:camera-camera2:$cameraXVersion"
    implementation "androidx.camera:camera-lifecycle:$cameraXVersion"
    implementation "androidx.camera:camera-view:$cameraXVersion"
'''

CAMERA_ACTIVITY = '''        <activity
            android:name=".CameraActivity"
            android:configChanges="orientation|screenSize"
            android:exported="false"
            android:screenOrientation="fullSensor"
            android:theme="@style/AppTheme.NoActionBar" />

'''


def configure_gradle(android_dir: Path) -> None:
    gradle = android_dir / 'app/build.gradle'
    source = gradle.read_text()
    if 'androidx.camera:camera-view' not in source:
        marker = '    testImplementation "junit:junit:$junitVersion"\n'
        if marker not in source:
            raise RuntimeError('Unable to locate Android dependency insertion point')
        source = source.replace(marker, CAMERA_DEPENDENCIES + marker, 1)
        gradle.write_text(source)


def configure_manifest(android_dir: Path) -> None:
    manifest = android_dir / 'app/src/main/AndroidManifest.xml'
    source = manifest.read_text()
    if 'android.permission.CAMERA' not in source:
        marker = '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        if marker not in source:
            raise RuntimeError('Unable to locate Android manifest permission insertion point')
        source = source.replace(
            marker,
            marker
            + '\n    <uses-permission android:name="android.permission.CAMERA" />\n'
            + '    <uses-feature android:name="android.hardware.camera.any" '
            + 'android:required="false" />\n',
            1,
        )
    if 'android:name=".CameraActivity"' not in source:
        marker = '    </application>\n'
        if marker not in source:
            raise RuntimeError('Unable to locate Android activity insertion point')
        source = source.replace(marker, CAMERA_ACTIVITY + marker, 1)
    manifest.write_text(source)


def main() -> None:
    android_dir = Path(sys.argv[1] if len(sys.argv) > 1 else 'android')
    configure_gradle(android_dir)
    configure_manifest(android_dir)
    print('CameraX dependencies and manifest configured')


if __name__ == '__main__':
    main()
