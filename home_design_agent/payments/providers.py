"""支付渠道适配层。

每个渠道实现两个能力：
- create_payment(order, request)：创建渠道支付单，返回给前端展示的信息；
- webhook(request)：解析异步回调，返回 (order_no, success, reference, raw)。

本地开发默认使用 MockProvider，通过 PAYMENT_MODE=mock 即可跑通完整闭环；
上线时切换为 live 并配置对应渠道密钥。
"""
from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookPayment:
    order_no: str | None
    success: bool
    reference: str | None
    raw: dict
    amount_cents: int | None = None
    currency: str = ''


def _decimal_amount_to_cents(value) -> int | None:
    try:
        amount = Decimal(str(value)) * 100
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount != amount.to_integral_value() or amount < 0:
        return None
    return int(amount)


def _setting(name, default=None):
    return getattr(settings, name, default)


def _load_private_key(pem: str):
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_private_key(pem.encode('utf-8'), password=None)


def _load_public_key(pem: str):
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_public_key(pem.encode('utf-8'))


def rsa_sha256_sign(private_key, message: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    signature = private_key.sign(message.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode('utf-8')


def rsa_sha256_verify(public_key, message: str, signature_b64: str) -> bool:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        public_key.verify(
            base64.b64decode(signature_b64),
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:  # noqa: BLE001
        return False


class BaseProvider:
    name = 'base'

    def create_payment(self, order, request):
        raise NotImplementedError

    def webhook(self, request):
        raise NotImplementedError

    def expected_payment(self, order):
        return order.currency.upper(), int(order.amount_cents)

    def validate_webhook_order(self, order, payment: WebhookPayment):
        expected_currency, expected_amount = self.expected_payment(order)
        if payment.amount_cents is None or payment.amount_cents != expected_amount:
            raise ValueError('支付回调金额与订单不一致。')
        if (payment.currency or '').upper() != expected_currency.upper():
            raise ValueError('支付回调币种与订单不一致。')


class MockProvider(BaseProvider):
    """本地联调用的模拟渠道，不发起真实扣款。"""

    name = 'mock'

    def create_payment(self, order, request):
        return {
            'mock': True,
            'order_no': order.order_no,
            'amount': order.amount_cents / 100,
            'currency': order.currency,
        }


class StaticQrProvider(BaseProvider):
    """静态收款码渠道：不调用支付 API，展示收款码后由后台人工确认入账。"""

    name = 'static_qr'

    def create_payment(self, order, request):
        return {
            'static_qr': True,
            'provider': order.provider,
            'reference': order.order_no,
            'amount': order.amount_cents / 100,
            'currency': order.currency,
        }

    def webhook(self, request):
        return WebhookPayment(None, False, None, {})


class StripeProvider(BaseProvider):
    name = 'stripe'

    def _client(self):
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover - 上线环境安装 stripe 后才会用到
            raise RuntimeError('缺少 stripe 依赖，请安装 requirements.txt 中的 stripe。') from exc
        stripe.api_key = _setting('PAYMENT_STRIPE_SECRET_KEY', '')
        stripe.api_version = _setting('PAYMENT_STRIPE_API_VERSION', '2025-03-31.basil')
        if not stripe.api_key:
            raise RuntimeError('未配置 PAYMENT_STRIPE_SECRET_KEY。')
        return stripe

    def _target_amount(self, order):
        stripe_currency = _setting('PAYMENT_STRIPE_CURRENCY', 'usd').lower()
        if order.currency.lower() == stripe_currency:
            return stripe_currency, order.amount_cents
        if order.currency.upper() == 'CNY':
            rate = float(_setting('PAYMENT_STRIPE_EXCHANGE_RATE', 0.14))
            return stripe_currency, int(round(order.amount_cents * rate))
        return stripe_currency, order.amount_cents

    def expected_payment(self, order):
        currency, amount = self._target_amount(order)
        return currency.upper(), int(amount)

    def validate_webhook_order(self, order, payment: WebhookPayment):
        super().validate_webhook_order(order, payment)
        if order.provider_reference and payment.reference != order.provider_reference:
            raise ValueError('Stripe 回调会话与原支付订单不一致。')

    def create_payment(self, order, request):
        stripe = self._client()
        currency, amount = self._target_amount(order)
        tax_code = _setting('PAYMENT_STRIPE_TAX_CODE', 'txcd_10000000')
        success_url = request.build_absolute_uri('/billing?paid=success')
        cancel_url = request.build_absolute_uri('/billing?paid=cancel')
        session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'unit_amount': amount,
                    'product_data': {
                        'name': f'{order.plan.name} · {order.credits} 次生成额度',
                        'tax_code': tax_code,
                    },
                },
                'quantity': 1,
            }],
            client_reference_id=order.order_no,
            metadata={'payment_order_id': str(order.pk), 'order_no': order.order_no},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {
            'provider': self.name,
            'reference': session.id,
            'checkout_url': session.url,
        }

    def webhook(self, request):
        stripe = self._client()
        payload = request.body
        signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, _setting('PAYMENT_STRIPE_WEBHOOK_SECRET', ''),
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError('Stripe webhook 验签失败') from exc

        accepted_events = {
            'checkout.session.completed',
            'checkout.session.async_payment_succeeded',
        }
        if event.type not in accepted_events:
            return WebhookPayment(None, False, None, {'type': event.type})
        session = event.data.object
        order_no = session.get('client_reference_id')
        reference = session.get('id')
        payment_status = session.get('payment_status')
        metadata = session.get('metadata') or {}
        if metadata.get('order_no') and metadata.get('order_no') != order_no:
            raise ValueError('Stripe 回调订单标识不一致。')
        return WebhookPayment(
            order_no=order_no,
            success=payment_status == 'paid',
            reference=reference,
            amount_cents=session.get('amount_total'),
            currency=(session.get('currency') or '').upper(),
            raw={
                'type': event.type,
                'event_id': event.get('id'),
                'session_id': reference,
                'payment_status': payment_status,
                'amount_total': session.get('amount_total'),
                'currency': session.get('currency'),
            },
        )


