"""Shared DRF throttles for authentication, generation, and sales endpoints."""

from __future__ import annotations

import hashlib
import re

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class _IPThrottle(SimpleRateThrottle):
    """Rate-limit every caller by the proxy-aware DRF client identifier."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


class _TargetThrottle(SimpleRateThrottle):
    """Rate-limit a normalized, hashed phone/email/token without caching PII."""

    target_fields = ('phone', 'email', 'username', 'token')

    def get_cache_key(self, request, view):
        data = getattr(request, 'data', {}) or {}
        field, target = next(
            ((name, data.get(name)) for name in self.target_fields if data.get(name)),
            ('', ''),
        )
        target = str(target).strip().lower()
        if field == 'phone':
            target = re.sub(r'\D', '', target)
        elif field in ('email', 'username'):
            target = ''.join(target.split())
        if not target:
            return None
        digest = hashlib.sha256(target.encode('utf-8')).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': digest}


class AuthRegisterIPThrottle(_IPThrottle):
    scope = 'auth_register_ip'


class AuthLoginIPThrottle(_IPThrottle):
    scope = 'auth_login_ip'


class AuthLoginTargetThrottle(_TargetThrottle):
    scope = 'auth_login_target'


class VerificationIPThrottle(_IPThrottle):
    scope = 'auth_verification_ip'


class VerificationTargetThrottle(_TargetThrottle):
    scope = 'auth_verification_target'


class PasswordResetIPThrottle(_IPThrottle):
    scope = 'auth_password_reset_ip'


class PasswordResetTargetThrottle(_TargetThrottle):
    scope = 'auth_password_reset_target'


class DesignRenderUserThrottle(UserRateThrottle):
    scope = 'design_render_user'


class DesignRenderIPThrottle(_IPThrottle):
    scope = 'design_render_ip'


class DesignSalesUserThrottle(UserRateThrottle):
    scope = 'design_sales_user'


class DesignSalesIPThrottle(_IPThrottle):
    scope = 'design_sales_ip'
