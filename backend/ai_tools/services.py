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
from django.utils import timezone

from . import content_schema, keywords as kw_engine, validation
from .content_schema import NEEDS_VERIFICATION

logger = logging.getLogger(__name__)

_client = None


class AIConfigError(Exception):
    """Raised when OPENAI_API_KEY is unset — callers turn this into a 503."""


class AIUnidentifiedError(Exception):
    """The model looked at the source and could not say what the product is.

    Reached mainly via image-only drafting when the photo is a molecular
    diagram, a stock close-up, or an unreadable label. The model signals this
    by returning a placeholder name ("unknown") and abandoning the content
    fields; prompt-level insistence on a best guess does not reliably
    override it, so this is caught in code and turned into a clear
    instruction to staff instead of a half-filled form."""


# What models return in place of a real product name when they give up.
UNIDENTIFIED_NAMES = {
    "", "unknown", "unknown product", "unidentified", "unidentified product",
    "n/a", "na", "none", "not identified", "not applicable", "chemical product",
}


class AIRefusalError(Exception):
    """The model declined to answer (or returned an empty body). Distinct
    from a transient API failure: retrying the identical request will
    usually refuse again, so callers surface this to staff as an actionable
    message rather than a generic 'try again shortly'."""


def _message_json(response) -> dict:
    """Parse a chat completion's JSON body, treating a refusal or empty
    content as a first-class outcome. Both are reachable in normal use —
    safety-tuned models refuse some legitimate chemical-supply pages — and
    json.loads(None) would otherwise raise an opaque TypeError."""
    choice = response.choices[0]
    refusal = getattr(choice.message, "refusal", None)
    if refusal:
        raise AIRefusalError(str(refusal))
    content = choice.message.content
    if not content:
        if choice.finish_reason == "length":
            raise AIRefusalError(
                "The response was cut off before it was complete. Try again, "
                "or use a shorter source page."
            )
        raise AIRefusalError("The AI returned an empty response.")
    return json.loads(content)


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
    'competitor product pages, not a short blurb. The FIRST SENTENCE must contain '
    'the target search phrase and name the country/region — do not open with a '
    'definition of the chemical in the abstract", '
    # "if it fits" was an escape hatch the model took on 44% of the catalogue,
    # shipping titles like "High-Quality Acetic Acid for Water Treatment" for
    # the keyword "acetic acid kenya" — no geo term at all. Made mandatory.
    '"meta_title": "<=60 characters. MUST contain the product name AND the '
    'country/region (\'Kenya\' or \'East Africa\'). Lead with the product name. '
    'Do NOT open with or include filler adjectives (High-Quality, Premium, Top, '
    'Best, Superior, Leading) — those characters are needed for the keyword", '
    '"meta_description": "<=155 characters. MUST start with the product name — '
    'never with a verb such as Discover/Explore/Buy/Unlock/Elevate/Order. '
    'Include the country/region plus one concrete buyer-facing detail '
    '(purity/packaging/delivery), then a short call to action", '
    '"applications": "4-8 specific applications, one per line", '
    '"safety_info": "3-5 sentences of general handling guidance, always ending by '
    'pointing the buyer to the MSDS/COA supplied with their order", '
    '"faqs": [{"q": "...", "a": "..."}] (5-7 items covering the questions a real buyer '
    'would search for — pricing/MOQ, purity, packaging options, delivery regions, storage), '
    '"image_alt": "<=140 characters, descriptive"}'
)

DRAFT_SYSTEM_PROMPT = (
    "You are a technical copywriter and SEO strategist for Karivex Solutions "
    "Ltd, an industrial chemical supplier in East Africa. Your content must "
    "win the top Google result for the products it covers — earned the only "
    "legitimate way: greater depth, more specific buyer-relevant detail, and "
    "tighter on-page SEO than rival listings, never by copying another "
    "supplier's page or naming/disparaging anyone. Draft ORIGINAL, specific, "
    "human-quality, comprehensive product content from the facts given — "
    "never generic manufacturer boilerplate, never invented certifications, "
    "regulatory codes, or safety claims you cannot support from the given "
    "facts. Depth and specificity matter for search ranking, but every added "
    "sentence must still be grounded in the given facts — pad with "
    "buyer-relevant framing (use cases, sourcing/delivery, handling "
    "context), never with invented technical claims. For safety_info, restate "
    "only well-established general handling practice for this class of "
    "chemical, and always close by directing the buyer to the MSDS/COA "
    "supplied with their order — never invent specific hazard codes. "
    "If a staff-provided target search phrase is given, its WORDS must appear "
    "in the meta_title and meta_description, and the product name and the "
    "country/region must both appear in the first sentence of the "
    "description. Do NOT paste the search phrase verbatim into prose: a "
    "phrase like 'acetic acid kenya' is a search query, not English, and "
    "splicing it in produces text like 'used in regions such as acetic acid "
    "Kenya' — which reads as spam to a buyer and as keyword stuffing to "
    "Google. Write 'acetic acid supplied across Kenya' instead. Once is "
    "enough; never repeat the phrase or stuff variations of it. Make "
    "sure the FAQs cover the exact questions a comparison-shopping buyer "
    "searches for (pricing/MOQ, purity, packaging, delivery speed to their "
    "region). "
    # Measured across the 148-product catalogue this prompt produced: 74% of
    # meta descriptions opened with the single word "Discover", and the
    # connectives below appeared in 40-62% of descriptions each. Uniform
    # openings read as machine-written, waste the highest-value pixels in the
    # SERP snippet, and make 148 pages look like one template.
    "WRITE LIKE A HUMAN SPECIALIST, NOT A CONTENT MILL. Never open a "
    "meta_description with Discover, Explore, Unlock, Elevate or Introducing. "
    "Never use the connectives Furthermore, Moreover, Additionally, "
    "In addition, It is important to note, or It is worth noting. Vary "
    "sentence openings — do not start consecutive paragraphs with the same "
    "construction. Prefer concrete nouns and figures over adjectives: write "
    "'supplied in 25 kg bags from our Nairobi warehouse', not 'premium "
    "quality product with excellent characteristics'. "
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
    data = _message_json(response)
    return _clean_draft(data, product.name, product.focus_keyword)


EXTRACT_SCHEMA_HINT = (
    '{"name": "the product\'s common commercial name only, e.g. \'Caustic Soda Flakes\' — '
    'strip any supplier/brand name, pack size or marketing words", '
    '"category": "EXACTLY one of the allowed category names given below — pick the best fit", '
    '"grade": "one of: industrial, food, lab, pharma, cosmetic", '
    '"cas_number": "CAS registry number if stated on the page, else empty string", '
    '"synonyms": "comma-separated alternative names if stated, else empty string", '
    '"purity": "e.g. \'>=98%\' if stated, else empty string", '
    '"appearance": "e.g. \'white crystalline flakes\' if stated or clearly visible, else empty string", '
    '"packaging": "e.g. \'25 kg bags\' if stated, else empty string", '
    '"focus_keyword": "the single search phrase this page should rank for in Kenya/East Africa, '
    'e.g. \'caustic soda flakes kenya\' — lowercase, 2-5 words, include the region", '
    '"confidence": "high | medium | low — how confident you are the extracted facts are correct", '
    # This path invents the focus_keyword and then previously said nothing
    # about using it, so only 56% of generated meta_titles contained all of
    # its words. The keyword is worthless if the two fields Google weighs
    # most do not carry it.
    '"description": "450-650 words, unique prose, 4-6 paragraphs separated by \\n\\n. '
    'The first sentence must contain the focus_keyword and name the region", '
    '"meta_title": "<=60 characters, MUST contain the focus_keyword\'s words '
    '(product name + region). Lead with the product name. No filler adjectives '
    '(High-Quality, Premium, Best, Superior)", '
    '"meta_description": "<=155 characters, MUST contain the focus_keyword\'s '
    'words. MUST start with the product name, never with a verb such as '
    'Discover/Explore/Buy/Unlock", '
    '"applications": "4-8 specific applications, one per line", '
    '"safety_info": "3-5 sentences ending by pointing the buyer to the MSDS/COA supplied with their order", '
    '"faqs": [{"q": "...", "a": "..."}] (5-7 items), '
    '"image_alt": "<=140 characters, descriptive"}'
)

EXTRACT_SYSTEM_PROMPT = (
    DRAFT_SYSTEM_PROMPT
    + " In this task you are ALSO extracting the product's factual "
    "attributes from whatever source staff supplied — a supplier page, a "
    "photograph of the product, or just its name. Extract only what that "
    "source actually supports: never guess a CAS number, purity or packaging "
    "that isn't stated or plainly visible; return an empty string instead. "
    "The extracted facts are shown to staff for correction before anything "
    "is saved, so accuracy matters more than completeness. The prose you "
    "write must be entirely your own words about the underlying chemical — "
    "never reuse the source page's sentences, headings or marketing claims, "
    "and never mention, name, or compare against the source supplier."
)


# The on-page checklist scores <400 words as a warning and <250 as a failure,
# so this is the bar the draft has to clear to publish "green".
MIN_DESCRIPTION_WORDS = 450
TARGET_DESCRIPTION_WORDS = 550

EXPAND_SYSTEM_PROMPT = (
    "You are the same technical copywriter expanding your own draft product "
    "description to full length for search-engine competitiveness. Keep the "
    "existing voice, facts and structure — do NOT restate the draft in "
    "different words, and do NOT introduce any technical claim, "
    "certification, hazard code or specification that isn't already present "
    "in the draft or the facts given. Add genuine buyer-relevant substance: "
    "concrete use cases and the industries behind them, how the material "
    "behaves in those applications, the specification and ordering decisions a "
    "buyer faces, packaging/handling/storage context, and sourcing and "
    "delivery framing. "
    # The previous wording of that clause was "what to consider when
    # specifying or ordering it" — the model echoed it back near-verbatim and
    # the phrase "When specifying or" ended up in 92 of 148 descriptions
    # (62%). Prompt wording leaks into output, so describe the topic to cover
    # rather than handing over a phrase that can be copied.
    "Do not reuse any wording from these instructions in the prose. "
    "Never use the connectives Furthermore, Moreover, Additionally, "
    "In addition, It is important to note, or It is worth noting, and do not "
    "begin more than one paragraph with the same construction. "
    "Return 4-7 paragraphs separated by blank lines. "
    'Respond with strict JSON only: {"description": "..."}'
)


# Phrases that mark text as machine-written. Measured across the 148-product
# catalogue drafted under the old prompts: "When specifying or" in 92 (62%),
# "Furthermore" in 77 (52%), "Moreover" in 59 (40%). The first of those was
# echoed straight out of EXPAND_SYSTEM_PROMPT's own wording.
BANNED_PROSE_PHRASES = (
    "when specifying or",
    "furthermore",
    "moreover",
    "additionally,",
    "in addition,",
    "it is important to note",
    "it is worth noting",
    "in conclusion",
    "in today's world",
)


def has_banned_prose(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in BANNED_PROSE_PHRASES)


# Discourse markers carry no information: "Furthermore, X" and "X" state the
# same fact. That is exactly why they can be removed mechanically without any
# risk of losing a specification — and mechanically is the only reliable way,
# because the model reproduces them even when the prompt forbids them by name
# (measured: every restyle attempt on the first two products came back still
# carrying "Additionally,").
_CONNECTIVE = r"(?:Furthermore|Moreover|Additionally|In addition|In conclusion|Notably|Importantly)"
_STRIPPERS = (
    # Marker followed by a lowercase word — drop it and lift the word's case.
    (re.compile(rf"\b{_CONNECTIVE}\s*,\s*([a-z])"), lambda m: m.group(1).upper()),
    # Marker followed by anything else (a proper noun, a figure) — just drop it.
    (re.compile(rf"\b{_CONNECTIVE}\s*,\s*"), ""),
    (re.compile(r"\bIt is (?:important to note|worth noting) that\s+([a-z])"),
     lambda m: m.group(1).upper()),
    (re.compile(r"\bIt is (?:important to note|worth noting) that\s+"), ""),
    # The phrase echoed straight out of the old EXPAND_SYSTEM_PROMPT.
    (re.compile(r"\bWhen specifying or ordering\b", re.I), "When ordering"),
    (re.compile(r"\bwhen specifying or ordering\b"), "when ordering"),
)


def strip_banned_connectives(text: str) -> str:
    """Remove formulaic discourse markers without touching any claim."""
    out = text or ""
    for pattern, repl in _STRIPPERS:
        out = pattern.sub(repl, out)
    # Removing a leading marker can leave a doubled space or an orphaned one
    # before punctuation.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([,.;:])", r"\1", out)
    return out.strip()


RESTYLE_SYSTEM_PROMPT = (
    "You are a technical copywriter revising a product description that reads "
    "as machine-written. This is a STYLE edit, not a rewrite of substance. "
    "Preserve every factual claim exactly: product names, CAS numbers, "
    "purity figures, packaging sizes, grades, applications, regions and "
    "delivery terms must all survive unchanged. Do NOT add any specification, "
    "certification, hazard code, percentage or claim that is not already in "
    "the text you are given — you have no source to verify additions against. "
    "Do NOT remove information: the revised text must be within about 10% of "
    "the original word count, never shorter than the minimum given below. "
    "What to change: replace formulaic connectives and uniform sentence "
    "openings with plain, varied, specific prose an industry specialist would "
    "write. Never use the words or phrases Furthermore, Moreover, "
    "Additionally, In addition, It is important to note, It is worth noting, "
    "In conclusion, or the construction 'When specifying or ordering'. Do not "
    "begin more than one paragraph with the same construction. Prefer "
    "concrete nouns and figures over adjectives. Keep the existing paragraph "
    "count and the blank-line separation between paragraphs. "
    'Respond with strict JSON only: {"description": "..."}'
)


# Quantities are the load-bearing facts in a chemical listing: pack size,
# purity, concentration. A style pass has no business touching them, but
# "preserve every factual claim" in the system prompt was not enough on its
# own — the first full run dropped a figure from 92 of 148 descriptions,
# usually by deleting the whole sentence that carried it. Word count and
# banned-phrase checks both passed, because neither was looking at this.
_NUMERIC_FACT = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kg|g\b|mg|t\b|tonnes?|L\b|l\b|ml|litres?|liters?|%|ppm|mm|cm|°c)",
    re.I,
)


