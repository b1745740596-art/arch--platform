"""额度与支付领域服务。

额度模型：
- 用户注册即拥有 PAYMENT_FREE_CREDITS（默认 5）次免费生成额度；
- 充值成功后 purchased_credits 增加套餐对应的次数；
- 生成时优先消耗免费额度，再消耗充值额度。
"""
from __future__ import annotations

import importlib.util
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import APIException

from users.models import UserProfile

from .models import CreditTransaction, PaymentOrder, PricingPlan
from .providers import get_provider


class InsufficientCreditsError(APIException):
    status_code = 402
    default_detail = '生成额度不足，请先充值。'
    default_code = 'insufficient_credits'


class PaymentProviderError(APIException):
    status_code = 503
    default_detail = '支付渠道暂时不可用，请稍后再试。'
    default_code = 'payment_provider_error'


def _lock_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'free_credits': settings.PAYMENT_FREE_CREDITS},
    )
    return UserProfile.objects.select_for_update().get(pk=profile.pk)


def balance_for_user(user):
    """返回用户额度信息；未创建资料时按默认值补齐。"""
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'free_credits': settings.PAYMENT_FREE_CREDITS},
    )
    return {
        'free_credits': profile.free_credits,
        'purchased_credits': profile.purchased_credits,
        'total_credits': profile.free_credits + profile.purchased_credits,
        'payment_mode': settings.PAYMENT_MODE,
    }


def consume_generation_credit(user, amount: int = 1, note: str = '效果图生成') -> dict:
    """生成前预扣一次额度，返回实际扣减明细（供失败时原路退回）。"""
    if amount <= 0:
        return {'free_used': 0, 'purchased_used': 0, 'balance_after': None}

    with transaction.atomic():
        profile = _lock_profile(user)
        available = profile.free_credits + profile.purchased_credits
        if available < amount:
            raise InsufficientCreditsError({
                'detail': f'生成额度不足，当前剩余 {available} 次，请先充值。',
                'free_credits': profile.free_credits,
                'purchased_credits': profile.purchased_credits,
            })

        free_used = min(profile.free_credits, amount)
        purchased_used = amount - free_used
        profile.free_credits -= free_used
        profile.purchased_credits -= purchased_used
        profile.save(update_fields=['free_credits', 'purchased_credits', 'updated_at'])

        balance_after = profile.free_credits + profile.purchased_credits
        CreditTransaction.objects.create(
            user=user,
            kind=CreditTransaction.Kind.CONSUME,
            credits=-amount,
            balance_after=balance_after,
            note=note,
        )
        return {
            'free_used': free_used,
            'purchased_used': purchased_used,
            'balance_after': balance_after,
        }


def refund_generation_credit(user, free_used: int, purchased_used: int, note: str = '生成失败退回') -> None:
    """生成失败时原路退回已预扣额度。"""
    if free_used <= 0 and purchased_used <= 0:
        return
    with transaction.atomic():
        profile = _lock_profile(user)
        profile.free_credits += free_used
        profile.purchased_credits += purchased_used
        profile.save(update_fields=['free_credits', 'purchased_credits', 'updated_at'])
        CreditTransaction.objects.create(
            user=user,
            kind=CreditTransaction.Kind.REFUND,
            credits=free_used + purchased_used,
            balance_after=profile.free_credits + profile.purchased_credits,
            note=note,
        )


def create_payment_order(user, plan: PricingPlan, provider_name: str, request):
    """创建待支付订单并调用渠道生成支付参数。"""
    provider = get_provider(provider_name)
    order = PaymentOrder.objects.create(
        user=user,
        plan=plan,
        provider=provider_name,
        amount_cents=plan.price_cents,
        currency=plan.currency,
        credits=plan.credits,
    )
    try:
        payload = provider.create_payment(order, request)
    except PaymentProviderError:
        order.status = PaymentOrder.Status.FAILED
        order.save(update_fields=['status', 'updated_at'])
        raise
    except Exception as exc:
        order.status = PaymentOrder.Status.FAILED
        order.save(update_fields=['status', 'updated_at'])
        raise PaymentProviderError(str(exc)) from exc

    order.provider_reference = payload.get('reference') or ''
    order.provider_response = payload
    order.save(update_fields=['provider_reference', 'provider_response', 'updated_at'])
    return order, payload


def mark_order_paid(order: PaymentOrder, reference: str = '', raw=None) -> PaymentOrder:
    """幂等入账：把订单标记为已支付并把额度计入用户账户。"""
    with transaction.atomic():
        order = PaymentOrder.objects.select_for_update().get(pk=order.pk)
        if order.status == PaymentOrder.Status.PAID:
            return order

        profile = _lock_profile(order.user)
        profile.purchased_credits += order.credits
        profile.save(update_fields=['purchased_credits', 'updated_at'])

        order.status = PaymentOrder.Status.PAID
        order.paid_at = timezone.now()
        if reference:
            order.provider_reference = reference
        if raw is not None:
            order.provider_response = raw
        order.save(update_fields=[
            'status', 'paid_at', 'provider_reference', 'provider_response', 'updated_at',
        ])

        CreditTransaction.objects.create(
            user=order.user,
            order=order,
            kind=CreditTransaction.Kind.PURCHASE,
            credits=order.credits,
            balance_after=profile.free_credits + profile.purchased_credits,
            note=f'购买套餐：{order.plan.name if order.plan else "套餐已删除"}',
        )
        return order


