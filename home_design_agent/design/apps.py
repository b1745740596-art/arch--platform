from django.apps import AppConfig


class DesignConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'design'

    def ready(self):
        """开启 SQLite WAL 模式，让多窗口并行任务的读写不互相阻塞。

        同时注册 HEIF/HEIC 图像打开器，允许 iPhone 等设备直接上传 HEIC 照片，
        后续再由工作流统一转换为 JPG/PNG。
        """
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        from django.db.backends.signals import connection_created

        def enable_wal(sender, connection, **kwargs):
            if connection.vendor != 'sqlite':
                return
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA busy_timeout=30000;')

        connection_created.connect(enable_wal, dispatch_uid='design.sqlite_wal')