class WeChatPayProvider(BaseProvider):
    """微信支付 Native（扫码）支付 v3。"""

    name = 'wechat'

    def _config(self):
        return {
            'mchid': _setting('PAYMENT_WECHAT_MCH_ID', ''),
            'appid': _setting('PAYMENT_WECHAT_APP_ID', ''),
            'serial_no': _setting('PAYMENT_WECHAT_SERIAL_NO', ''),
            'private_key': _setting('PAYMENT_WECHAT_PRIVATE_KEY', ''),
            'api_v3_key': _setting('PAYMENT_WECHAT_API_V3_KEY', ''),
            'notify_url': _setting('PAYMENT_WECHAT_NOTIFY_URL', ''),
            'platform_public_key': _setting('PAYMENT_WECHAT_PLATFORM_PUBLIC_KEY', ''),
        }

    def _authorization(self, method, path, body, cfg):
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        message = f'{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n'
        signature = rsa_sha256_sign(_load_private_key(cfg['private_key']), message)
        return (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{cfg["mchid"]}",nonce_str="{nonce}",'
            f'signature="{signature}",timestamp="{timestamp}",'
            f'serial_no="{cfg["serial_no"]}"'
        )

    def create_payment(self, order, request):
        import httpx

        cfg = self._config()
        if not all((cfg['mchid'], cfg['appid'], cfg['serial_no'], cfg['private_key'], cfg['api_v3_key'])):
            raise RuntimeError('微信支付参数未配置完整。')
        notify_url = cfg['notify_url'] or request.build_absolute_uri('/api/payments/webhook/wechat/')
        body = json.dumps({
            'appid': cfg['appid'],
            'mchid': cfg['mchid'],
            'description': f'{order.plan.name} · {order.credits} 次生成额度',
            'out_trade_no': order.order_no,
            'notify_url': notify_url,
            'amount': {'total': int(order.amount_cents), 'currency': order.currency},
        }, ensure_ascii=False)
        path = '/v3/pay/transactions/native'
        headers = {
            'Authorization': self._authorization('POST', path, body, cfg),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Arch-AI-Payments/1.0',
        }
        resp = httpx.post(
            'https://api.mch.weixin.qq.com' + path,
            content=body.encode('utf-8'),
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f'微信支付下单失败：{resp.status_code} {resp.text}')
        result = resp.json()
        return {
            'provider': self.name,
            'reference': order.order_no,
            'qr_code': result.get('code_url'),
            'raw': result,
        }

    def webhook(self, request):
        cfg = self._config()
        timestamp = request.META.get('HTTP_WECHATPAY_TIMESTAMP', '')
        nonce = request.META.get('HTTP_WECHATPAY_NONCE', '')
        signature = request.META.get('HTTP_WECHATPAY_SIGNATURE', '')
        raw_body = request.body.decode('utf-8')
        message = f'{timestamp}\n{nonce}\n{raw_body}\n'
        if not cfg['platform_public_key']:
            raise ValueError('未配置 PAYMENT_WECHAT_PLATFORM_PUBLIC_KEY，无法校验回调。')
        if not rsa_sha256_verify(_load_public_key(cfg['platform_public_key']), message, signature):
            raise ValueError('微信支付回调验签失败')

        data = json.loads(raw_body)
        resource = data.get('resource') or {}
        plaintext = _wechat_decrypt(cfg['api_v3_key'], resource)
        trade = json.loads(plaintext)
        if trade.get('mchid') != cfg['mchid'] or trade.get('appid') != cfg['appid']:
            raise ValueError('微信支付回调商户或应用标识不一致。')
        order_no = trade.get('out_trade_no')
        success = trade.get('trade_state') == 'SUCCESS'
        reference = trade.get('transaction_id')
        amount = trade.get('amount') or {}
        return WebhookPayment(
            order_no=order_no,
            success=success,
            reference=reference,
            amount_cents=amount.get('total'),
            currency=(amount.get('currency') or '').upper(),
            raw={
                'notification_id': data.get('id'),
                'mchid': trade.get('mchid'),
                'appid': trade.get('appid'),
                'out_trade_no': order_no,
                'transaction_id': reference,
                'trade_state': trade.get('trade_state'),
                'amount': {
                    'total': amount.get('total'),
                    'currency': amount.get('currency'),
                },
            },
        )


