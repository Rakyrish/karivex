"""Server-side fetch for staff-supplied product image URLs. Turning a pasted
URL into a real stored file (same storage/CDN pipeline as an upload — see
AdminProductViewSet._maybe_attach_image_from_url) rather than hotlinking it
keeps images on our own domain/Cloudinary, which is what next/image's
remotePatterns and Google Image Search both expect.

Fetching a staff-supplied URL server-side is a classic SSRF vector (probing
internal services, cloud metadata endpoints, etc.), so this validates the
resolved IP isn't private/loopback/link-local, disables redirects, and caps
the download size — defense-in-depth on top of the IsAdminUser gate.
"""
import ipaddress
import mimetypes
import socket
from urllib.parse import urlparse

import requests
from django.core.files.uploadedfile import SimpleUploadedFile

ALLOWED_SCHEMES = {"http", "https"}
FETCH_TIMEOUT_SECONDS = 10
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


class ImageFetchError(Exception):
    """Raised for any invalid/unsafe/failed image URL — callers turn this
    into a 400 with the message shown directly to staff."""


def _is_safe_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def fetch_image_from_url(url: str) -> SimpleUploadedFile:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise ImageFetchError("Only http/https image URLs are supported.")
    if not _is_safe_host(parsed.hostname):
        raise ImageFetchError("That URL can't be used as an image source.")

    headers = {"User-Agent": "KarivexBot/1.0 (+https://karivex.co.ke; product image import)"}
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=FETCH_TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException:
        raise ImageFetchError("Could not download the image from that URL.")

    if resp.status_code in (301, 302, 303, 307, 308):
        raise ImageFetchError("That URL redirects — please paste the direct image URL instead.")
    if resp.status_code != 200:
        raise ImageFetchError(f"That URL returned HTTP {resp.status_code}.")

    content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
    if not content_type.startswith("image/"):
        raise ImageFetchError("That URL did not return an image.")

    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_IMAGE_BYTES:
        raise ImageFetchError("Image is too large (max 8 MB).")

    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            raise ImageFetchError("Image is too large (max 8 MB).")
        chunks.append(chunk)

    ext = mimetypes.guess_extension(content_type) or ".jpg"
    return SimpleUploadedFile(f"fetched{ext}", b"".join(chunks), content_type=content_type)
