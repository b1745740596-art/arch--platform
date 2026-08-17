from django.contrib import admin

from .models import PasswordResetToken, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'phone', 'locale', 'email_verified', 'updated_at')
    list_filter = ('locale', 'email_verified')
    search_fields = ('user__username', 'user__email', 'display_name', 'phone')
    raw_id_fields = ('user',)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'expires_at', 'used_at', 'created_at')
    list_filter = ('used_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('token_hash', 'expires_at', 'used_at', 'created_at')