def resolve_webhook(provider_name: str, request):
    """解析渠道回调并尝试入账。返回 (order, handled, success)。"""
    provider = get_provider(provider_name)
    order_no, success, reference, raw = provider.webhook(request)
    if not order_no:
        return None, False, False
    order = PaymentOrder.objects.filter(order_no=order_no).first()
    if order is None:
        return None, True, False
    if success:
        mark_order_paid(order, reference=reference, raw=raw)
    return order, True, success


def _revenue_group(queryset):
    rows = queryset.values('currency').annotate(
        amount_cents=Sum('amount_cents'),
        order_count=Count('id'),
    )
    return [
        {'currency': row['currency'], 'amount_cents': row['amount_cents'] or 0,
         'order_count': row['order_count']}
        for row in rows
    ]


def get_admin_stats():
    """营业额与收款概览：总营业额、今日、本月、近 14 日趋势、按渠道拆分。"""
    paid = PaymentOrder.objects.filter(status=PaymentOrder.Status.PAID)
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    by_provider = paid.values('provider').annotate(
        amount_cents=Sum('amount_cents'),
        order_count=Count('id'),
    )

    trend_start = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_map = {}
    for paid_at, amount_cents in paid.filter(paid_at__gte=trend_start).values_list(
        'paid_at', 'amount_cents',
    ):
        local_date = timezone.localtime(paid_at).date()
        current = daily_map.setdefault(local_date, {'amount_cents': 0, 'order_count': 0})
        current['amount_cents'] += amount_cents
        current['order_count'] += 1

    daily_revenue = []
    for offset in range(14):
        day = (trend_start + timedelta(days=offset)).date()
        item = daily_map.get(day, {'amount_cents': 0, 'order_count': 0})
        daily_revenue.append({
            'date': day.strftime('%m-%d'),
            'amount_cents': item['amount_cents'],
            'order_count': item['order_count'],
        })

    return {
        'total_revenue': _revenue_group(paid),
        'today_revenue': _revenue_group(paid.filter(paid_at__gte=today_start)),
        'month_revenue': _revenue_group(paid.filter(paid_at__gte=month_start)),
        'daily_revenue': daily_revenue,
        'total_orders': PaymentOrder.objects.count(),
        'paid_orders': paid.count(),
        'pending_orders': PaymentOrder.objects.filter(status=PaymentOrder.Status.PENDING).count(),
        'by_provider': [
            {'provider': row['provider'], 'provider_display': PaymentOrder.Provider(row['provider']).label,
             'amount_cents': row['amount_cents'] or 0, 'order_count': row['order_count']}
            for row in by_provider
        ],
        'generated_at': timezone.now(),
    }


def _package_installed(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def get_payment_diagnostics(request=None):
    """支付链路自检：报告运行模式、依赖与各渠道密钥配置情况。"""
    wechat_ready = all((
        settings.PAYMENT_WECHAT_APP_ID,
        settings.PAYMENT_WECHAT_MCH_ID,
        settings.PAYMENT_WECHAT_SERIAL_NO,
        settings.PAYMENT_WECHAT_PRIVATE_KEY,
        settings.PAYMENT_WECHAT_API_V3_KEY,
        settings.PAYMENT_WECHAT_PLATFORM_PUBLIC_KEY,
    ))
    alipay_ready = all((
        settings.PAYMENT_ALIPAY_APP_ID,
        settings.PAYMENT_ALIPAY_PRIVATE_KEY,
        settings.PAYMENT_ALIPAY_PUBLIC_KEY,
    ))
    stripe_ready = bool(settings.PAYMENT_STRIPE_SECRET_KEY)

    def _abs(path):
        return request.build_absolute_uri(path) if request else path

    return {
        'payment_mode': settings.PAYMENT_MODE,
        'free_credits': settings.PAYMENT_FREE_CREDITS,
        'plans_count': PricingPlan.objects.filter(is_active=True).count(),
        'webhook_urls': {
            'stripe': _abs('/api/payments/webhook/stripe/'),
            'wechat': _abs('/api/payments/webhook/wechat/'),
            'alipay': _abs('/api/payments/webhook/alipay/'),
        },
        'providers': {
            'stripe': {
                'configured': stripe_ready,
                'package_installed': _package_installed('stripe'),
                'currency': settings.PAYMENT_STRIPE_CURRENCY,
            },
            'wechat': {
                'configured': wechat_ready,
                'package_installed': _package_installed('httpx') and _package_installed('cryptography'),
            },
            'alipay': {
                'configured': alipay_ready,
                'package_installed': _package_installed('httpx') and _package_installed('cryptography'),
            },
        },
        'generated_at': timezone.now(),
    }
