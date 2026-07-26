"""OpenAI-backed content drafting and chat. Every AI output here is either a
DRAFT that a human must review before it reaches a public page (product
content), or explicitly scoped and guarded (the chatbot) — this mirrors the
"unique, human-reviewed, never templated" rule baked into catalog/models.py.
"""
import base64
import json
import logging
import mimetypes
import re

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)

_client = None


class AIConfigError(Exception):
    """Raised when OPENAI_API_KEY is unset — callers turn this into a 503."""


def get_client():
    global _client
    if not settings.OPENAI_API_KEY:
        raise AIConfigError("OPENAI_API_KEY is not configured.")
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _image_data_uri(product, image_url_override: str | None):
    """Prefer an explicit staff-supplied URL; otherwise base64-embed the
    product's own image so this works even when MEDIA isn't publicly
    reachable (e.g. local dev, or before Cloudinary/CDN migration)."""
    if image_url_override:
        return image_url_override
    if not product.image:
        return None
    try:
        with product.image.open("rb") as f:
            raw = f.read()
        mime = mimetypes.guess_type(product.image.name)[0] or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    except Exception:
        logger.warning("Could not read image for product %s", product.pk, exc_info=True)
        return None


DRAFT_SCHEMA_HINT = (
    '{"description": "450-650 words, unique prose, 4-6 paragraphs separated by \\n\\n — '
    'cover what it is, specs/grade, how it\'s used, why buyers choose this supplier '
    '(regions/packaging/COA), thorough enough to compete with the longest-form '
    'competitor product pages, not a short blurb", '
    '"meta_title": "<=60 characters, include the product name and \'Kenya\' or the '
    'primary region if it fits", '
    '"meta_description": "<=155 characters, include a concrete buyer-facing detail '
    '(purity/packaging/delivery) plus a call to action", '
    '"applications": "4-8 specific applications, one per line", '
    '"safety_info": "3-5 sentences of general handling guidance, always ending by '
    'pointing the buyer to the MSDS/COA supplied with their order", '
    '"faqs": [{"q": "...", "a": "..."}] (5-7 items covering the questions a real buyer '
    'would search for — pricing/MOQ, purity, packaging options, delivery regions, storage), '
    '"image_alt": "<=140 characters, descriptive"}'
)

DRAFT_SYSTEM_PROMPT = (
    "You are a technical copywriter for Karivex Solutions Ltd, an industrial "
    "chemical supplier in East Africa, writing to compete with established "
    "competitors whose product pages run long and detailed. Draft ORIGINAL, "
    "specific, human-quality, comprehensive product content from the facts "
    "given — never generic manufacturer boilerplate, never invented "
    "certifications, regulatory codes, or safety claims you cannot support "
    "from the given facts. Depth and specificity matter for search ranking, "
    "but every added sentence must still be grounded in the given facts — "
    "pad with buyer-relevant framing (use cases, sourcing/delivery, handling "
    "context), never with invented technical claims. For safety_info, restate "
    "only well-established general handling practice for this class of "
    "chemical, and always close by directing the buyer to the MSDS/COA "
    "supplied with their order — never invent specific hazard codes. "
    "If a staff-provided target search phrase is given, work it naturally "
    "into the description and meta fields without keyword-stuffing. "
    "Respond with strict JSON only, no markdown fences."
)


def generate_product_draft(
    product, image_url: str | None = None, notes: str = "", source_text: str | None = None
) -> dict:
    client = get_client()

    facts = [
        f"Product name: {product.name}",
        f"Category: {product.category.name}",
        f"Grade: {product.get_grade_display()}",
    ]
    if product.cas_number:
        facts.append(f"CAS number: {product.cas_number}")
    if product.synonyms:
        facts.append(f"Synonyms: {product.synonyms}")
    if product.purity:
        facts.append(f"Purity: {product.purity}")
    if product.packaging:
        facts.append(f"Packaging: {product.packaging}")
    if product.appearance:
        facts.append(f"Appearance: {product.appearance}")
    facts.append(f"Regions served: {product.regions}")
    if product.description:
        facts.append(f"Existing description (rewrite/improve, keep it unique — do not copy verbatim): {product.description}")
    if notes:
        facts.append(f"Staff notes: {notes}")
    if source_text:
        facts.append(
            "Reference material fetched from a staff-supplied source page (a "
            "supplier spec sheet or competitor listing). Use it only to "
            "ground facts already implied above — extract useful specifics, "
            "rewrite entirely in your own words, never copy sentences "
            "verbatim, and never adopt claims that contradict the facts "
            "given elsewhere: " + source_text
        )

    user_content: list = [
        {"type": "text", "text": "\n".join(facts) + "\n\nRespond with JSON matching this shape: " + DRAFT_SCHEMA_HINT}
    ]
    image_payload = _image_data_uri(product, image_url)
    if image_payload:
        user_content.append({"type": "image_url", "image_url": {"url": image_payload}})

    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
        max_tokens=2200,  # bumped alongside DRAFT_SCHEMA_HINT's 450-650 word target
    )
    data = json.loads(response.choices[0].message.content)
    return _clean_draft(data)


