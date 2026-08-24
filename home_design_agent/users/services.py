import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import (
    EmailVerificationCode,
    PasswordResetToken,
    RememberToken,
    SmsVerificationCode,
)
from .sms import send_sms_code

PHONE_RE = re.compile(r'^1[3-9]\d{9}$')


def _ensure_email_delivery_is_private():
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if not settings.DEBUG and backend.endswith('console.EmailBackend'):
        raise ImproperlyConfigured('生产环境禁止使用 console 邮件后端。')


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


@transaction.atomic
def consume_password_reset_token(user, raw_token):
    """校验并消耗令牌；无效/过期返回 None。"""
    token = PasswordResetToken.objects.select_for_update().filter(
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
    _ensure_email_delivery_is_private()
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


def normalize_phone(value):
    """去掉空格、横线与括号，返回纯数字；空值返回空字符串。"""
    if not value:
        return ''
    return re.sub(r'[\s\-()]', '', str(value))


def is_valid_phone(value):
    """校验中国大陆手机号。"""
    return bool(PHONE_RE.match(value or ''))


def create_sms_code(phone, purpose):
    """为指定手机号与用途创建一次性短信验证码，旧未用验证码作废。"""
    SmsVerificationCode.objects.filter(
        phone=phone,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())

    raw_code = SmsVerificationCode.generate_code()
    expires_at = timezone.now() + timedelta(
        minutes=getattr(settings, 'SMS_CODE_TTL_MINUTES', 5),
    )
    SmsVerificationCode.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=SmsVerificationCode.hash_code(raw_code),
        expires_at=expires_at,
    )
    send_sms_code(phone, raw_code)
    return raw_code


@transaction.atomic
def verify_sms_code(phone, purpose, raw_code):
    """校验验证码，返回 (记录, 错误信息)；校验成功会消耗验证码。"""
    record = SmsVerificationCode.objects.select_for_update().filter(
        phone=phone,
        purpose=purpose,
        used_at__isnull=True,
    ).order_by('-created_at').first()

    if record is None:
        return None, '验证码不存在或已过期，请重新获取。'
    if record.attempts >= getattr(settings, 'SMS_MAX_ATTEMPTS', 5):
        return None, '尝试次数过多，请重新获取验证码。'
    if timezone.now() > record.expires_at:
        return None, '验证码已过期，请重新获取。'

    record.attempts += 1
    if not secrets.compare_digest(record.code_hash, SmsVerificationCode.hash_code(raw_code or '')):
        record.save(update_fields=['attempts'])
        return None, '验证码错误。'

    record.used_at = timezone.now()
    record.save(update_fields=['attempts', 'used_at'])
    return record, None


def send_email_verification_code(email, raw_code):
    _ensure_email_delivery_is_private()
    subject = '你的 Arch_AI 邮箱验证码'
    ttl = getattr(settings, 'EMAIL_CODE_TTL_MINUTES', 5)
    message = (
        f'你的邮箱验证码是：{raw_code}\n\n'
        f'请在 {ttl} 分钟内完成验证。如果这不是你本人操作，请忽略此邮件。'
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=settings.DEBUG,
    )


def create_email_code(email, purpose):
    """为指定邮箱与用途创建一次性验证码，旧未用验证码作废，并发送邮件。"""
    EmailVerificationCode.objects.filter(
        email=email,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())

    raw_code = EmailVerificationCode.generate_code()
    expires_at = timezone.now() + timedelta(
        minutes=getattr(settings, 'EMAIL_CODE_TTL_MINUTES', 5),
    )
    EmailVerificationCode.objects.create(
        email=email,
        purpose=purpose,
        code_hash=EmailVerificationCode.hash_code(raw_code),
        expires_at=expires_at,
    )
    send_email_verification_code(email, raw_code)
    return raw_code


@transaction.atomic
def verify_email_code(email, purpose, raw_code):
    """校验邮箱验证码，返回 (记录, 错误信息)；校验成功会消耗验证码。"""
    record = EmailVerificationCode.objects.select_for_update().filter(
        email=email,
        purpose=purpose,
        used_at__isnull=True,
    ).order_by('-created_at').first()

    if record is None:
        return None, '验证码不存在或已过期，请重新获取。'
    if record.attempts >= getattr(settings, 'EMAIL_CODE_MAX_ATTEMPTS', 5):
        return None, '尝试次数过多，请重新获取验证码。'
    if timezone.now() > record.expires_at:
        return None, '验证码已过期，请重新获取。'

    record.attempts += 1
    if not secrets.compare_digest(record.code_hash, EmailVerificationCode.hash_code(raw_code or '')):
        record.save(update_fields=['attempts'])
        return None, '验证码错误。'

    record.used_at = timezone.now()
    record.save(update_fields=['attempts', 'used_at'])
    return record, None


def create_remember_token(user):
    """为用户创建持久登录令牌，返回明文令牌。"""
    raw_token = RememberToken.generate_raw_token()
    expires_at = timezone.now() + timedelta(
        days=getattr(settings, 'REMEMBER_TOKEN_TTL_DAYS', 30),
    )
    RememberToken.objects.create(
        user=user,
        token_hash=RememberToken.hash_token(raw_token),
        expires_at=expires_at,
    )
    return raw_token


def consume_remember_token(raw_token):
    """校验持久登录令牌并返回用户；无效/过期/已注销返回 None。"""
    record = RememberToken.objects.filter(
        token_hash=RememberToken.hash_token(raw_token or ''),
        revoked_at__isnull=True,
    ).select_related('user').first()
    if record is None or not record.is_valid or not record.user.is_active:
        return None
    record.last_used_at = timezone.now()
    record.save(update_fields=['last_used_at'])
    return record.user


def revoke_remember_token(raw_token):
    """注销指定持久登录令牌。"""
    RememberToken.objects.filter(
        token_hash=RememberToken.hash_token(raw_token or ''),
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
