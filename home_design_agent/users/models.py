import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """用户资料：以 OneToOne 扩展内置 User，避免迁移现有数据到自定义用户模型。"""

    class Locale(models.TextChoices):
        ZH_CN = 'zh-CN', '简体中文'
        EN_US = 'en-US', 'English'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='用户',
    )
    display_name = models.CharField('显示名', max_length=50, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)
    avatar = models.ImageField('头像', upload_to='avatars/', null=True, blank=True)
    bio = models.CharField('个人简介', max_length=200, blank=True)
    locale = models.CharField(
        '语言', max_length=10, choices=Locale.choices, default=Locale.ZH_CN,
    )
    timezone = models.CharField('时区', max_length=50, default='Asia/Shanghai')
    email_verified = models.BooleanField('邮箱已验证', default=False)
    free_credits = models.PositiveIntegerField(
        '免费生成额度', default=5,
        help_text='每位用户一次性赠送的免费生成次数，消耗完毕后开始使用充值额度',
    )
    purchased_credits = models.PositiveIntegerField(
        '充值生成额度', default=0,
        help_text='通过支付套餐购买的生成次数',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '用户资料'
        ordering = ('-created_at',)

    def __str__(self):
        return self.display_name or self.user.get_username()


class PasswordResetToken(models.Model):
    """密码重置令牌：数据库存摘要，不落明文令牌。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        verbose_name='用户',
    )
    token_hash = models.CharField(
        '令牌摘要', max_length=64, unique=True, db_index=True,
    )
    expires_at = models.DateTimeField('过期时间')
    used_at = models.DateTimeField('使用时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '密码重置令牌'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user}@{self.created_at:%Y-%m-%d %H:%M}'

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() <= self.expires_at

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_raw_token():
        return secrets.token_urlsafe(32)


class SmsVerificationCode(models.Model):
    """短信验证码：库内只存 SHA-256 摘要，支持绑定手机与验证码登录两种用途。"""

    class Purpose(models.TextChoices):
        BIND = 'bind', '绑定手机'
        LOGIN = 'login', '验证码登录'

    phone = models.CharField('手机号', max_length=20, db_index=True)
    purpose = models.CharField('用途', max_length=10, choices=Purpose.choices)
    code_hash = models.CharField('验证码摘要', max_length=64)
    expires_at = models.DateTimeField('过期时间')
    attempts = models.PositiveSmallIntegerField('失败次数', default=0)
    used_at = models.DateTimeField('使用时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '短信验证码'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['phone', 'purpose', 'used_at']),
        ]

    def __str__(self):
        return f'{self.phone}@{self.purpose}@{self.created_at:%Y-%m-%d %H:%M}'

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() <= self.expires_at

    @staticmethod
    def hash_code(raw_code):
        return hashlib.sha256(raw_code.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_code():
        length = getattr(settings, 'SMS_CODE_LENGTH', 6)
        upper_bound = 10 ** length
        return str(secrets.randbelow(upper_bound)).zfill(length)


class EmailVerificationCode(models.Model):
    """邮箱验证码：用于邮箱验证、绑定邮箱与验证码登录。"""

    class Purpose(models.TextChoices):
        BIND = 'bind', '绑定邮箱'
        LOGIN = 'login', '验证码登录'

    email = models.EmailField('邮箱', max_length=254, db_index=True)
    purpose = models.CharField('用途', max_length=10, choices=Purpose.choices)
    code_hash = models.CharField('验证码摘要', max_length=64)
    expires_at = models.DateTimeField('过期时间')
    attempts = models.PositiveSmallIntegerField('失败次数', default=0)
    used_at = models.DateTimeField('使用时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '邮箱验证码'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['email', 'purpose', 'used_at']),
        ]

    def __str__(self):
        return f'{self.email}@{self.purpose}@{self.created_at:%Y-%m-%d %H:%M}'

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() <= self.expires_at

    @staticmethod
    def hash_code(raw_code):
        return hashlib.sha256(raw_code.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_code():
        length = getattr(settings, 'EMAIL_CODE_LENGTH', 6)
        upper_bound = 10 ** length
        return str(secrets.randbelow(upper_bound)).zfill(length)


class RememberToken(models.Model):
    """持久登录令牌：客户端关闭后可用令牌恢复 Session 登录。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='remember_tokens',
        verbose_name='用户',
    )
    token_hash = models.CharField(
        '令牌摘要', max_length=64, unique=True, db_index=True,
    )
    expires_at = models.DateTimeField('过期时间')
    last_used_at = models.DateTimeField('最近使用时间', null=True, blank=True)
    revoked_at = models.DateTimeField('注销时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '持久登录令牌'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user}@{self.created_at:%Y-%m-%d %H:%M}'

    @property
    def is_valid(self):
        return self.revoked_at is None and timezone.now() <= self.expires_at

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_raw_token():
        return secrets.token_urlsafe(48)