def numeric_facts(text: str) -> set[str]:
    """Quantities mentioned in the text, normalised for comparison."""
    return {re.sub(r"\s+", "", m).lower() for m in _NUMERIC_FACT.findall(text or "")}


def restyle_description(description: str, focus_keyword: str = "", min_words: int = 0) -> str:
    """Rewrite a description's voice while holding its facts fixed.

    Used to retire the templated phrasing left by the earlier prompts. Returns
    the original text unchanged if the model gives back something empty, too
    short, or still carrying the banned phrasing — a failed restyle must never
    be able to shorten a page or make it worse than it already is.
    """
    client = get_client()
    original_words = len(description.split())
    floor = max(min_words, int(original_words * 0.9))
    ask = (
        f"Revise the description below. Keep at least {floor} words "
        f"(the original has {original_words}).\n\n{description}"
    )
    if focus_keyword:
        # Requiring the verbatim phrase is what produced openings like "used
        # in regions such as acetic acid Kenya" in 58 of the 148 live
        # descriptions. Ask for the components, and explicitly repair the
        # splices already in the text.
        ask += (
            f"\n\nThis page targets the search query \"{focus_keyword}\". That "
            "is a query, not English — do NOT paste it in verbatim. The "
            "product name and the country/region must both appear naturally "
            "in the opening paragraph. If the text you are given already "
            "splices the query in awkwardly (for example 'in regions such as "
            "acetic acid Kenya'), rewrite that clause into plain English "
            "which still names the product and the country."
        )
    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": RESTYLE_SYSTEM_PROMPT},
            {"role": "user", "content": ask},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=2400,
    )
    data = _message_json(response)
    revised = str(data.get("description", "")).strip()
    if not revised:
        # No usable output — still strip the markers from what we already have
        # so the call is never a total loss.
        return strip_banned_connectives(description)
    if len(revised.split()) < floor * 0.95:
        logger.warning(
            "restyle came back short (%d words vs floor %d) — keeping original",
            len(revised.split()), floor,
        )
        return strip_banned_connectives(description)
    # The model varies the sentence openings; this guarantees the markers are
    # gone whether or not it obeyed. Rejecting the whole rewrite over a stray
    # "Additionally," would throw away the part it did well.
    revised = strip_banned_connectives(revised)
    if has_banned_prose(revised):
        logger.warning("restyle still contains banned phrasing after strip — keeping original")
        return strip_banned_connectives(description)
    dropped = numeric_facts(description) - numeric_facts(revised)
    if dropped:
        # Losing "25 kg" or ">=99%" makes the page less useful to a buyer and
        # less specific to Google. Fall back to the deterministic strip, which
        # removes the templated phrasing without rewriting a single claim.
        logger.warning("restyle dropped quantities %s — keeping original", sorted(dropped))
        return strip_banned_connectives(description)
    return revised


def _expand_description(description: str, facts: str, focus_keyword: str = "") -> str:
    """Second, focused pass that brings a short draft up to length.

    Measured: the combined extract-and-draft call reliably lands ~270-380
    words regardless of model or how emphatically the prompt demands 450+,
    because it is also producing a dozen other fields in the same JSON
    object. A dedicated call whose only output is the description clears the
    bar consistently. Fires only when the first pass came up short, so the
    extra token cost is paid only when it buys something.
    """
    client = get_client()
    ask = (
        f"Facts (do not contradict or go beyond these):\n{facts}\n\n"
        f"Current draft ({len(description.split())} words — too short):\n{description}\n\n"
        f"Expand it to at least {TARGET_DESCRIPTION_WORDS} words."
    )
    if focus_keyword:
        ask += (
            f" Keep the phrase \"{focus_keyword}\" reading naturally in the "
            "opening paragraph and once or twice more — never keyword-stuffed."
        )
    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": EXPAND_SYSTEM_PROMPT},
            {"role": "user", "content": ask},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=2400,
    )
    expanded = str(_message_json(response).get("description", "")).strip()
    # Never trade down: keep whichever version is actually longer.
    if len(expanded.split()) > len(description.split()):
        return expanded[:5000]
    return description


