"""Validation shared by external AI provider configuration entry points."""

from urllib.parse import urlparse


def is_safe_https_endpoint(value: str) -> bool:
    endpoint = urlparse(value or '')
    return (
        endpoint.scheme == 'https'
        and bool(endpoint.hostname)
        and not endpoint.username
        and not endpoint.password
        and not endpoint.query
        and not endpoint.fragment
    )
