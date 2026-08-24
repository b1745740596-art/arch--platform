"""Authenticated, ownership-aware delivery for files stored under MEDIA_ROOT."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views.decorators.http import require_safe

from design.models import (
    Designer,
    DesignScheme,
    Furniture,
    Project,
    RenderJob,
)
from users.models import UserProfile


def _safe_media_path(raw_path: str) -> tuple[str, Path]:
    """Return a canonical storage name and path contained by MEDIA_ROOT."""
    decoded = raw_path or ''
    for _ in range(8):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    else:
        raise Http404

    if not decoded or decoded.startswith('/') or '\\' in decoded or '\x00' in decoded:
        raise Http404
    parts = decoded.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise Http404

    root = Path(settings.MEDIA_ROOT).resolve()
    try:
        candidate = root.joinpath(*parts).resolve()
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        raise Http404
    return '/'.join(parts), candidate


def _can_read_media(user_id: int, storage_name: str) -> bool:
    """Allow owned uploads plus active, authenticated-only catalog media."""
    if storage_name.startswith('designers/') and Designer.objects.filter(
        is_active=True,
        avatar=storage_name,
    ).exists():
        return True
    if storage_name.startswith('furniture/') and Furniture.objects.filter(
        is_active=True,
        image=storage_name,
    ).exists():
        return True
    if UserProfile.objects.filter(user_id=user_id, avatar=storage_name).exists():
        return True
    if (
        Project.objects.filter(user_id=user_id)
        .filter(Q(floorplan=storage_name) | Q(raw_photo=storage_name))
        .exists()
    ):
        return True
    if DesignScheme.objects.filter(
        project__user_id=user_id,
        cover_image=storage_name,
    ).exists():
        return True
    return (
        RenderJob.objects.filter(project__user_id=user_id)
        .filter(Q(raw_photo=storage_name) | Q(result_image=storage_name))
        .exists()
    )


@require_safe
def private_media(request, path: str):
    """Serve a media file only to staff or the user who owns its model record."""
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    storage_name, candidate = _safe_media_path(path)
    if not request.user.is_staff and not _can_read_media(request.user.pk, storage_name):
        # Hide whether another user's file exists.
        raise Http404
    if not candidate.is_file():
        raise Http404

    try:
        handle = candidate.open('rb')
    except OSError:
        raise Http404
    content_type = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
    response = FileResponse(
        handle,
        as_attachment=False,
        filename=candidate.name,
        content_type=content_type,
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_safe
def public_app_download(request):
    """Serve only the fixed Android release artifact, never an app directory."""
    _, candidate = _safe_media_path('app/arch-ai.apk')
    if not candidate.is_file():
        raise Http404
    try:
        handle = candidate.open('rb')
    except OSError:
        raise Http404
    response = FileResponse(
        handle,
        as_attachment=True,
        filename='arch-ai.apk',
        content_type='application/vnd.android.package-archive',
    )
    response['Cache-Control'] = 'public, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
