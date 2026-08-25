from django.contrib import admin

from .models import (
    EmailVerificationCode,
    PasswordResetToken,
    RememberToken,
    SmsVerificationCode,
    UserProfile,
    VerificationConfig,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'display_name', 'phone', 'locale', 'email_verified',
        'free_credits', 'purchased_credits', 'updated_at',
    )
    list_filter = ('locale', 'email_verified')
    search_fields = ('user__username', 'user__email', 'display_name', 'phone')
    raw_id_fields = ('user',)


@admin.register(VerificationConfig)
class VerificationConfigAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 'phone_verification_enabled', 'email_verification_enabled',
        'require_phone_verification_for_order', 'require_email_verification_for_order',
        'updated_at',
    )
    fieldsets = (
        ('验证功能开关', {
            'fields': ('phone_verification_enabled', 'email_verification_enabled'),
            'description': '关闭后，对应验证码接口会拒绝请求，前端绑定和验证码登录入口也会隐藏。',
        }),
        ('下单验证要求', {
            'fields': (
                'require_phone_verification_for_order',
                'require_email_verification_for_order',
            ),
            'description': '当前两项默认关闭，因此下单无需手机号或邮箱验证；可按需独立开启。',
        }),
        ('基础', {'fields': ('name',)}),
    )

    def has_add_permission(self, request):
        return not VerificationConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'expires_at', 'used_at', 'created_at')
    list_filter = ('used_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('token_hash', 'expires_at', 'used_at', 'created_at')


@admin.register(SmsVerificationCode)
class SmsVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('phone', 'purpose', 'attempts', 'expires_at', 'used_at', 'created_at')
    list_filter = ('purpose', 'used_at')
    search_fields = ('phone',)
    readonly_fields = ('code_hash', 'expires_at', 'attempts', 'used_at', 'created_at')


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('email', 'purpose', 'attempts', 'expires_at', 'used_at', 'created_at')
    list_filter = ('purpose', 'used_at')
    search_fields = ('email',)
    readonly_fields = ('code_hash', 'expires_at', 'attempts', 'used_at', 'created_at')


@admin.register(RememberToken)
class RememberTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'expires_at', 'last_used_at', 'revoked_at', 'created_at')
    list_filter = ('revoked_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('token_hash', 'expires_at', 'last_used_at', 'revoked_at', 'created_at')
