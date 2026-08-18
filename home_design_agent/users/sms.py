"""短信发送后端。

默认使用控制台后端（仅打印日志，便于本地联调）。生产可切换为通用 Webhook
后端，把 `{phone, code}` POST 到短信网关，再自行对接具体厂商模板。
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class ConsoleSmsBackend:
    """本地开发后端：验证码只打印到日志，不真实发送。"""

    def send(self, phone, code):
        logger.info('短信验证码：phone=%s code=%s', phone, code)


class WebhookSmsBackend:
    """通用 Webhook 后端：POST JSON 到 SMS_WEBHOOK_URL。"""

    def send(self, phone, code):
        url = getattr(settings, 'SMS_WEBHOOK_URL', '')
        if not url:
            raise RuntimeError('SMS_WEBHOOK_URL 未配置，无法发送短信。')
        response = httpx.post(
            url,
            json={'phone': phone, 'code': code},
            timeout=float(getattr(settings, 'SMS_WEBHOOK_TIMEOUT', 10)),
        )
        response.raise_for_status()


def get_sms_backend():
    backend = getattr(settings, 'SMS_BACKEND', 'console')
    if backend == 'webhook':
        return WebhookSmsBackend()
    return ConsoleSmsBackend()


def send_sms_code(phone, code):
    get_sms_backend().send(phone, code)
