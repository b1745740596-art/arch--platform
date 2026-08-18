"""支付链路自检命令：在服务器上快速定位支付配置缺口。

用法：
    python manage.py check_payments
"""
from django.core.management.base import BaseCommand

from payments.services import get_payment_diagnostics


class Command(BaseCommand):
    help = '检查支付运行模式、依赖与渠道密钥配置'

    def handle(self, *args, **options):
        data = get_payment_diagnostics()
        self.stdout.write(f"PAYMENT_MODE       : {data['payment_mode']}")
        self.stdout.write(f"FREE_CREDITS       : {data['free_credits']}")
        self.stdout.write(f"ACTIVE_PLANS       : {data['plans_count']}")
        self.stdout.write('')
        for name, info in data['providers'].items():
            self.stdout.write(
                f"{name:8s} configured={str(info['configured']):5s} "
                f"package_installed={info['package_installed']}"
            )
        self.stdout.write('')
        self.stdout.write('Webhook URLs（渠道后台需配置为公网 HTTPS 地址）：')
        for name, url in data['webhook_urls'].items():
            self.stdout.write(f"  {name:8s} {url}")