def generate_product_from_source(
    *,
    category_names: list[str],
    source_text: str = "",
    source_title: str = "",
    image: str | None = None,
    name_hint: str = "",
    notes: str = "",
    regions: str = "",
) -> dict:
    """One OpenAI call that EXTRACTS a product's facts and DRAFTS its full
    public content, from whichever source staff supplied:

      * a product page   — prose to mine, usually plus a photo
      * a photo alone    — vision identifies the product (URL or upload)
      * just a name      — no source material, write from the name

    Returns extracted facts alongside the same content keys
    generate_product_draft() produces, so one review form can prefill from
    any of the three. Nothing is saved; staff review first.

    `image` is either an https URL or a base64 data URI (see
    utils.to_vision_data_uri) — the OpenAI vision API accepts both.
    """
    if not (source_text or image or name_hint):
        raise ValueError("Need at least one of: source_text, image, name_hint.")

    client = get_client()

    parts = [
        "Allowed category names (pick exactly one, copied verbatim): "
        + ", ".join(category_names),
    ]
    if regions:
        parts.append(f"Regions this supplier serves: {regions}")
    if name_hint:
        parts.append(
            f"Product name given by staff (treat as authoritative — correct "
            f"only obvious typos): {name_hint}"
        )
    if source_title:
        parts.append(f"Source page title: {source_title}")
    if notes:
        parts.append(f"Staff notes: {notes}")

    if source_text:
        parts.append(
            "Source page text (extract the facts from this, then write entirely "
            "original prose — do not copy its sentences): " + source_text
        )
        if image:
            parts.append(
                "A photo from that page is attached — use it for appearance "
                "and image_alt, and to sanity-check the extracted facts."
            )
    elif image:
        parts.append(
            "An IMAGE of the product is attached and is your only source. "
            "Identify the chemical product from it: read any label, drum, sack "
            "or packaging text visible in the image (product name, grade, "
            "purity, CAS number, net weight, manufacturer) and combine that "
            "with the visible physical form — flakes, pellets, powder, "
            "granules, crystals, liquid — and the packaging type and size.\n"
            "Rules for what you may claim from an image:\n"
            "- Fill 'packaging' ONLY if actual packaging (a sack, drum, bottle, "
            "jerrycan, box) is visible. If you see only loose material, a "
            "close-up, or a diagram, packaging MUST be an empty string.\n"
            "- Fill 'cas_number', 'purity' and 'grade' ONLY if you can read "
            "them in the image. Otherwise leave them empty.\n"
            "- A chemical structure diagram, ball-and-stick or space-filling "
            "molecular model, formula, stock photo, or generic close-up of "
            "white powder/crystals does NOT reliably identify a specific "
            "commercial product. In that case set confidence to 'low' and "
            "leave every measurable field you cannot actually see empty.\n"
            "- Set confidence 'high' ONLY when you have read a legible product "
            "label. No label read means 'low' or at best 'medium'.\n"
            "Never invent a specification to fill a field.\n"
            "TWO THINGS ARE STILL MANDATORY AT EVERY CONFIDENCE LEVEL:\n"
            "1. 'name' must be a real, specific chemical product name — your "
            "single best guess from the image. NEVER output 'unknown', "
            "'unidentified', 'N/A' or an empty name.\n"
            "2. Every content field (description, meta_title, "
            "meta_description, applications, safety_info, faqs, image_alt, "
            "category, focus_keyword) must be written IN FULL to the lengths "
            "required below, for that best-guess product. Low confidence "
            "restricts which hard specifications you may claim — it never "
            "means writing less content."
        )
    else:
        parts.append(
            "No source page or photo was supplied — write from the product "
            "name alone. Fill in only the attributes that are inherent to "
            "that named chemical and leave anything supplier-specific "
            "(purity, packaging, CAS if you are not certain) as empty "
            "strings for staff to complete."
        )

    parts.append("Respond with JSON matching this shape: " + EXTRACT_SCHEMA_HINT)
    # Length/format adherence is the whole SEO game here, and smaller models
    # routinely undershoot it, so restate the hard requirements last where
    # they carry the most weight.
    parts.append(
        "REQUIREMENTS — these are not optional:\n"
        "- description MUST be at least 450 words, split into 4-6 paragraphs "
        "separated by blank lines (\\n\\n). Anything shorter fails review.\n"
        "- applications MUST list 4-8 separate applications, ONE PER LINE, "
        "separated by newline characters — never one run-on line.\n"
        "- meta_description MUST be between 120 and 155 characters.\n"
        "- meta_title MUST be between 40 and 60 characters.\n"
        "- faqs MUST contain 5-7 entries."
    )

    user_content: list = [{"type": "text", "text": "\n\n".join(parts)}]
    if image:
        # Lets the model describe real appearance and write accurate alt text —
        # and, when it's the only source, identify the product outright.
        user_content.append({"type": "image_url", "image_url": {"url": image}})

    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
        # Headroom for a 650-word description plus 7 FAQs and the extracted
        # facts in one response — truncation here silently costs word count.
        max_tokens=3400,
    )
    data = _message_json(response)

    # Bail out before the (paid) expansion pass if the model gave up on
    # identifying the product — a draft named "unknown" with no FAQs is worse
    # than a clear "try a different photo".
    product_name = str(data.get("name", "")).strip()
    if product_name.lower() in UNIDENTIFIED_NAMES:
        raise AIUnidentifiedError(
            "The AI couldn't identify a specific product from that "
            + ("image" if image and not source_text else "source")
            + ". Photos work best when the product label or packaging text is "
            "readable — a molecular diagram or a plain close-up of powder "
            "usually isn't enough. Try a clearer photo, paste a product page "
            "URL, or switch to \"Just the name\"."
        )

    grade = str(data.get("grade", "")).strip().lower()
    if grade not in {"industrial", "food", "lab", "pharma", "cosmetic"}:
        grade = "industrial"
    category = str(data.get("category", "")).strip()
    if category not in category_names:
        category = ""  # caller falls back rather than trusting a hallucinated name

    confidence = str(data.get("confidence", "")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    # This path invents both the name and the focus keyword, so they come from
    # the payload rather than an existing Product row.
    cleaned = _clean_draft(data, str(data.get("name", "")), str(data.get("focus_keyword", "")))
    if len(cleaned["description"].split()) < MIN_DESCRIPTION_WORDS:
        summary = "; ".join(
            f"{k}: {data.get(k)}"
            for k in ("name", "category", "grade", "cas_number", "synonyms",
                      "purity", "appearance", "packaging")
            if str(data.get(k, "")).strip()
        )
        try:
            cleaned["description"] = _expand_description(
                cleaned["description"], summary, str(data.get("focus_keyword", "")),
            )
        except Exception:
            # A short description is still a usable draft — staff see the
            # word count in the on-page checklist and can regenerate. Never
            # let the optional second pass fail the whole import.
            logger.warning("Description expansion pass failed; keeping first draft", exc_info=True)

    return {
        **cleaned,
        "name": product_name[:200],
        "category": category,
        "grade": grade,
        "cas_number": str(data.get("cas_number", ""))[:30].strip(),
        "synonyms": str(data.get("synonyms", ""))[:300].strip(),
        "purity": str(data.get("purity", ""))[:60].strip(),
        "appearance": str(data.get("appearance", ""))[:200].strip(),
        "packaging": str(data.get("packaging", ""))[:200].strip(),
        "focus_keyword": str(data.get("focus_keyword", ""))[:100].strip(),
        "confidence": confidence,
    }


# --- Deterministic SEO guards -------------------------------------------
#
# The prompts above ask for all of this, but asking is not enough: measured
# over the 148-product catalogue the previous prompt achieved only 56%
# compliance on "put the keyword in the meta_title" and 26% on "don't open the
# meta_description with a filler verb". Prompt wording moves the average; it
# does not give a guarantee. These run on every draft so the invariants hold
# regardless of which model produced the text or how it drifts.

# Google truncates the SERP title near 60 characters and the snippet near 155.
SERP_TITLE_LIMIT = 60
SERP_DESC_LIMIT = 155

_FILLER_LEAD = re.compile(
    r"^(?:discover|explore|unlock|elevate|introducing|buy|order|purchase|shop|get)\b[\s,:—-]*",
    re.I,
)
_FILLER_ADJ = re.compile(
    r"^(?:high[\s-]?quality|top[\s-]?quality|premium|superior|best|leading|trusted|reliable|quality)\b[\s,:—-]*",
    re.I,
)
_GEO_TERMS = ("kenya", "east africa", "nairobi", "uganda", "tanzania", "rwanda")


def _truncate_on_word(text: str, limit: int) -> str:
    """Cut to `limit` without slicing a word in half — a mid-word cut is what
    turns a clean title into 'Sodium Hypochlorite Solution for Water Treatm'."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-—|")


def _has_geo(text: str) -> bool:
    return any(g in text.lower() for g in _GEO_TERMS)


# Words that stay lowercase inside a title, unless they lead it.
_TITLE_MINOR_WORDS = {"in", "of", "and", "for", "the", "with", "to", "at", "on", "&", "a"}


def _has_upper(word: str) -> bool:
    return any(c.isupper() for c in word)


def _title_case_if_flat(text: str) -> str:
    """Title-case a string ONLY if it arrived entirely lowercase.

    The all-lowercase test is the safety catch. Chemical copy is full of
    casing that must survive untouched — pH, IBC, PEROXYACETIC ACID, HDPE —
    and this codebase has already been bitten once by a blanket `.toLowerCase()`
    flattening proper nouns. If the model capitalised anything at all, it had
    an opinion about casing and we leave it alone; only a completely flat
    string is treated as a raw keyword that was never cased in the first place.
    """
    if not text or _has_upper(text):
        return text
    words = text.split()
    return " ".join(
        word if index and word in _TITLE_MINOR_WORDS else word[:1].upper() + word[1:]
        for index, word in enumerate(words)
    )


def _capitalise_first(text: str) -> str:
    """Uppercase the opening letter, unless the first word carries its own
    casing (pH, mPa) — in which case it is a term, not a sentence start."""
    if not text or _has_upper(text.split()[0]):
        return text
    return text[:1].upper() + text[1:]


def enforce_meta_title(title: str, product_name: str = "", focus_keyword: str = "") -> str:
    """Guarantee the title leads with substance and carries the region.

    Strips the filler adjectives that were eating characters the keyword
    needed, then appends the region when it is missing — the single most
    common defect, present on 60 of 148 live titles."""
    title = _FILLER_ADJ.sub("", str(title or "").strip()).strip()
    if not title:
        title = product_name.strip()
    if not title:
        return ""
    # Applied to the RAW model output, before any padding adds capitals of its
    # own. Emphasising the primary keyword led the model to hand back the
    # lowercase keyword as the title — "sulphuric acid kenya" — which is
    # publicly visible in the SERP and the browser tab.
    title = _title_case_if_flat(title)
    if not _has_geo(title):
        geo = "Kenya"
        for term in _GEO_TERMS:
            if term in (focus_keyword or "").lower():
                geo = "East Africa" if term == "east africa" else term.title()
                break
        suffix = f" | {geo}"
        title = _truncate_on_word(title, SERP_TITLE_LIMIT - len(suffix)) + suffix
    return _truncate_on_word(_pad_short_title(title), SERP_TITLE_LIMIT)


# Google renders roughly 60 characters of title. Coming in at 12 ("Xylene
# Kenya") wastes four fifths of the most valuable line in the result — but the
# first live run produced exactly that on all five pilot products, because
# emphasising the primary keyword led the model to return the keyword itself as
# the title. Padding is deterministic and additive: qualifiers first, brand
# last, and only while the result still fits.
SERP_TITLE_MIN = 40
# Tried in order, shortest first — the smallest addition that reaches the band
# wins, so a title only gets as wordy as it needs to be.
_TITLE_QUALIFIERS = ("Supplier", "Suppliers & Distributors")
_BRAND_SUFFIX = " | Karivex"
# Any role word already in the title. Matched on the stem so "Supplier"
# suppresses "Suppliers & Distributors" too — checking the whole word let
# "Xylene Supplier Kenya" become "Xylene Supplier Suppliers & Distributors".
_ROLE_STEM = re.compile(r"\b(?:suppl|distribut|stockist|vendor|manufactur)", re.I)


def _insert_role(title: str, qualifier: str) -> str:
    """Put the role before the region — "X Supplier in Kenya", not "X Kenya
    Supplier", which reads like a machine assembled it."""
    for geo in _GEO_TERMS:
        match = re.search(rf"\s*[|,-]?\s*\b({re.escape(geo)})\b", title, re.I)
        if match:
            return title[: match.start()].rstrip(" |,-") + f" {qualifier} in {match.group(1)}"
    return f"{title} {qualifier}"


def _pad_short_title(title: str) -> str:
    """Grow a too-short title into the 40-60 band without inventing a claim.

    Only ever adds role and brand words — never an adjective, a specification
    or a superlative, so nothing here can become a factual claim the business
    cannot support. A title that still falls short after that is left short:
    stuttering "Supplier Suppliers" to hit a character count is worse than an
    honest 31-character title.
    """
    if len(title) >= SERP_TITLE_MIN:
        return title

    options = [title]
    if not _ROLE_STEM.search(title):
        options += [_insert_role(title, q) for q in _TITLE_QUALIFIERS]

    best = title
    for option in options:
        candidate = option
        if "karivex" not in option.lower() and len(option) + len(_BRAND_SUFFIX) <= SERP_TITLE_LIMIT:
            candidate = option + _BRAND_SUFFIX
        if len(candidate) > SERP_TITLE_LIMIT:
            continue
        if len(candidate) >= SERP_TITLE_MIN:
            return candidate  # first option to reach the band
        if len(candidate) > len(best):
            best = candidate
    return best


def enforce_meta_description(desc: str, product_name: str = "", focus_keyword: str = "",
                             detail: str = "") -> str:
    """Guarantee the snippet opens with the product, not a filler verb.

    109 of 148 live descriptions opened with the word 'Discover', which spends
    the most valuable pixels in the result on nothing and makes the catalogue
    read as one template."""
    desc = str(desc or "").strip()
    stripped = _FILLER_LEAD.sub("", desc).strip()
    if stripped != desc and stripped:
        # Re-lead with the product name so the snippet still reads as a
        # sentence, rather than starting mid-clause on a stray adjective.
        stripped = _FILLER_ADJ.sub("", stripped).strip()
        name = product_name.strip()
        if name and not stripped.lower().startswith(name.lower()):
            body = stripped[0].lower() + stripped[1:] if stripped else ""
            desc = f"{name} — {body}"
        else:
            desc = stripped[0].upper() + stripped[1:] if stripped else ""
    if desc and not _has_geo(desc):
        geo = "Kenya"
        tail = f" Delivered across {geo}."
        if len(desc) + len(tail) <= SERP_DESC_LIMIT:
            desc = desc.rstrip() + tail
    # A snippet well under the limit throws away pixels Google would have
    # rendered. Topped up with a PRODUCT-SPECIFIC fact rather than a fixed
    # phrase: appending the same sentence to 178 descriptions would make the
    # catalogue read as one template, which is worse than a short snippet.
    if desc and detail and len(desc) < 120:
        # Only if the copy does not already carry the fact. The first pilot run
        # produced "Get your xylene in drums today! Supplied in drum." and
        # "...with 20 kg bags for easy handling. Supplied in 20 kg bags."
        # Prefix matching on the stem catches drum/drums and bag/bags.
        low = desc.lower()
        key_tokens = [t for t in re.findall(r"[a-z]{4,}", detail.lower())
                      if t not in {"supplied", "with", "from", "purity", "stock", "immediate", "dispatch"}]
        already_said = any(t[:4] in low for t in key_tokens)
        tail = f" {detail.strip().rstrip('.')}."
        if not already_said and len(desc) + len(tail) <= SERP_DESC_LIMIT:
            desc = desc.rstrip() + tail
    return _truncate_on_word(_capitalise_first(desc), SERP_DESC_LIMIT)


def _clean_draft(data: dict, product_name: str = "", focus_keyword: str = "") -> dict:
    faqs = [
        {"q": str(f.get("q", ""))[:300], "a": str(f.get("a", ""))[:1000]}
        for f in data.get("faqs", []) if isinstance(f, dict) and f.get("q") and f.get("a")
    ][:7]
    name = product_name or str(data.get("name", ""))
    kw = focus_keyword or str(data.get("focus_keyword", ""))
    return {
        "description": str(data.get("description", ""))[:5000],
        "meta_title": enforce_meta_title(data.get("meta_title", ""), name, kw),
        "meta_description": enforce_meta_description(data.get("meta_description", ""), name, kw),
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
    data = _message_json(response)
    sources = [
        s for s in data.get("sources", [])
        if isinstance(s, dict) and s.get("type") in ("product", "post") and s.get("slug")
    ][:5]
    return {"answer": str(data.get("answer", ""))[:2000], "sources": sources}


# =====================================================================
# Structured product content pipeline
# =====================================================================
#
# The pipeline the flat-text drafter above could not express:
#
#   image analysis -> structured sections -> SEO assets -> image SEO
#   -> FAQ -> internal links -> related products -> score -> validate
#
# Split across two model calls rather than one. A single call asked to produce
# fifteen prose sections *and* six keyword groups *and* image metadata spends
# its attention budget on breadth and reliably undershoots length on every
# field — the same failure documented on _expand_description() above, one
# level up. Sections first, then SEO assets derived from the finished copy,
# which also means the keywords describe what the page actually says.
#
# Everything factual that a buyer could order against is either passed IN from
# the database or marked NEEDS_VERIFICATION on the way out. The model is never
# the source of a CAS number, a purity figure, or a certification.

STRUCTURED_SYSTEM_PROMPT = (
    "You are writing the product page for an industrial chemical distributor. "
    "You hold every one of these roles at once: industrial chemical "
    "specialist, technical documentation writer, product marketing "
    "specialist, and an assistant to a procurement buyer who is comparing "
    "suppliers. Write for that buyer — someone who already knows what the "
    "chemical is and is deciding whether to raise a purchase order with this "
    "supplier.\n\n"
    "THE ONE ABSOLUTE RULE: never invent a fact. You may write freely about "
    "what a named chemical is used for and how it behaves, because that is "
    "general technical knowledge. You may NOT originate any of the following: "
    "CAS numbers, purity or assay figures, molecular weights, densities, "
    "certifications, regulatory approvals, company age, staff numbers, "
    "warehouse locations, prices, stock levels, or delivery times. Those are "
    "properties of this specific supplier's specific stock, not of the "
    "chemical, and a confident wrong answer sends a buyer the wrong material. "
    f"When you cannot determine such a value from the facts given, output "
    f"exactly \"{NEEDS_VERIFICATION}\" as the value. That is a correct, "
    "expected answer — not a failure. A page with six honest gaps is worth "
    "more than one with six invented specifications.\n\n"
    "COMPANY CLAIMS: the 'Company facts' block in the user message is the "
    "complete set of claims you may make about the supplier. Do not add to "
    "it. If it does not mention a certification, the supplier does not hold "
    "one.\n\n"
    "SUBSTANCE ROLE: describe what the chemical DOES in a process, not what "
    "regulatory or biological category it belongs to. Do not label it an "
    "excipient, an active pharmaceutical ingredient, a food or feed additive, "
    "a dietary supplement, or a plant nutrient unless the product facts say "
    "so — these are classifications with legal meaning, and the wrong one is "
    "the error a technical buyer notices first. Potassium iodide is an "
    "active ingredient, not an excipient; iodine is not a plant nutrient. "
    "When you are unsure of the mechanism, state the use without the "
    "mechanism: 'used in iodometric titration' is safe, 'promotes plant "
    "growth' is a claim you cannot support.\n\n"
    "STYLE: write like a specialist, not a content mill. No filler adjectives "
    "(premium, high-quality, superior, world-class). Never write that a "
    "product is 'versatile' or 'used in a wide range of industries' — say "
    "which industries and what it does there. Never use the connectives "
    "Furthermore, Moreover, Additionally, In addition, It is important to "
    "note, or It is worth noting. Do not start more than one sentence in the "
    "same section with the same three words. Prefer concrete nouns and "
    "figures over adjectives. Do not repeat the same sentence or fact across "
    "sections — each section must earn its place.\n"
    "Respond with strict JSON only, no markdown fences."
)

STRUCTURED_SCHEMA_HINT = """{
  "image_analysis": {
    "product_identity": "what the product appears to be, or the verification marker",
    "packaging_type": "sack | drum | jerrycan | IBC | bottle | box | none visible",
    "package_size": "as printed on the label, else the verification marker",
    "labels_read": ["text you could actually read in the image"],
    "visible_specifications": ["only specs legible in the image"],
    "manufacturer": "only if the brand is legible, else the verification marker",
    "hazard_symbols": ["GHS pictograms actually visible"],
    "physical_form": "liquid | powder | granules | flakes | pellets | crystals | paste | gas",
    "colour": "as seen",
    "confidence": "high | medium | low"
  },
  "sections": {
    "summary": "2-3 paragraphs, 130-200 words, separated by \\n\\n. The FIRST SENTENCE must lead with the SUPPLIER OFFER, not a definition. Pattern: '<Company> supplies <grade/purity if given> <product> in <packaging if given> to <the specific buyer types> across <regions>.' Only then explain what it does and why those buyers need it. A buyer who already knows what the chemical is must learn in one sentence that you stock it, in what form, and where you deliver. Never open with 'X is a chemical compound...'.",
    "key_features": ["6-8 short factual bullets on the MATERIAL and how it is supplied: physical form, stability, handling behaviour, pack formats. Write them as PROSE, never as 'Label: value' — anything in the specification table (CAS, formula, molecular weight, appearance, packaging, hazard class) or the stock/delivery sections is already on the page and a bullet restating it will be discarded. Say what a property MEANS for the buyer: 'Free-flowing crystals that dose without caking' earns its place; 'Appearance: white powder' does not."],
    "benefits": [{"title": "a label naming the specific property or service responsible for the benefit, e.g. 'Consistent assay between lots' or '25 kg packs sized to one batch'", "detail": "1-2 sentences on the concrete operational advantage — what it saves, prevents or enables in the buyer's process. BANNED titles, because they say nothing and repeat across every product: Operational Efficiency, Cost-Effectiveness, Reliable Supply, Comprehensive Documentation, Quick Delivery, Easy Handling, Quality Assurance, Safety Compliance. If the benefit would be equally true of every chemical in the catalogue, it is not a benefit — cut it and write fewer."}],
    "specifications": [{"label": "Appearance", "value": "the value, or the verification marker"}, {"label": "Solubility", "value": "..."}],
    "available_grades": ["ONLY grades stated in the facts given. Empty list if none stated."],
    "grades_note": "1-3 sentences telling a buyer which grade this listing IS and what that suits, so they do not order the wrong material. If only one grade is stated in the facts, say so plainly and say what it is intended for. Never describe grades the supplier has not said it stocks as if they were available here. Empty string if the facts state no grade.",
    "packaging_options": ["ONLY packaging stated in the facts given. Empty list if none stated."],
    "applications": [{"use": "the specific process or operation, naming it precisely — 'iodometric titration', not 'analytical chemistry'", "why": "1-2 sentences on WHY this chemical is the one used there: the property it contributes and what the process needs it for. This is the section buyers read most closely; a bare list of uses tells them nothing they could not guess. State the use without the mechanism rather than inventing a mechanism you cannot support."}],
    "industries": [{"name": "industry", "detail": "2-3 sentences, 35-60 words: what this product does in that industry specifically, which operation it goes into, and what those manufacturers need from a supplier of it. One short sentence here reads as a bare list and wastes the section."}],
    "storage_guidelines": "3-5 sentences: container, temperature range, incompatible materials, ventilation. General good practice for this class of chemical only.",
    "handling_safety": {
      "guidance": "3-5 sentences of general handling practice for this class of chemical. Never invent hazard codes or exposure limits. Close by directing the buyer to the MSDS and COA supplied with their order.",
      "ppe": ["specific PPE items"],
      "_note": "Do NOT output first_aid, spill_response or transport. Those are transcribed from the supplier SDS by staff and are discarded if you write them."
    },
    "typical_uses": [{"scenario": "the job the buyer is trying to do", "guidance": "1-2 factual sentences on why this product suits that job, and — where genuinely relevant — which alternative chemistry is normally used instead and why. Never claim this product is better, cheaper or safer than another; describe what each is used for. Never name a competing supplier."}],
    "faqs": [{"q": "...", "a": "Answer it. An answer that restates the question — 'What is the minimum order quantity?' / 'Contact us for information on minimum order quantities' — is worse than omitting the question, because it is published as FAQ structured data and a search result then shows a non-answer. If the facts given do not let you answer a question, ask a DIFFERENT question that they do let you answer."}],
    "cta": {"headline": "short", "body": "2 sentences. Name the product, invite a quotation request, and state what the team can actually help with — bulk quantities, technical documentation (COA/MSDS), and delivery across the regions listed in the company facts. No urgency language, no discounts, no promises about price."}
  }
}"""


def ensure_identifiers(product) -> list[str]:
    """Fill blank registry identifiers from PubChem, saving them on the product.

    Runs as part of generation so a NEWLY ADDED product reaches the same state
    as one that went through `manage.py backfill_identifiers` — otherwise the
    catalogue drifts into two tiers: backfilled products with a full spec
    table, and anything added later without one.

    Same rules as the command: blank fields only (never overwrites staff
    input), nothing written when the name does not resolve to exactly one
    compound, and UN number left to a human because it depends on
    concentration. Failure is non-fatal — an identifier lookup must never take
    down a content generation.
    """
    from . import chem_lookup

    wanted = ("cas_number", "chemical_formula", "molecular_weight", "density",
              "signal_word", "hazard_statements", "hazard_class")
    if all(getattr(product, field, "") for field in wanted):
        return []

    try:
        result = chem_lookup.lookup_identifiers(product.name)
        if not result:
            return []
        if not (product.density and product.signal_word and product.hazard_class):
            result = {**result, **chem_lookup.lookup_safety(result["cid"])}
    except Exception:
        logger.warning("Identifier lookup failed for %s", product.name, exc_info=True)
        return []

    key = {"cas_number": "cas"}
    updates = {
        field: result[key.get(field, field)]
        for field in wanted
        if not getattr(product, field, "") and result.get(key.get(field, field))
    }
    if not updates:
        return []

    provenance = {"source": result["source"], "cid": result["cid"],
                  "url": result["source_url"], "matched_name": result["matched_name"],
                  "cas_candidates": result.get("cas_candidates", [])}
    for field, value in updates.items():
        setattr(product, field, value)
    product.identifier_source = {
        **(product.identifier_source or {}),
        **{field: provenance for field in updates},
        **({"un_candidates": result["un_candidates"]} if result.get("un_candidates") else {}),
    }
    product.save(update_fields=[*updates, "identifier_source"])
    logger.info("Filled %s for %s from PubChem CID %s",
                ", ".join(updates), product.name, result["cid"])
    return list(updates)


def _product_record(product) -> str:
    """Everything the BUSINESS has already vouched for about this substance.

    Used to suppress role-claim flags: if the staff-written description already
    calls a product a food additive, the generator repeating it is not an
    invention. Deliberately excludes anything the model produced.
    """
    return " ".join(str(value) for value in (
        product.name, product.synonyms, product.get_grade_display(),
        getattr(product.category, "name", ""), product.description,
        product.applications,
    ) if value)


def verified_facts_for(product) -> dict[str, str]:
    """The spec values the DATABASE vouches for. Only these may fill a
    DB-only spec row (see content_schema.DB_ONLY_SPEC_LABELS)."""
    return {
        "cas number": (product.cas_number or "").strip(),
        "purity": (product.purity or "").strip(),
        "chemical formula": (product.chemical_formula or "").strip(),
        "molecular weight": (product.molecular_weight or "").strip(),
        "density": (product.density or "").strip(),
        "signal word": (product.signal_word or "").strip(),
        "hazard class": (product.hazard_class or "").strip(),
        "un number": (product.un_number or "").strip(),
    }


def _product_facts(product, notes: str = "", source_text: str | None = None) -> list[str]:
    """Everything known from the database, stated as fact to the model."""
    facts = [
        f"Product name: {product.name}",
        f"Category: {product.category.name}",
        f"Grade: {product.get_grade_display()}",
        f"Regions served: {product.regions}",
        f"Stock status: {product.get_stock_status_display()}",
    ]
    optional = (
        ("CAS number", product.cas_number),
        ("Synonyms", product.synonyms),
        ("Purity", product.purity),
        ("Chemical formula", product.chemical_formula),
        ("Molecular weight", product.molecular_weight),
        ("UN number", product.un_number),
        ("Hazard class", product.hazard_class),
        ("Packaging", product.packaging),
        ("Appearance", product.appearance),
        ("Focus keyword", product.focus_keyword),
    )
    for label, value in optional:
        if value:
            facts.append(f"{label}: {value}")
        elif label in ("CAS number", "Purity", "Packaging", "UN number", "Hazard class"):
            # Naming the gap explicitly stops the model quietly filling it.
            facts.append(
                f"{label}: NOT RECORDED — output \"{NEEDS_VERIFICATION}\" for this; do not guess."
            )
    if notes:
        facts.append(f"Staff notes (authoritative): {notes}")
    if source_text:
        facts.append(
            "Reference material from a staff-supplied source page. Use it only to "
            "ground facts, rewrite entirely in your own words, never copy sentences, "
            "and never adopt a claim that contradicts the facts above: " + source_text[:6000]
        )
    return facts


def _company_block() -> str:
    facts = content_schema.company_facts(settings.SITE)
    lines = [f"Supplier: {facts['company']}"]
    if facts["regions"]:
        lines.append("Regions served: " + ", ".join(facts["regions"]))
    for entry in facts["delivery"]:
        lines.append(f"Delivery: {entry}")
    if facts["documentation"]:
        lines.append(f"Documentation: {facts['documentation']}")
    if facts["hours"]:
        lines.append(f"Support hours: {facts['hours']}")
    lines.append(
        "No other supplier claim may be made. The supplier holds no "
        "certification, award, rating or years-in-business record beyond what "
        "is listed here — do not imply otherwise."
    )
    return "\n".join(lines)


def _search_intent_block(plan: dict) -> str:
    """Tell the writer WHAT BUYERS ARE LOOKING FOR, not which strings to use.

    This is the whole reason the keyword engine runs before the copy instead
    of after it. Handing a model a list of twenty phrases to include produces
    stuffed prose — the same failure that put "used in regions such as acetic
    acid Kenya" on 58 of 148 live pages when the old prompt demanded the
    verbatim focus phrase. Intents get covered; phrases get pasted.
    """
    candidates = plan["candidates"]
    facets = plan["facets"]
    lines = [
        "SEARCH INTENT — what buyers looking for this product actually want to "
        "know. Cover these TOPICS in natural English. Do NOT paste any phrase "
        "below into the copy verbatim: they are search queries, not sentences. "
        f"Writing \"{facets['head']} kenya\" is spam; writing "
        f"\"{facets['head']} supplied across Kenya\" is correct.",
        f"- The buyer is searching for: {plan['primary']}",
    ]
    if facets["family"]:
        lines.append(f"- Chemical family to establish topically: {facets['family']}")
    if facets["category"]:
        lines.append(f"- Catalogue context: {facets['category']}")
    if facets["packaging"]:
        lines.append("- Pack formats buyers ask for: " + ", ".join(facets["packaging"]))
    if plan["geo"]["all"]:
        lines.append("- Places supplied (name them naturally where relevant, never as a "
                     "list): " + ", ".join(plan["geo"]["all"]))
    lines.append("- Commercial questions to answer somewhere on the page: "
                 + "; ".join(candidates["buyer_intent_keywords"][:6]))
    lines.append(
        "- Topics the FAQs should answer. Write each question the way a buyer "
        "would actually type it in an email — do NOT reuse the phrasings below "
        "as question text, and never repeat one across two questions: "
        + "; ".join(candidates["long_tail_keywords"][:6]))
    lines.append(
        "Use each idea ONCE where it genuinely belongs. Repeating the product "
        "name in every bullet, or ending several sentences with the country "
        "name, reads as spam to a buyer and as keyword stuffing to Google."
    )
    return "\n".join(lines)


def _generate_sections(product, image_payload, notes, source_text, plan) -> dict:
    """Call A — image analysis plus the fifteen content sections."""
    client = get_client()
    parts = [
        "Company facts (the complete set of supplier claims you may make):\n" + _company_block(),
        "Product facts from the supplier's database (authoritative):\n"
        + "\n".join(_product_facts(product, notes, source_text)),
        _search_intent_block(plan),
    ]
    if image_payload:
        parts.append(
            "A photograph of the product is attached. Read it for packaging "
            "type and size, label text, manufacturer branding, GHS hazard "
            "pictograms, physical form and colour. Report ONLY what is "
            "actually legible or visible — if the image is a close-up of "
            "loose material, a molecular diagram or a stock photo, say so via "
            f"low confidence and \"{NEEDS_VERIFICATION}\" rather than "
            "describing packaging that is not there. Never let the image "
            "override a value already given in the product facts above."
        )
    else:
        parts.append(
            "No photograph was supplied. Set every image_analysis field to "
            f"\"{NEEDS_VERIFICATION}\" and confidence to \"low\"."
        )
    parts.append("Respond with JSON matching this shape:\n" + STRUCTURED_SCHEMA_HINT)
    parts.append(
        "REQUIREMENTS — not optional:\n"
        "- summary: 130-200 words across 2-3 paragraphs.\n"
        "- key_features: 6-8 entries. benefits: 4-6 entries.\n"
        "- applications: 6-10 entries. industries: 4-8 entries.\n"
        "- typical_uses: 3-5 entries.\n"
        "- Not every reader is ready to buy. The summary, applications and "
        "industries sections must answer the informational question (what it "
        "does, how it behaves, which grade suits which job) properly, and let "
        "the CTA carry the commercial ask. Do not turn explanatory sections "
        "into sales copy.\n"
        "- NAME THINGS. \"Suitable for various industrial applications\" tells a "
        "buyer nothing — write \"Used in fertiliser manufacturing, metal "
        "pickling, wastewater neutralisation and battery production\". Every "
        "time you are about to write \"various\", \"a range of\", \"many\", "
        "\"numerous\" or \"different\" followed by industries, applications or "
        "uses, replace it with the actual list. This applies to the summary, "
        "features, benefits, applications, industries and the image caption.\n"
        "- faqs: 5-7 entries, covering MOQ and bulk orders, packaging sizes, "
        "delivery regions and lead time, COA and MSDS availability, stock "
        "status, grade selection, and technical support. Do not ask a question "
        "the page already answers in its opening paragraph.\n"
        "- specifications: ONE OBJECT PER PROPERTY. Use these labels where you "
        "can determine a value: Grade, Chemical Formula, Molecular Weight, "
        "Appearance, Solubility, Density, Packaging, Storage Conditions, Shelf "
        "Life. Never put more than one property name in a single label — "
        "\"Appearance | Density\" is wrong, two separate objects is right.\n"
        "- available_grades and packaging_options: leave as empty lists unless "
        "the product facts above actually state them. Do not populate them "
        "from the image alone unless the pack size is printed and legible."
    )

    user_content: list = [{"type": "text", "text": "\n\n".join(parts)}]
    if image_payload:
        user_content.append({"type": "image_url", "image_url": {"url": image_payload}})

    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": STRUCTURED_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
        # Sixteen sections of prose in one object. Raised from 4500 after the
        # typical_uses section pushed the longest product (sulphuric acid) over
        # the limit: the reply came back valid JSON but missing key_features,
        # benefits and cta entirely, which reads as a model failure rather than
        # truncation. Headroom is far cheaper than a wasted generation.
        max_tokens=6000,
    )
    data = _message_json(response)
    if response.choices[0].finish_reason == "length":
        # Valid JSON can still be short a few sections when the model runs out
        # of room mid-object. Log it so a sparse result is diagnosable instead
        # of looking like the model simply refused to write them.
        logger.warning(
            "Sections response hit the token limit — some sections may be missing.")
    return data


SEO_ASSET_SYSTEM_PROMPT = (
    "You are an SEO consultant and semantic-search specialist producing the "
    "search assets for an industrial chemical product page that has already "
    "been written. You are given the finished copy. Derive the assets FROM "
    "that copy — every keyword you return must be a phrase the page could "
    "honestly rank for, covering commercial, informational and transactional "
    "intent. Do not invent product attributes; you are not writing content.\n"
    "Keyword rules: lowercase, no duplicates across groups, no keyword "
    "stuffing, and no phrase that reads as a machine-generated permutation "
    "('chemical supplier supplier kenya'). Geographic keywords must name real "
    "places the supplier serves. Buyer-intent keywords are what someone ready "
    "to purchase types — 'bulk', 'supplier', 'price', 'distributor', "
    "'wholesale', '25kg', 'near me'.\n"
    "Headings must form a real H2/H3 outline of the page as written.\n"
    "External references: only PubChem, ECHA, CDC, OSHA, WHO, FAO, EPA or "
    "NIST, and only when genuinely relevant. Return an empty list rather than "
    "a guessed URL — a broken citation is worse than none.\n"
    "Respond with strict JSON only, no markdown fences."
)

SEO_SCHEMA_HINT = """{
  "meta_title": "<=60 characters. Lead with the product name, and include the country or region. No filler adjectives (High-Quality, Premium, Best, Superior, Leading).",
  "meta_description": "150-160 characters. MUST start with the product name, never a verb such as Discover/Explore/Buy/Unlock. Include the region plus one concrete buyer-facing detail, then a short call to action.",
  "h1": "the visible page heading — human phrasing, may differ from meta_title",
  "heading_suggestions": ["3-5 H2 headings that work a DIFFERENT commercial variation into each one, e.g. 'Bulk sulphuric acid supply across East Africa', 'Buying sulphuric acid in Nairobi'. Natural sentence headings, never a bare keyword. These are suggestions for the page outline."],
  "focus_keyword": "the single phrase this page should rank for, lowercase, 2-5 words, including the region",
  "secondary_keywords": ["10-20 commercial variations the page can honestly rank for"],
  "semantic_keywords": ["6-12 topically related terms that establish subject relevance, NOT variations of the focus keyword"],
  "long_tail_keywords": ["4-10 full phrases of 4+ words, phrased the way a buyer searches"],
  "buyer_intent_keywords": ["4-10 purchase-ready phrases"],
  "geographic_keywords": ["4-10 place-qualified phrases, using ONLY the supplied places"],
  "headings": [{"h2": "section heading", "h3": ["sub-headings"]}],
  "external_references": [{"title": "...", "url": "https://..."}],
  "image_seo": {
    "alt": "<=140 characters. Describe what is actually visible, then who supplies it and where: '<pack size and type> of <purity/grade if known> <product> supplied by <company> for industrial use in <country>'. Written for a screen reader first — it must still read as a description of the picture, not a caption stuffed with company detail.",
    "title": "short",
    "caption": "one sentence suitable for display under the image",
    "filename": "hyphenated-descriptive-name.jpg"
  }
}"""


def _generate_seo_assets(product, sections: dict, image_analysis: dict, plan: dict) -> dict:
    """Call B — SEO assets and image SEO, derived from the finished copy."""
    client = get_client()
    outline = [
        f"Product: {product.name}",
        f"Category: {product.category.name}",
        f"Regions served: {product.regions}",
        f"Primary keyword (use this verbatim as focus_keyword): {plan['primary']}",
        # Candidates are a menu, not a quota. The model has read the copy and
        # knows which of these the page can honestly answer; anything it drops
        # is topped back up deterministically by reconcile_keyword_sets().
        "Derived candidate keywords — keep the ones this page genuinely "
        "satisfies, discard the rest, and add better ones you can justify from "
        "the copy:\n"
        + "\n".join(
            f"  {group.replace('_', ' ')}: " + "; ".join(items)
            for group, items in plan["candidates"].items() if items
        ),
        "Geographic keywords may ONLY use these places: "
        + ", ".join(plan["geo"]["all"]) + ". Naming anywhere else is a factual error.",
    ]
    outline.append("Summary as written:\n" + (sections.get("summary") or ""))
    if sections.get("applications"):
        outline.append("Applications covered: " + "; ".join(
            application_uses(sections)[:10]))
    if sections.get("industries"):
        outline.append("Industries covered: " + "; ".join(
            i.get("name", "") for i in sections["industries"][:8]))
    visible = ", ".join(filter(None, [
        image_analysis.get("packaging_type", ""),
        image_analysis.get("package_size", ""),
        image_analysis.get("physical_form", ""),
        image_analysis.get("colour", ""),
    ]))
    outline.append(
        f"Visible in the product photo (for image alt/caption): {visible or 'nothing verified'}"
    )
    outline.append("Respond with JSON matching this shape:\n" + SEO_SCHEMA_HINT)

    response = client.chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": SEO_ASSET_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(outline)},
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
        max_tokens=1600,
    )
    return _message_json(response)


