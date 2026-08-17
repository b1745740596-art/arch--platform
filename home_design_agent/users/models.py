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
