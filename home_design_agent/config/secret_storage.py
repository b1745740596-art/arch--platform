"""Small encrypted-at-rest storage helper for administrator-managed API secrets."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


_PREFIX = 'fernet:v1:'


class SecretDecryptionError(ValueError):
    """Raised when a stored secret cannot be decrypted with this deployment key."""


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    """Encrypt a secret without ever serializing its plaintext into model fields."""
    plaintext = (value or '').strip()
    if not plaintext:
        return ''
    token = _fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')
    return f'{_PREFIX}{token}'


def decrypt_secret(value: str) -> str:
    """Decrypt a value created by :func:`encrypt_secret`."""
    ciphertext = value or ''
    if not ciphertext:
        return ''
    if not ciphertext.startswith(_PREFIX):
        raise SecretDecryptionError('Unsupported encrypted secret format.')
    try:
        return _fernet().decrypt(ciphertext.removeprefix(_PREFIX).encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise SecretDecryptionError('Stored secret cannot be decrypted.') from exc
