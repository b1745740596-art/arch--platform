from django.apps import AppConfig


class DesignConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'design'

    def ready(self):
        """开启 SQLite WAL 模式，让多窗口并行任务的读写不互相阻塞。"""
        from django.db.backends.signals import connection_created

        def enable_wal(sender, connection, **kwargs):
            if connection.vendor != 'sqlite':
                return
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA busy_timeout=30000;')

        connection_created.connect(enable_wal, dispatch_uid='design.sqlite_wal')
