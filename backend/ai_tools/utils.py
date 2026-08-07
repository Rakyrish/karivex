"""Server-side fetch of a supplier/competitor product page's text, used only
as supplementary source material for AI draft generation — see
services.generate_product_draft. Same SSRF hardening as
dashboard.utils.fetch_image_from_url: this fetches an arbitrary
staff-supplied URL server-side, so it validates the resolved IP isn't
private/loopback/link-local, disables redirects, and caps the response size.
"""
import base64
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_TEXT_CHARS = 6000  # keeps the OpenAI prompt bounded regardless of page size
MAX_IMAGE_CANDIDATES = 12  # enough for staff to pick the right product photo
VISION_MAX_EDGE = 1024  # px; vision billing scales with pixels, detail past this adds nothing


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
    without pulling in a full HTML parsing dependency like BeautifulSoup.
    Also collects the page's own og:image/title metadata and any <img>
    candidates, so the same single fetch can supply the product photo
    instead of forcing a second round trip."""

    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "nav", "footer", "header"}
    # Boilerplate that is never the product photo, matched against the URL.
    _IMG_DENY = re.compile(r"(logo|icon|sprite|placeholder|avatar|banner|badge|pixel|spacer)", re.I)

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []
        self.og_image: str = ""
        self.og_title: str = ""
        self.img_candidates: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            content = (a.get("content") or "").strip()
            if content and key in ("og:image", "og:image:secure_url", "twitter:image") and not self.og_image:
                self.og_image = content
            elif content and key in ("og:title", "twitter:title") and not self.og_title:
                self.og_title = content
        elif tag == "img":
            src = (a.get("src") or a.get("data-src") or "").strip()
            if src and not src.startswith("data:") and not self._IMG_DENY.search(src):
                self.img_candidates.append(src)

    def handle_startendtag(self, tag, attrs):
        # <meta …/> and <img …/> are void elements; HTMLParser routes the
        # self-closing form here instead of handle_starttag.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.chunks.append(text)


@dataclass
class PageContent:
    """Everything one fetch of a source page yields for product drafting.

    `is_image` distinguishes the two things staff legitimately paste: a
    product *page* (prose + an og:image) and a direct link to a product
    *photo* (no prose at all, vision does the work).
    """
    text: str
    title: str = ""
    image_url: str = ""
    image_candidates: list[str] = field(default_factory=list)
    is_image: bool = False


def to_vision_data_uri(raw: bytes, content_type: str) -> str:
    """Base64 data URI for the OpenAI vision API, downscaled first.

    Sending the original file would work but is wasteful: vision billing
    scales with pixel count, and a 4000px product photo costs several times
    a 1024px one while telling the model nothing extra about a drum of
    caustic soda. Falls back to the untouched bytes if Pillow can't read the
    format.
    """
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(raw))
        img.load()
        if max(img.size) > VISION_MAX_EDGE:
            img.thumbnail((VISION_MAX_EDGE, VISION_MAX_EDGE))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        raw, content_type = buf.getvalue(), "image/jpeg"
    except Exception:
        logger.warning("Could not downscale image for vision; sending as-is", exc_info=True)
    return f"data:{content_type};base64,{base64.b64encode(raw).decode()}"


def fetch_page_text_from_url(url: str) -> str:
    """Text-only view of fetch_page_content_from_url, kept for callers that
    only ever needed the prose (see ai_tools.views / the existing
    source_url grounding path)."""
    return fetch_page_content_from_url(url).text


def fetch_page_content_from_url(url: str) -> PageContent:
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
    if content_type.startswith("image/"):
        # Staff pasted a direct link to a product photo rather than a page.
        # There's no prose to mine, so hand back an image-only source and let
        # vision carry the extraction.
        resp.close()
        return PageContent(text="", image_url=url, image_candidates=[url], is_image=True)
    if content_type and not content_type.startswith("text/html") and "xml" not in content_type:
        raise PageFetchError("That URL is neither a web page nor an image.")

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

    # Relative srcs are common; resolve against the page URL so the caller
    # always gets something directly fetchable.
    candidates = [urljoin(url, src) for src in parser.img_candidates[:MAX_IMAGE_CANDIDATES]]
    primary = urljoin(url, parser.og_image) if parser.og_image else (candidates[0] if candidates else "")

    return PageContent(
        text=text[:MAX_TEXT_CHARS],
        title=parser.og_title.strip(),
        image_url=primary,
        image_candidates=candidates,
    )
