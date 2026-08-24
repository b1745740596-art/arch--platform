"""Explicit CSRF enforcement for anonymous endpoints that establish a session."""

from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.exceptions import PermissionDenied


def enforce_login_csrf(request) -> None:
    """Run Django's CSRF check even though DRF APIView wrappers are csrf_exempt.

    SessionAuthentication enforces CSRF only after authentication. Login endpoints
    are anonymous by definition, so they need this explicit check to prevent a site
    from forcing a visitor into an attacker's account.
    """
    django_request = getattr(request, '_request', request)
    failure = CsrfViewMiddleware(lambda current_request: None).process_view(
        django_request,
        lambda current_request: None,
        (),
        {},
    )
    if failure is not None:
        raise PermissionDenied('CSRF 校验失败，请刷新页面后重试。')
