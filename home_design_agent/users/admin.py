from django.contrib import admin

from .models import (
    EmailVerificationCode,
    PasswordResetToken,
    RememberToken,
    SmsVerificationCode,
    UserProfile,
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