def _wechat_decrypt(api_v3_key: str, resource: dict) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    ciphertext = base64.b64decode(resource.get('ciphertext', ''))
    nonce = (resource.get('nonce') or '').encode('utf-8')
    associated_data = (resource.get('associated_data') or '').encode('utf-8')
    return AESGCM(api_v3_key.encode('utf-8')).decrypt(nonce, ciphertext, associated_data).decode('utf-8')


class AlipayProvider(BaseProvider):
    """支付宝当面付（扫码）支付。"""

    name = 'alipay'

    def _config(self):
        return {
            'app_id': _setting('PAYMENT_ALIPAY_APP_ID', ''),
            'private_key': _setting('PAYMENT_ALIPAY_PRIVATE_KEY', ''),
            'public_key': _setting('PAYMENT_ALIPAY_PUBLIC_KEY', ''),
            'seller_id': _setting('PAYMENT_ALIPAY_SELLER_ID', ''),
            'notify_url': _setting('PAYMENT_ALIPAY_NOTIFY_URL', ''),
        }

    def _build_params(self, order, cfg, request):
        biz_content = {
            'out_trade_no': order.order_no,
            'total_amount': f'{order.amount_cents / 100:.2f}',
            'subject': f'{order.plan.name} · {order.credits} 次生成额度',
            'timeout_express': '30m',
        }
        params = {
            'app_id': cfg['app_id'],
            'method': 'alipay.trade.precreate',
            'format': 'JSON',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'notify_url': cfg['notify_url'] or request.build_absolute_uri('/api/payments/webhook/alipay/'),
            'biz_content': json.dumps(biz_content, ensure_ascii=False),
        }
        unsigned = '&'.join(f'{k}={params[k]}' for k in sorted(params))
        params['sign'] = rsa_sha256_sign(_load_private_key(cfg['private_key']), unsigned)
        return params

    def create_payment(self, order, request):
        import httpx

        cfg = self._config()
        if not all((cfg['app_id'], cfg['private_key'])):
            raise RuntimeError('支付宝参数未配置完整。')
        params = self._build_params(order, cfg, request)
        resp = httpx.post(
            'https://openapi.alipay.com/gateway.do',
            data=params,
            timeout=15,
        )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise RuntimeError(f'支付宝下单返回异常：{resp.text}') from exc
        response = payload.get('alipay_trade_precreate_response') or {}
        if response.get('code') != '10000':
            raise RuntimeError(f"支付宝下单失败：{response.get('sub_msg') or response.get('msg')}")
        return {
            'provider': self.name,
            'reference': order.order_no,
            'qr_code': response.get('qr_code'),
            'raw': payload,
        }

    def webhook(self, request):
        cfg = self._config()
        params = {k: v for k, v in request.POST.items() if k not in ('sign', 'sign_type')}
        unsigned = '&'.join(f'{k}={params[k]}' for k in sorted(params))
        signature = request.POST.get('sign', '')
        if not cfg['public_key'] or not rsa_sha256_verify(_load_public_key(cfg['public_key']), unsigned, signature):
            raise ValueError('支付宝回调验签失败')
        if params.get('app_id') != cfg['app_id']:
            raise ValueError('支付宝回调应用标识不一致。')
        if cfg['seller_id'] and params.get('seller_id') != cfg['seller_id']:
            raise ValueError('支付宝回调收款账号不一致。')
        order_no = params.get('out_trade_no')
        success = params.get('trade_status') in ('TRADE_SUCCESS', 'TRADE_FINISHED')
        reference = params.get('trade_no')
        return WebhookPayment(
            order_no=order_no,
            success=success,
            reference=reference,
            amount_cents=_decimal_amount_to_cents(params.get('total_amount')),
            currency='CNY',
            raw={
                'notify_id': params.get('notify_id'),
                'app_id': params.get('app_id'),
                'seller_id': params.get('seller_id'),
                'out_trade_no': order_no,
                'trade_no': reference,
                'trade_status': params.get('trade_status'),
                'total_amount': params.get('total_amount'),
            },
        )


PROVIDERS = {
    MockProvider.name: MockProvider,
    StripeProvider.name: StripeProvider,
    WeChatPayProvider.name: WeChatPayProvider,
    AlipayProvider.name: AlipayProvider,
}


def get_provider(name: str):
    """根据渠道名取 provider；mock 模式强制走 MockProvider，二维码模式走静态收款码。"""
    if _setting('PAYMENT_QR_MODE', False):
        return StaticQrProvider()
    if _setting('PAYMENT_MODE', 'mock') != 'live':
        if not settings.DEBUG:
            raise RuntimeError('生产环境禁止使用模拟支付渠道。')
        return MockProvider()
    provider_cls = PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f'不支持的支付渠道：{name}')
    return provider_cls()
