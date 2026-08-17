from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from users.roles import ROLE_LABELS, ROLE_PERMISSIONS


class Command(BaseCommand):
    help = '创建默认角色组并绑定最小权限集。'

    def handle(self, *args, **options):
        for role, permission_keys in ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=role)
            permissions = []
            for key in permission_keys:
                try:
                    app_label, codename = key.split('.', 1)
                    permission = Permission.objects.get(
                        content_type__app_label=app_label,
                        codename=codename,
                    )
                except (Permission.DoesNotExist, ValueError):
                    self.stderr.write(self.style.WARNING(f'权限不存在，跳过: {key}'))
                    continue
                permissions.append(permission)
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(
                f'{"创建" if created else "更新"}角色 {ROLE_LABELS.get(role, role)}'
                f'（{len(permissions)} 项权限）'
            ))