def _clean_draft(data: dict) -> dict:
    faqs = [
        {"q": str(f.get("q", ""))[:300], "a": str(f.get("a", ""))[:1000]}
        for f in data.get("faqs", []) if isinstance(f, dict) and f.get("q") and f.get("a")
    ][:7]
    return {
        "description": str(data.get("description", ""))[:5000],
        "meta_title": str(data.get("meta_title", ""))[:70],
        "meta_description": str(data.get("meta_description", ""))[:160],
        "applications": str(data.get("applications", ""))[:2000],
        "safety_info": str(data.get("safety_info", ""))[:2000],
        "faqs": faqs,
        "image_alt": str(data.get("image_alt", ""))[:160],
    }


def suggest_internal_links(product, limit: int = 5) -> list[dict]:
    """Deterministic, DB-driven — no OpenAI call. Related content is a factual
    query (same category, shared references), not something worth risking a
    hallucinated URL over."""
    from catalog.models import BlogPost, Product

    related_products = list(
        Product.objects.filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by("-featured", "-updated_at")[:limit]
    )
    suggestions = [
        {"type": "product", "slug": p.slug, "title": p.name, "reason": f"Same category — {product.category.name}"}
        for p in related_products
    ]
    remaining = max(0, limit - len(suggestions))
    if remaining:
        posts = (
            BlogPost.objects.filter(published=True)
            .filter(Q(related_products=product) | Q(title__icontains=product.category.name))
            .distinct()[:remaining]
        )
        suggestions += [
            {"type": "post", "slug": p.slug, "title": p.title, "reason": "Related buyer's guide"}
            for p in posts
        ]
    return suggestions


CHAT_SYSTEM_TEMPLATE = """You are the website assistant for {name} ({tagline}), an \
industrial chemical supplier operating in {regions}.

Company facts (use these, do not invent others):
- Phone / WhatsApp: {phone}
- Email: {email}
- Hours: {hours}
- Delivery: {delivery_nairobi}; {delivery_regional}
- Certifications: {certifications}

You answer ONLY using the company facts above and the product/guide context \
provided in each message. If a question needs information not present in that \
context (exact pricing not shown, stock levels, order status, or ANY chemical \
safety/handling/dosage/mixing question beyond a product's stated safety_info), \
say you don't have that on hand and direct the buyer to call/WhatsApp {phone}, \
email {email}, or request a quote — never improvise safety or handling advice. \
Never invent a product, price, or certification that isn't in the given context. \
Keep answers short and concrete. Respond with strict JSON only: \
{{"answer": "...", "sources": [{{"type": "product|post", "slug": "...", "title": "..."}}]}}\
 listing only items you actually referenced."""


def _search_context(message: str, limit_products: int = 5, limit_posts: int = 3):
    from catalog.models import BlogPost, Product

    words = [w for w in re.split(r"\W+", message.lower()) if len(w) > 2][:8]
    if not words:
        return [], []

    pq = Q()
    for w in words:
        pq |= Q(name__icontains=w) | Q(description__icontains=w) | Q(applications__icontains=w) | Q(category__name__icontains=w)
    products = list(Product.objects.filter(pq).select_related("category").distinct()[:limit_products])

    bq = Q()
    for w in words:
        bq |= Q(title__icontains=w) | Q(excerpt__icontains=w)
    posts = list(BlogPost.objects.filter(bq, published=True).distinct()[:limit_posts])

    return products, posts


def answer_chat(message: str, history: list[dict] | None = None) -> dict:
    client = get_client()
    site = settings.SITE

    products, posts = _search_context(message)
    context_lines = []
    for p in products:
        faqs = "; ".join(f"{f.get('q')} -> {f.get('a')}" for f in (p.faqs or [])[:3])
        context_lines.append(
            f"[product] {p.name} (/products/{p.slug}) — {p.purity or ''} {p.packaging or ''}. "
            f"{'Quote only' if not p.is_small_pack else f'From KES {p.price_kes}'}. "
            f"Safety: {p.safety_info[:200] if p.safety_info else 'see MSDS'}. FAQs: {faqs or 'none'}"
        )
    for post in posts:
        context_lines.append(f"[guide] {post.title} (/blog/{post.slug}) — {post.excerpt}")
    context_block = "\n".join(context_lines) if context_lines else "No matching products or guides found for this question."

    system_prompt = CHAT_SYSTEM_TEMPLATE.format(
        name=site["name"], tagline=site["tagline"], regions=", ".join(site["regions"]),
        phone=site["phone"], email=site["email"], hours=site["hours"],
        delivery_nairobi=site["delivery_nairobi"], delivery_regional=site["delivery_regional"],
        certifications=site["certifications"],
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:2000]})
    messages.append({"role": "user", "content": f"Context:\n{context_block}\n\nQuestion: {message[:2000]}"})

    response = client.chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=600,
    )
    data = json.loads(response.choices[0].message.content)
    sources = [
        s for s in data.get("sources", [])
        if isinstance(s, dict) and s.get("type") in ("product", "post") and s.get("slug")
    ][:5]
    return {"answer": str(data.get("answer", ""))[:2000], "sources": sources}
