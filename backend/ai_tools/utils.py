"""Server-side fetch of a supplier/competitor product page's text, used only
as supplementary source material for AI draft generation — see
services.generate_product_draft. Same SSRF hardening as
dashboard.utils.fetch_image_from_url: this fetches an arbitrary
staff-supplied URL server-side, so it validates the resolved IP isn't
private/loopback/link-local, disables redirects, and caps the response size.
"""
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

ALLOWED_SCHEMES = {"http", "https"}
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_TEXT_CHARS = 6000  # keeps the OpenAI prompt bounded regardless of page size


class PageFetchError(Exception):
    """Raised for any invalid/unsafe/failed source URL — callers turn this
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


class _TextExtractor(HTMLParser):
    """Minimal visible-text extractor — good enough for feeding an LLM,
    without pulling in a full HTML parsing dependency like BeautifulSoup."""

    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.chunks.append(text)


def fetch_page_text_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise PageFetchError("Only http/https URLs are supported.")
    if not _is_safe_host(parsed.hostname):
        raise PageFetchError("That URL can't be used as a source.")

    headers = {"User-Agent": "KarivexBot/1.0 (+https://karivex.co.ke; product content research)"}
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=FETCH_TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException:
        raise PageFetchError("Could not fetch that URL.")

    if resp.status_code in (301, 302, 303, 307, 308):
        raise PageFetchError("That URL redirects — please paste the direct page URL instead.")
    if resp.status_code != 200:
        raise PageFetchError(f"That URL returned HTTP {resp.status_code}.")

    content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
    if content_type and not content_type.startswith("text/html") and "xml" not in content_type:
        raise PageFetchError("That URL did not return a web page.")

    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > MAX_PAGE_BYTES:
            break
        chunks.append(chunk)
    html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="ignore")

    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"\s+", " ", " ".join(parser.chunks)).strip()
    if not text:
        raise PageFetchError("Couldn't find any readable text on that page.")
    return text[:MAX_TEXT_CHARS]
