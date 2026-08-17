from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import PasswordResetToken


def create_password_reset_token(user):
    """为用户创建一次性重置令牌；旧未用令牌同步作废。"""
    PasswordResetToken.objects.filter(
        user=user, used_at__isnull=True,
    ).update(used_at=timezone.now())

    raw_token = PasswordResetToken.generate_raw_token()
    expires_at = timezone.now() + timedelta(
        minutes=settings.PASSWORD_RESET_TIMEOUT_MINUTES,
    )
    PasswordResetToken.objects.create(
        user=user,
        token_hash=PasswordResetToken.hash_token(raw_token),
        expires_at=expires_at,
    )
    return raw_token


def consume_password_reset_token(user, raw_token):
    """校验并消耗令牌；无效/过期返回 None。"""
    token = PasswordResetToken.objects.filter(
        user=user,
        token_hash=PasswordResetToken.hash_token(raw_token),
        used_at__isnull=True,
    ).order_by('-created_at').first()
    if token is None or not token.is_valid:
        return None
    token.used_at = timezone.now()
    token.save(update_fields=['used_at'])
    return token


def build_password_reset_url(request, user, raw_token):
    """拼接前端重置页链接：/reset-password?uid=..&token=.."""
    path = f'/reset-password?uid={user.pk}&token={raw_token}'
    return request.build_absolute_uri(path)


def send_password_reset_email(user, raw_token, reset_url):
    subject = '重置你的 Arch_AI 账号密码'
    message = (
        f'你好，{user.get_username()}：\n\n'
        f'我们收到了重置密码的请求。请在 {settings.PASSWORD_RESET_TIMEOUT_MINUTES} '
        f'分钟内点击以下链接完成重置：\n\n{reset_url}\n\n'
        '如果不是你本人操作，请忽略此邮件。'
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=settings.DEBUG,
    )
