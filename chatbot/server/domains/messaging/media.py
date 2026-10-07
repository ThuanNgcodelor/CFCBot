"""Safe media ingress primitives; OCR remains shadow until a provider is approved."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from .config import MessagingConfig
from .contracts import MediaInspectRequest, MediaInspectResponse


def _host_is_private(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        try:
            return any(ipaddress.ip_address(item[4][0]).is_private for item in socket.getaddrinfo(host, None))
        except OSError:
            return True


def inspect_media(req: MediaInspectRequest, config: MessagingConfig) -> MediaInspectResponse:
    if not config.media_enabled:
        return MediaInspectResponse(accepted=False, status="disabled", reason="media_ingest_disabled")
    parsed = urlparse(req.source_url)
    if parsed.scheme != "https" or not parsed.hostname:
        return MediaInspectResponse(accepted=False, status="blocked", reason="https_url_required")
    host = parsed.hostname.lower().rstrip(".")
    if _host_is_private(host):
        return MediaInspectResponse(accepted=False, status="blocked", reason="private_or_loopback_host")
    if config.media_allowed_hosts and host not in config.media_allowed_hosts:
        return MediaInspectResponse(accepted=False, status="blocked", reason="host_not_allowlisted")
    if req.content_length is not None and req.content_length > config.media_max_bytes:
        return MediaInspectResponse(accepted=False, status="blocked", reason="media_too_large")
    if req.media_type != "image":
        return MediaInspectResponse(accepted=True, status="shadow", reason="provider_not_configured")
    if not config.ocr_enabled:
        return MediaInspectResponse(accepted=True, status="shadow", reason="ocr_disabled")
    return MediaInspectResponse(accepted=True, status="shadow", reason="ocr_provider_pending")