DESTUFF_SYSTEM_PROMPT = (
    "You are an editor removing keyword stuffing from product copy. This is a "
    "STYLE edit with one goal: make the text read as though a specialist wrote "
    "it for a buyer, not for a search engine.\n"
    "PRESERVE EXACTLY: every factual claim, product name, CAS number, purity "
    "figure, percentage, pack size, grade, application, industry, place name "
    "and delivery term. Do NOT add any specification, certification, figure or "
    "claim that is not already in the text — you have no source to check "
    "additions against. Do NOT shorten the text by more than 10%: remove "
    "repetition, not information.\n"
    "WHAT TO FIX: a phrase repeated more often than a human would repeat it; "
    "search queries pasted in as if they were English (\"acetic acid kenya\" "
    "should read \"acetic acid supplied across Kenya\"); several sentences in a "
    "row ending on the same place name; the product's full name repeated in "
    "every bullet where a pronoun or shorter form would read better.\n"
    "Keep the paragraph and list structure exactly as given.\n"
    'Respond with strict JSON only: {"text": "..."}'
)


def _destuff_text(text: str, plan: dict, overused: list[str], splices: list[str]) -> str:
    """Rewrite one over-optimised block, holding its facts fixed.

    Returns the original text unchanged if the rewrite comes back empty, too
    short, or still stuffed — a failed repair must never be able to shorten a
    page or drop a specification. Mirrors the guard rails already proven on
    restyle_description(): word-count floor plus numeric-fact preservation,
    because a style pass deleting "25 kg" was a real, measured failure there
    (92 of 148 descriptions lost a figure).
    """
    original_words = len(text.split())
    floor = int(original_words * 0.9)
    ask = [f"Revise the text below. Keep at least {floor} words "
           f"(the original has {original_words})."]
    if overused:
        ask.append("Over-repeated phrases to thin out (keep each idea, state it once): "
                   + ", ".join(f'"{p}"' for p in overused))
    if splices:
        ask.append("Search queries pasted in as prose — rewrite these clauses into plain "
                   "English that still names the product and the place: "
                   + ", ".join(f'"{s}"' for s in splices))
    ask.append(f"The page targets the query \"{plan['primary']}\". It must still be "
               "obvious what the product is and where it is supplied — but say so once, "
               "in natural English.")
    ask.append("\nTEXT:\n" + text)

    response = get_client().chat.completions.create(
        model=settings.OPENAI_CONTENT_MODEL,
        messages=[
            {"role": "system", "content": DESTUFF_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(ask)},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
        max_tokens=2000,
    )
    revised = str(_message_json(response).get("text", "")).strip()
    if not revised or len(revised.split()) < floor * 0.95:
        logger.warning("de-stuff pass came back short — keeping original")
        return text
    dropped = numeric_facts(text) - numeric_facts(revised)
    if dropped:
        logger.warning("de-stuff pass dropped quantities %s — keeping original", sorted(dropped))
        return text
    return strip_banned_connectives(revised)


# Sections whose rewritten text can be written straight back as a single
# string. List-shaped sections (features, applications, FAQs) are deliberately
# excluded: reflowing prose back into the right number of bullets is not
# reliable, and a botched split would silently drop an application.
_REWRITABLE_TEXT_SECTIONS = ("summary", "storage_guidelines")


def destuff_sections(sections: dict, plan: dict, seo: dict) -> tuple[dict, list[str]]:
    """Automatically rewrite over-optimised prose before publishing.

    Returns the sections and the list of keys actually rewritten. Only the
    free-prose sections are repaired automatically; a stuffed list section is
    still reported by the validator for a human to fix, because silently
    restructuring a bulleted list risks losing an item.
    """
    rewritten: list[str] = []
    for key in _REWRITABLE_TEXT_SECTIONS:
        text = sections.get(key) or ""
        if not text:
            continue
        analysis = kw_engine.analyse_section(text, plan, seo)
        if not kw_engine.is_stuffed(analysis):
            continue
        try:
            revised = _destuff_text(text, plan, analysis["overused"], analysis["splices"])
        except Exception:
            # A failed repair leaves the validator to report the problem —
            # never fail the whole generation over an optional pass.
            logger.warning("de-stuff pass failed for section %s", key, exc_info=True)
            continue
        if revised != text:
            sections[key] = revised
            rewritten.append(key)
    return sections, rewritten


# Vague quantifier + the noun a buyer wanted the specifics of. Same family the
# validator flags, captured here so the phrase can be REPLACED rather than
# merely reported.
_VAGUE_NOUN = re.compile(
    r"\b(?:various|numerous|many|multiple|several|different|"
    r"a\s+(?:wide\s+)?(?:range|variety)\s+of|a\s+number\s+of)\s+"
    # Up to three intervening adjectives, because the qualifier is rarely
    # adjacent in practice: "various pharmaceutical and industrial
    # applications" slipped past a pattern that only allowed
    # industrial/commercial/other.
    r"(?:\w+\s+){0,3}"
    r"(?:applications?|industries|uses|sectors|purposes|needs|fields)\b",
    re.I,
)


def _join_list(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def specify_vague_phrases(text: str, specifics: list[str]) -> str:
    """Replace "various industrial applications" with the actual industries.

    Asking the model not to write this does not work — it shipped across the
    first live pilot even with an explicit instruction naming the exact phrase.
    But the page already knows the answer: the industries and applications
    sections list them. So the vague phrase is substituted for real content
    rather than reported and left in place.

    Falls back to leaving the text untouched when there is nothing concrete to
    substitute — an honest vague phrase beats an invented specific one, and the
    validator still raises it for a human.
    """
    if not specifics:
        return text
    replacement = _join_list([s.lower() for s in specifics[:3]])
    return _VAGUE_NOUN.sub(replacement, text or "")


def application_uses(sections: dict) -> list[str]:
    """The `use` half of each application, tolerating the pre-pair shape.

    Applications became `{use, why}` pairs; products generated before that
    still hold plain strings, and this runs over stored content as well as
    freshly generated content.
    """
    out: list[str] = []
    for item in sections.get("applications") or []:
        text = item if isinstance(item, str) else (item or {}).get("use", "")
        if text:
            out.append(str(text))
    return out


def _section_specifics(sections: dict) -> list[str]:
    """Concrete industries this page actually covers, for substitution."""
    names = [i.get("name", "") for i in sections.get("industries", []) if i.get("name")]
    if len(names) < 2:
        names += [a.split(" in ")[-1] for a in application_uses(sections)[:3]]
    return [n.strip() for n in names if n.strip()][:3]


def _clean_prose_sections(sections: dict) -> dict:
    """Apply the deterministic connective strip to every prose surface.

    strip_banned_connectives() previously only reached `description`. The
    section split multiplied the number of places a "Furthermore," can hide,
    and the model reproduces them even when the prompt forbids them by name.
    """
    specifics = _section_specifics(sections)

    def clean(text: str) -> str:
        return specify_vague_phrases(strip_banned_connectives(text), specifics)

    for key in ("summary", "storage_guidelines", "grades_note"):
        if sections.get(key):
            sections[key] = clean(sections[key])
    if sections.get("handling_safety", {}).get("guidance"):
        sections["handling_safety"]["guidance"] = clean(sections["handling_safety"]["guidance"])
    sections["key_features"] = [clean(f) for f in sections.get("key_features", [])]
    sections["applications"] = [
        clean(a) if isinstance(a, str)
        else {**a, "use": clean(a.get("use", "")), "why": clean(a.get("why", ""))}
        for a in sections.get("applications", [])
    ]
    for item in sections.get("benefits", []):
        item["detail"] = clean(item.get("detail", ""))
    for item in sections.get("industries", []):
        item["detail"] = clean(item.get("detail", ""))
    for item in sections.get("typical_uses", []):
        item["guidance"] = clean(item.get("guidance", ""))
    for item in sections.get("faqs", []):
        item["a"] = clean(item.get("a", ""))
    if sections.get("cta", {}).get("body"):
        sections["cta"]["body"] = clean(sections["cta"]["body"])
    return sections


# Internal link targets that exist as real routes in the frontend app. A
# suggestion pointing at a 404 costs staff time and, if followed, leaks crawl
# budget — so this list is checked against `frontend/app/**/page.tsx` rather
# than assumed. There is deliberately no /safety-resources entry: that page
# does not exist yet.
STATIC_LINK_TARGETS = [
    {"path": "/quote", "title": "Request a quotation", "reason": "Primary conversion page"},
    {"path": "/contact", "title": "Contact sales", "reason": "Buyer contact route"},
    {"path": "/how-we-work", "title": "How we work", "reason": "Ordering process and documentation"},
    {"path": "/categories", "title": "All product categories", "reason": "Catalogue hub"},
]


def build_internal_links(product, limit: int = 8, plan: dict | None = None) -> list[dict]:
    """Deterministic, DB-driven internal links — no model call.

    Which pages exist is a fact the database and the router already know.
    Asking a model to suggest URLs risks a confident 404, and there is nothing
    to gain: the query is exact.

    When a keyword plan is supplied, catalogue links carry varied
    keyword-aware anchor text instead of the bare page title — 148 pages
    linking out with identical anchors wastes the signal, and 148 pages using
    the identical keyword anchor is a footprint.
    """
    links: list[dict] = []
    if product.category_id:
        links.append({
            "path": f"/categories/{product.category.slug}",
            "title": product.category.name,
            "reason": "Parent category",
            "type": "category",
        })
        parent = getattr(product.category, "parent", None)
        if parent:
            links.append({
                "path": f"/categories/{parent.slug}",
                "title": parent.name,
                "reason": "Industry landing page",
                "type": "category",
            })
    for suggestion in suggest_internal_links(product, limit=4):
        prefix = "/products/" if suggestion["type"] == "product" else "/blog/"
        links.append({
            "path": prefix + suggestion["slug"],
            "title": suggestion["title"],
            "reason": suggestion["reason"],
            "type": suggestion["type"],
        })
    links.extend({**t, "type": "page"} for t in STATIC_LINK_TARGETS)
    links = links[:limit]

    if plan:
        for index, link in enumerate(links):
            # Static pages keep their plain, functional labels — "Request a
            # quotation" is already the right anchor and does not want a
            # keyword bolted onto it.
            link["anchor"] = (link["title"] if link["type"] == "page"
                              else kw_engine.anchor_text(link["title"], index, plan))
    return links


def build_related_products(product, limit: int = 6) -> list[dict]:
    """Related products, straight from the catalogue.

    Same-category first, then products sharing a category parent — so a
    product in a thin category still gets a lateral crawl path instead of an
    empty band. Only real rows are ever returned.
    """
    from catalog.models import Product

    qs = (Product.objects.filter(category=product.category)
          .exclude(pk=product.pk).select_related("category")
          .order_by("-featured", "-updated_at"))
    related = list(qs[:limit])
    if len(related) < limit and getattr(product.category, "parent_id", None):
        siblings = (Product.objects
                    .filter(category__parent_id=product.category.parent_id)
                    .exclude(pk=product.pk)
                    .exclude(pk__in=[p.pk for p in related])
                    .select_related("category")
                    .order_by("-featured", "-updated_at"))
        related += list(siblings[: limit - len(related)])
    return [
        {"slug": p.slug, "name": p.name, "category": p.category.name,
         "purity": p.purity, "packaging": p.packaging}
        for p in related
    ]


def run_generation_job(job_id: int, product_ids: list[int]) -> None:
    """Work through a queue of products, updating the job row as it goes.

    Runs on a background thread so no HTTP request is held open for the
    30-60 seconds a single product costs. Deliberately defensive: every
    product is wrapped, because one bad product must not abandon the other
    173, and the database connection is closed at the end because a thread
    that Django did not spawn does not get one cleaned up for it.
    """
    from django.db import close_old_connections
    from catalog.models import GenerationJob, Product

    close_old_connections()
    try:
        for product_id in product_ids:
            job = GenerationJob.objects.filter(pk=job_id).first()
            # Checked between products, never mid-generation: stopping should
            # not waste a product that is already half paid for.
            if job is None or job.cancel_requested:
                break

            product = Product.objects.select_related("category").filter(pk=product_id).first()
            if product is None:
                continue

            entry = {"id": product_id, "name": product.name}
            try:
                payload = generate_structured_product_content(product)
                report = payload["report"]
                entry["score"] = payload["score"]
                if report["publishable"]:
                    _apply_structured(product, payload)
                    entry["status"] = "published"
                    job.published += 1
                else:
                    Product.objects.filter(pk=product_id).update(
                        ai_draft=payload, ai_draft_generated_at=timezone.now())
                    entry["status"] = "held"
                    entry["errors"] = [i["message"] for i in report["issues"]
                                       if i["severity"] == "error"][:3]
                    job.held += 1
            except Exception as exc:
                logger.exception("Generation failed for product %s in job %s", product_id, job_id)
                entry["status"] = "error"
                entry["detail"] = f"{type(exc).__name__}: {exc}"[:200]
                job.failed += 1

            job.processed += 1
            job.results = ([entry] + list(job.results or []))[:80]
            job.save(update_fields=["processed", "published", "held", "failed",
                                    "results", "updated_at"])

        job = GenerationJob.objects.filter(pk=job_id).first()
        if job:
            job.status = "cancelled" if job.cancel_requested else "done"
            job.save(update_fields=["status", "updated_at"])
    except Exception as exc:
        logger.exception("Generation job %s crashed", job_id)
        GenerationJob.objects.filter(pk=job_id).update(
            status="failed", detail=f"{type(exc).__name__}: {exc}"[:500])
    finally:
        close_old_connections()


def _apply_structured(product, payload: dict) -> None:
    """Write a validated payload onto the product's structured fields.

    Never touches the flat prose columns — the same contract the
    single-product path uses with apply_flat=false.
    """
    product.content_sections = payload["sections"]
    product.seo_assets = payload["seo"]
    product.image_seo = payload["image_seo"]
    product.internal_links = payload["internal_links"]
    product.seo_score = payload["score"]
    product.content_report = payload["report"]
    product.content_generated_at = timezone.now()
    # save() rather than update() so the revalidation signal fires.
    product.save()


def generate_structured_product_content(
    product, image_url: str | None = None, notes: str = "", source_text: str | None = None
) -> dict:
    """Run the full structured pipeline for one product.

    Returns the complete payload — sections, SEO assets, image SEO, internal
    links, related products, quality score and validation report. Writes
    nothing: the caller decides whether to store it as a draft or apply it,
    preserving the human-review guarantee in catalog/models.py.
    """
    # Registry identifiers first, so the spec table this generation builds
    # already has real CAS/formula/density values to mark as verified rather
    # than filling the table with verification markers.
    filled_identifiers = ensure_identifiers(product)

    image_payload = _image_data_uri(product, image_url)
    related_products = build_related_products(product)

    # Stage 1 — a keyword plan from the product's own facts, before any copy
    # exists. This is what the writer is briefed against, so the content is
    # shaped by real buyer intent rather than having keywords bolted on after.
    plan = kw_engine.build_keyword_plan(
        product, settings.SITE, settings.SITE_DELIVERY_CITIES,
        related_names=[r["name"] for r in related_products],
    )

    raw = _generate_sections(product, image_payload, notes, source_text, plan)
    image_analysis = raw.get("image_analysis") if isinstance(raw.get("image_analysis"), dict) else {}
    sections = content_schema.coerce_sections(
        raw.get("sections") or raw,
        verified_facts=verified_facts_for(product),
        # Regeneration must not discard SDS text a human transcribed.
        preserved=(product.content_sections or {}).get("handling_safety"),
    )
    sections = _clean_prose_sections(sections)

    # Stage 2 — refine the plan now the industries the copy actually covers are
    # known. Those drive the "<product> for <industry>" and "<industry>
    # chemicals" phrases, which cannot be derived before the content exists.
    plan = kw_engine.build_keyword_plan(
        product, settings.SITE, settings.SITE_DELIVERY_CITIES,
        industries=[i.get("name", "") for i in sections.get("industries", [])],
        related_names=[r["name"] for r in related_products],
    )

    # Packaging comes from the database, not the model. The pilot rendered a
    # "Packaging options" section reading just "drum" while the product row
    # said "100-liter drum" — the model had paraphrased away the one detail a
    # buyer needs. The DB value is authoritative whenever it exists.
    if product.packaging:
        sections["packaging_options"] = [
            part.strip() for part in re.split(r"[,;]|\band\b", product.packaging)
            if part.strip()
        ]

    # Sections the business owns rather than the model: assembled from
    # settings.SITE so they can never claim a credential Karivex lacks.
    sections["why_choose_us"] = content_schema.why_choose_us(settings.SITE)
    sections["delivery_coverage"] = {
        "regions": [r.strip() for r in (product.regions or "").split(",") if r.strip()]
                   or list(settings.SITE.get("regions") or []),
        "notes": content_schema.company_facts(settings.SITE)["delivery"],
    }

    try:
        seo_raw = _generate_seo_assets(product, sections, image_analysis, plan)
    except Exception:
        # SEO assets are a second call; losing them should degrade the result,
        # not fail the whole generation. The validator will flag what's absent.
        logger.warning("SEO asset pass failed for product %s", product.pk, exc_info=True)
        seo_raw = {}

    seo = content_schema.coerce_seo(seo_raw)
    # Stage 3 — merge the model's selections with the derived candidates, drop
    # cross-group duplicates, and strip any place the business does not serve.
    seo = kw_engine.reconcile_keyword_sets(seo, plan)
    if not seo["h1"]:
        primary_country = plan["geo"]["countries"][0] if plan["geo"]["countries"] else "Kenya"
        seo["h1"] = f"{product.name} Supplier in {primary_country}"
    # Same lowercase-keyword echo that hit meta_title, and more visible: the H1
    # is the page's main heading. The pilot shipped "xylene supplier in kenya".
    # _capitalise_first also covers the half-cased case ("peroxyacetic acid ...
    # in Kenya"), which the all-lowercase guard deliberately leaves alone.
    seo["h1"] = _capitalise_first(_title_case_if_flat(seo["h1"]))

    image_seo = content_schema.coerce_image_seo(seo_raw.get("image_seo"), product.name)
    # The caption and alt text are read by buyers and by Google Images, and the
    # pilot produced "…for various industrial applications" in both.
    specifics = _section_specifics(sections)
    for key in ("alt", "caption"):
        image_seo[key] = specify_vague_phrases(image_seo[key], specifics)
    if not image_seo["alt"]:
        image_seo["alt"] = (product.image_alt
                            or f"{product.name} supplied by {settings.SITE.get('name', '')}")[:160]

    # The measured deterministic repairs — filler-verb stripping and geo-term
    # injection — run last, after all copy has settled.
    meta_title = enforce_meta_title(
        seo_raw.get("meta_title") or product.meta_title, product.name, seo["focus_keyword"])
    # Concrete, product-specific detail used only if the snippet comes back
    # short — packaging first, then purity, then stock status.
    snippet_detail = next(
        (d for d in (
            f"Supplied in {product.packaging}" if product.packaging else "",
            f"Purity {product.purity}" if product.purity else "",
            "In stock for immediate dispatch" if product.in_stock else "",
        ) if d), "")
    meta_description = enforce_meta_description(
        seo_raw.get("meta_description") or product.meta_description,
        product.name, seo["focus_keyword"], detail=snippet_detail)

    # The SEO pass writes these independently of the sections, so it never saw
    # the vague-phrase substitution. The pilot published meta descriptions
    # reading "…for various industrial applications" while the body copy named
    # the real industries.
    meta_title = specify_vague_phrases(meta_title, specifics)
    meta_description = specify_vague_phrases(meta_description, specifics)
    seo["meta_title"] = _truncate_on_word(meta_title, SERP_TITLE_LIMIT)
    seo["meta_description"] = _truncate_on_word(meta_description, SERP_DESC_LIMIT)
    meta_title, meta_description = seo["meta_title"], seo["meta_description"]
    seo["canonical_path"] = f"/products/{product.slug}"
    seo["slug"] = product.slug
    seo["open_graph"] = {
        "title": meta_title,
        "description": meta_description,
        "type": "website",
        "image_alt": image_seo["alt"],
    }
    seo["twitter"] = {
        "card": "summary_large_image",
        "title": meta_title,
        "description": meta_description,
        "image_alt": image_seo["alt"],
    }

    internal_links = build_internal_links(product, plan=plan)
    seo["internal_links"] = internal_links

    # Stage 4 — automatic de-stuffing. Runs BEFORE validation so the report
    # describes what will actually be published, not a draft that no longer
    # exists. Only free-prose sections are repaired automatically; a stuffed
    # list is left for a human, since reflowing bullets risks losing one.
    sections, rewritten = destuff_sections(sections, plan, seo)

    report = validation.validate_content(
        sections=sections,
        seo=seo,
        image_seo=image_seo,
        meta_title=meta_title,
        meta_description=meta_description,
        product_name=product.name,
        supported_claims=_company_block(),
        product_record=_product_record(product),
        internal_links=internal_links,
        plan=plan,
        slug=product.slug,
    )
    report["rewritten_sections"] = rewritten

    return {
        "image_analysis": image_analysis,
        "sections": sections,
        "seo": seo,
        "keyword_plan": plan,
        "image_seo": image_seo,
        "internal_links": internal_links,
        "related_products": related_products,
        "score": report["score"],
        "report": report,
        # Which identifiers this run resolved from PubChem, so the admin can
        # show what was filled automatically rather than it appearing silently.
        "filled_identifiers": filled_identifiers,
        # Legacy flat fields, so this payload can prefill the existing admin
        # form and the existing renderer without a migration of live content.
        "flat": _flatten_for_legacy_fields(sections, meta_title, meta_description, image_seo),
    }


def _flatten_for_legacy_fields(sections: dict, meta_title: str, meta_description: str,
                               image_seo: dict) -> dict:
    """Project the structured sections back onto the original flat columns.

    148 published products render from `description`/`applications`/
    `safety_info`/`faqs`, and every existing consumer — the chatbot's context
    builder, the SEO audit, the sitemap — reads those. Keeping them populated
    means structured content is additive rather than a breaking change.
    """
    paragraphs = [sections.get("summary", "")]
    for item in sections.get("benefits", []):
        if item.get("detail"):
            paragraphs.append(item["detail"])
    for item in sections.get("industries", []):
        if item.get("detail"):
            paragraphs.append(item["detail"])
    description = "\n\n".join(p for p in paragraphs if p).strip()

    safety = sections.get("handling_safety", {})
    safety_parts = [safety.get("guidance", "")]
    if safety.get("ppe"):
        safety_parts.append("PPE: " + ", ".join(safety["ppe"]) + ".")
    if sections.get("storage_guidelines"):
        safety_parts.append(sections["storage_guidelines"])

    return {
        "description": description[:5000],
        # The flat column is one application per line, so only the `use` half
        # carries over — the reason lives in the structured section.
        "applications": "\n".join(application_uses(sections))[:2000],
        "safety_info": " ".join(p for p in safety_parts if p)[:2000],
        "faqs": sections.get("faqs", []),
        "meta_title": meta_title,
        "meta_description": meta_description,
        "image_alt": image_seo.get("alt", "")[:160],
    }
