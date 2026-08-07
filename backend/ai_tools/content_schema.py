"""The structured product-content contract.

The old pipeline asked the model for a bag of loose strings (`description`,
`applications`, `safety_info`) and rendered whatever came back. This module
replaces that with an explicit, section-by-section contract: what the model is
asked to produce, and — far more importantly — what is *accepted* from it.

Two rules drive every coercion helper here:

1. **Shape is enforced in code, not requested in prose.** Measured over the
   148-product catalogue, prompt-level instructions land somewhere between 26%
   and 74% compliance (see the comments in services.py). Anything the renderer
   or the schema depends on is therefore normalised here rather than trusted.

2. **An unknown is never filled in.** Every field a buyer could order against
   resolves to `NEEDS_VERIFICATION` instead of a plausible guess. CAS number
   and purity get a hard structural guard on top of that (see
   `coerce_specifications`) because they are the two fields where a confident
   wrong answer ships the wrong chemical.
"""
from __future__ import annotations

import re

# Rendered verbatim on the admin form and suppressed on the public page. The
# exact string is part of the contract: validation.py counts it, the frontend
# matches on it, and staff filter for it.
NEEDS_VERIFICATION = "Requires manual verification"


def needs_verification(value) -> bool:
    return isinstance(value, str) and value.strip() == NEEDS_VERIFICATION


# Safety detail that may only ever be transcribed from the supplier SDS. Held
# inside handling_safety, staff-entered, and rendered only when filled — an
# empty section is the correct state until someone has the document in hand.
SDS_SAFETY_FIELDS = ("first_aid", "spill_response", "transport")


# --- primitive coercion --------------------------------------------------

def _text(value, limit: int) -> str:
    """A model that has nothing to say returns None, 0, [] or "null" — none of
    which should reach a page as the literal word."""
    if value is None or isinstance(value, (list, dict, bool)):
        return ""
    out = str(value).strip()
    if out.lower() in {"null", "none", "n/a", "na", "undefined", "-"}:
        return ""
    return out[:limit]


def _str_list(value, limit: int, item_limit: int = 300) -> list[str]:
    """Accepts a list, or a newline/bullet-delimited string — models return
    both for the same field depending on how the section reads."""
    if isinstance(value, str):
        items = re.split(r"[\n\r]+|(?:^|\s)[•\-*]\s+", value)
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            # Some sections come back as [{"feature": "..."}] instead of ["..."].
            item = next((v for v in item.values() if isinstance(v, str)), "")
        text = _text(item, item_limit).lstrip("•-*• ").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:  # a repeated bullet is a defect, not content
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _pair_list(value, key_a: str, key_b: str, limit: int,
               a_limit: int = 200, b_limit: int = 1200) -> list[dict]:
    """Normalise `[{"title": ..., "detail": ...}]`-shaped sections, tolerating
    the alternative key names models reach for."""
    if not isinstance(value, (list, tuple)):
        return []
    aliases_a = (key_a, "title", "name", "heading", "label", "q", "question", "industry")
    aliases_b = (key_b, "detail", "description", "body", "text", "a", "answer", "value")
    out: list[dict] = []
    for item in value:
        if isinstance(item, str):
            # "Water Treatment: coagulant dosing" — split on the first colon.
            head, _, tail = item.partition(":")
            item = {key_a: head, key_b: tail}
        if not isinstance(item, dict):
            continue
        lowered = {str(k).lower(): v for k, v in item.items()}
        a = next((_text(lowered[k], a_limit) for k in aliases_a if lowered.get(k)), "")
        b = next((_text(lowered[k], b_limit) for k in aliases_b if lowered.get(k)), "")
        if not (a or b):
            continue
        out.append({key_a: a, key_b: b})
        if len(out) >= limit:
            break
    return out


# --- specifications ------------------------------------------------------

# Fields a buyer orders against. The model may never originate these: a wrong
# CAS number ships a different substance, and purity is a property of Karivex's
# specific stock from their specific supplier, not a public fact about the
# chemical. Both are accepted only when passed in from the Product row.
#
# Standing decision (2026-07-29): these are not bulk-filled by guessing. The
# agreed route is a staff-completed CSV sourced from supplier SDS documents.
DB_ONLY_SPEC_LABELS = {
    "cas number", "cas", "cas no", "cas registry number", "purity", "assay",
    # Formula and molecular weight look like textbook constants, and for a
    # single pure substance they are. The catalogue is not made of those: it
    # holds trade names, blends and hydrates, where the formula carries exactly
    # the ambiguity that makes CAS unsafe here. "Magnesium Sulphate" is MgSO4
    # or MgSO4·7H2O depending on which drum is in the warehouse, and only the
    # SDS says which. A formula that disagrees with the delivered material is
    # the same failure as a wrong CAS, so it follows the same rule.
    #
    # This previously disagreed with the prompt, which already told the model
    # never to originate a molecular weight. The prompt held in practice, but a
    # guarantee that depends on prompt wording is not a guarantee.
    "chemical formula", "formula", "molecular formula",
    "molecular weight", "molar mass", "formula weight",
    # Density is a constant for a solid but varies with concentration for every
    # solution in the catalogue — 98% and 30% sulphuric acid are different
    # numbers. Sourced from PubChem into the database instead.
    "density", "specific gravity", "bulk density",
    # Transport classification, not chemistry. UN number and hazard class vary
    # with concentration and packing group, they are printed on shipping
    # documents, and a wrong one is a legal and safety failure rather than a
    # content defect. Staff-entered only, same rule as CAS.
    "un number", "un no", "un", "hazard class", "hazard classification",
    "transport class", "dangerous goods class",
    "signal word", "hazard statements", "hazard statement", "ghs classification",
}

# The spec table's canonical row order. Anything the model adds beyond these is
# appended after them, so the table reads consistently across the catalogue.
SPEC_LABEL_ORDER = [
    "Grade", "Purity", "CAS Number", "Chemical Formula", "Molecular Weight",
    "Appearance", "Solubility", "Density", "UN Number", "Signal Word",
    "Hazard Class", "Hazard Statements", "Packaging", "Storage Conditions",
    "Shelf Life",
]

# Rows always present in the table, so a missing identifier shows as an
# explicit gap for staff rather than silently not existing. UN number and
# hazard class are NOT here: they apply only to regulated goods, and a
# permanent "Requires manual verification" against a non-hazardous product
# would be noise that trains staff to ignore the marker.
ALWAYS_PRESENT_SPEC_LABELS = ("CAS Number", "Chemical Formula", "Purity")
_SPEC_ORDER_INDEX = {label.lower(): i for i, label in enumerate(SPEC_LABEL_ORDER)}


def coerce_specifications(value, verified_facts: dict[str, str] | None = None) -> list[dict]:
    """Build the spec table, overwriting anything the model claimed about a
    DB-only field with the database's own value (or the verification marker).

    `verified_facts` is keyed by lowercased label and comes from the Product
    row — the only trusted source for CAS and purity.
    """
    verified_facts = {k.lower(): v for k, v in (verified_facts or {}).items() if v}
    rows: list[dict] = []
    seen: set[str] = set()

    raw = value if isinstance(value, (list, tuple)) else []
    if isinstance(value, dict):  # {"Purity": "98%"} instead of a list of rows
        raw = [{"label": k, "value": v} for k, v in value.items()]

    for item in raw:
        if not isinstance(item, dict):
            continue
        lowered = {str(k).lower(): v for k, v in item.items()}
        label = _text(
            next((lowered[k] for k in ("label", "name", "field", "property", "key")
                  if lowered.get(k)), ""), 80)
        raw_value = _text(
            next((lowered[k] for k in ("value", "spec", "detail", "content")
                  if lowered.get(k)), ""), 300)
        # A label carrying a pipe or running long is the schema hint's own list
        # of allowed property names echoed back as a single row — observed in
        # the first live run, which produced one row labelled
        # "Grade | Chemical Formula | Molecular Weight | Appearance | ...".
        # The prompt now forbids it; this drops it whatever the model does.
        if not label or "|" in label or len(label) > 40 or label.lower() in seen:
            continue
        seen.add(label.lower())

        # The database always wins where it holds a value — for every label,
        # not just the DB-only ones. A staff-entered chemical formula must not
        # be overwritten by the model's guess at it.
        trusted = verified_facts.get(label.lower(), "")
        if trusted:
            rows.append({"label": label, "value": trusted, "verified": True})
            continue
        if label.lower() in DB_ONLY_SPEC_LABELS:
            # No database value, and the model may never originate one here.
            rows.append({"label": label, "value": NEEDS_VERIFICATION, "verified": False})
            continue
        rows.append({"label": label, "value": raw_value or NEEDS_VERIFICATION,
                     "verified": bool(raw_value)})

    # Guarantee the core identifier rows exist even when the model omitted
    # them — a missing CAS row hides the gap; a marked one prompts staff to
    # fill it. UN number and hazard class are added only when the database
    # actually holds one (see ALWAYS_PRESENT_SPEC_LABELS).
    for label in ALWAYS_PRESENT_SPEC_LABELS:
        if label.lower() in seen:
            continue
        trusted = verified_facts.get(label.lower(), "")
        rows.append({"label": label, "value": trusted or NEEDS_VERIFICATION,
                     "verified": bool(trusted)})
    for label in ("UN Number", "Hazard Class"):
        trusted = verified_facts.get(label.lower(), "")
        if trusted and label.lower() not in seen:
            rows.append({"label": label, "value": trusted, "verified": True})

    rows.sort(key=lambda r: _SPEC_ORDER_INDEX.get(r["label"].lower(), len(SPEC_LABEL_ORDER)))
    return rows[:20]


# --- content that says nothing -------------------------------------------
#
# Everything below is enforced here rather than asked for in the prompt. All
# three were forbidden in the prompt first, and all three came back anyway on
# the very next run: the model reproduced "Comprehensive Documentation" on 4 of
# 22 products, restated the minimum-order question as its own answer on 9, and
# on one product wrote the verification marker into a customer-facing bullet.

# Vocabulary that carries no product-specific content. A benefit title built
# ENTIRELY from these words could head any page in the catalogue — which is
# what makes it duplicate content rather than a benefit. Checking the whole
# title against a word list, instead of matching fixed phrases, is what
# separates "Reliable Supply Chain" and "Convenient Packaging Size" from
# "Efficient Coagulation" and "High Adsorption Efficiency", which name what the
# material actually does.
_GENERIC_TITLE_WORDS = frozenset("""
and or of the for a an in to with your our
reliable reliability supply supplies supplier sourcing chain stock stocks level levels
comprehensive complete full documentation documents paperwork
operational operations efficiency efficient effective effectiveness
cost costs pricing price competitive affordable value
quick fast prompt rapid speedy delivery dispatch lead time times
easy easily simple convenient convenience handling handle use usage
quality assurance assured consistent consistency trusted guaranteed
safety safe compliance compliant regulatory standards
wide broad availability available access
versatile versatility flexible flexibility
packaging packs pack size sizes bulk
favorable favourable physical properties property characteristics
support service assistance expertise
""".split())


def is_generic_benefit_title(title: str) -> bool:
    """True when every word in a benefit heading is business boilerplate."""
    words = re.findall(r"[a-z]+", (title or "").lower())
    return bool(words) and all(word in _GENERIC_TITLE_WORDS for word in words)


def is_non_answer(question: str, answer: str) -> bool:
    """True when an answer only restates its question.

    "What is the minimum order quantity?" answered with "Please contact us for
    information on minimum order quantities" publishes as FAQPage structured
    data, so a search result ends up showing a non-answer. That is strictly
    worse than not asking the question at all.

    Words match on a five-character prefix so quantity/quantities counts as the
    same word rather than reading as new content.
    """
    stopwords = _FAQ_STOPWORDS

    def tokens(text: str) -> list[str]:
        return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
                if w not in stopwords]

    asked = {w[:5] for w in tokens(question)}
    answered = tokens(answer)
    if not answered:
        return True
    novel = [w for w in answered if w[:5] not in asked]
    return len(novel) <= 2 and len(answered) <= 14


_FAQ_STOPWORDS = frozenset((
    "a an and are as at be by can do does for from has have how i in is it its of on or "
    "our please that the their there these this to us we what when where which who why "
    "will with you your").split())


def _drops_marker(text: str) -> bool:
    """The verification marker is an instruction to staff. It must never reach
    a buyer outside the specification table, where the renderer suppresses it —
    a bullet reading "Requires manual verification for purity" is published
    prose, and nothing downstream would catch it."""
    return NEEDS_VERIFICATION.lower() in (text or "").lower()


# --- key features --------------------------------------------------------

# Labels that restate something the page already shows elsewhere: availability
# has its own row in the spec table, delivery has its own section.
_REDUNDANT_FEATURE_LABELS = {
    "stock status", "availability", "delivery", "delivery time", "lead time",
}


def dedupe_key_features(features: list[str], specifications: list[dict]) -> list[str]:
    """Drop "Label: value" bullets that just repeat the specification table.

    Key features renders directly above that table, and the generator was
    filling it from the same rows — "Chemical formula: IK", "Molecular weight:
    166.0028 g/mol", "Stock status: In stock". Measured across the first 25
    generated products, "Packaging" led 8 of them, "Stock status" 7 and
    "Delivery" 6. Restating the table earns nothing and pushes the genuinely
    distinguishing bullets down the page. Prose bullets are left alone.
    """
    labels = {row.get("label", "").strip().lower() for row in specifications}
    labels |= _REDUNDANT_FEATURE_LABELS
    out: list[str] = []
    for feature in features:
        if _drops_marker(feature):
            continue
        label, separator, _ = feature.partition(":")
        if separator and label.strip().lower() in labels:
            continue
        out.append(feature)
    return out


# --- section coercion ----------------------------------------------------

def coerce_sections(data: dict, verified_facts: dict[str, str] | None = None,
                    preserved: dict | None = None) -> dict:
    """Normalise the model's section payload into the stored contract.

    Missing sections come back as empty containers rather than absent keys, so
    the renderer and the admin form can both assume the shape exists.

    `preserved` is the product's EXISTING handling_safety block. The SDS fields
    in it are staff-authored and survive regeneration untouched.
    """
    data = data if isinstance(data, dict) else {}
    preserved = preserved if isinstance(preserved, dict) else {}
    specifications = coerce_specifications(data.get("specifications"), verified_facts)
    return {
        "summary": _text(data.get("summary"), 1500),
        "key_features": dedupe_key_features(
            _str_list(data.get("key_features"), 10), specifications),
        # A heading that fits every product in the catalogue is dropped rather
        # than published — the prompt bans them and the model writes them
        # anyway.
        "benefits": [b for b in _pair_list(data.get("benefits"), "title", "detail", 8)
                     if not is_generic_benefit_title(b["title"])],
        "specifications": specifications,
        "available_grades": _str_list(data.get("available_grades"), 6, 80),
        # Which grade this listing IS, so a buyer does not order the wrong
        # material off a one-item "Available grades" list.
        "grades_note": _text(data.get("grades_note"), 600),
        "packaging_options": _str_list(data.get("packaging_options"), 8, 120),
        # Pairs, not strings. As a flat list this section could only ever be
        # "Used in analytical chemistry" — the use without the reason, which is
        # the part a buyer is actually reading for. `_pair_list` accepts the
        # legacy list-of-strings shape, so products generated before this
        # still resolve (the use survives, `why` comes back empty).
        "applications": [a for a in _pair_list(data.get("applications"), "use", "why", 12, 200, 900)
                         if not (_drops_marker(a["use"]) or _drops_marker(a["why"]))],
        "industries": _pair_list(data.get("industries"), "name", "detail", 10),
        "storage_guidelines": _text(data.get("storage_guidelines"), 1500),
        "handling_safety": {
            "guidance": _text((data.get("handling_safety") or {}).get("guidance")
                              if isinstance(data.get("handling_safety"), dict)
                              else data.get("handling_safety"), 2000),
            "ppe": _str_list(
                (data.get("handling_safety") or {}).get("ppe")
                if isinstance(data.get("handling_safety"), dict) else None, 8, 120),
            # First aid, spill response and transport classification, copied
            # from the supplier SDS by staff. The model is never asked for
            # these and cannot originate them: a wrong first-aid instruction
            # injures someone, and a wrong transport class is a legal failure
            # — the same reasoning that keeps CAS and UN number out of its
            # hands, applied to the fields where being wrong hurts most.
            #
            # `preserved` carries the staff-entered text through a
            # regeneration, which would otherwise wipe it: the model's payload
            # has no such key, so coercion would resolve it to "".
            **{field: _text((preserved or {}).get(field), 1200)
               for field in SDS_SAFETY_FIELDS},
        },
        # "When is this the right choice?" — the question a buyer comparing
        # options actually has. Factual only: it may describe what a material
        # does well and where a different chemistry is normally used, never
        # disparage a named product or claim superiority.
        "typical_uses": _pair_list(data.get("typical_uses"), "scenario", "guidance", 6),
        # A question whose answer restates it is dropped, not published: it
        # goes out as FAQPage structured data, so the non-answer is what a
        # search result shows.
        "faqs": [f for f in _pair_list(data.get("faqs"), "q", "a", 8, 300, 1200)
                 if not is_non_answer(f["q"], f["a"])],
        "cta": {
            "headline": _text((data.get("cta") or {}).get("headline")
                              if isinstance(data.get("cta"), dict) else None, 160),
            "body": _text((data.get("cta") or {}).get("body")
                          if isinstance(data.get("cta"), dict) else None, 600),
        },
    }


# --- SEO assets ----------------------------------------------------------

_KEYWORD_GROUPS = (
    ("secondary_keywords", 8),
    ("semantic_keywords", 12),
    ("long_tail_keywords", 8),
    ("buyer_intent_keywords", 8),
    ("geographic_keywords", 8),
)


def coerce_seo(data: dict) -> dict:
    """Normalise the SEO asset block.

    `meta_title` and `meta_description` are deliberately NOT finalised here —
    services.enforce_meta_title/_description own those, because they carry
    measured repair logic (filler-verb stripping, geo-term injection) that must
    run last, after any expansion pass has settled the copy.
    """
    data = data if isinstance(data, dict) else {}
    headings = []
    for item in (data.get("headings") or [])[:12]:
        if isinstance(item, str):
            headings.append({"h2": _text(item, 160), "h3": []})
        elif isinstance(item, dict):
            lowered = {str(k).lower(): v for k, v in item.items()}
            h2 = _text(lowered.get("h2") or lowered.get("heading") or lowered.get("title"), 160)
            if h2:
                headings.append({"h2": h2, "h3": _str_list(lowered.get("h3"), 6, 160)})

    out = {
        "h1": _text(data.get("h1"), 200),
        "focus_keyword": _text(data.get("focus_keyword"), 100).lower(),
        "headings": headings,
        "external_references": [],
    }
    for key, cap in _KEYWORD_GROUPS:
        out[key] = [k.lower() for k in _str_list(data.get(key), cap, 100)]

    # External references are the one place the model can emit a URL. An
    # invented citation is worse than none, so only well-known reference
    # domains survive — anything else is dropped rather than shown to staff as
    # a link worth adding.
    for item in (data.get("external_references") or [])[:6]:
        if not isinstance(item, dict):
            continue
        lowered = {str(k).lower(): v for k, v in item.items()}
        url = _text(lowered.get("url"), 300)
        title = _text(lowered.get("title") or lowered.get("name"), 200)
        if url and _is_allowed_reference(url):
            out["external_references"].append({"title": title or url, "url": url})
    return out


# Authoritative, stable chemical-reference sources. A link to a competitor or
# to a hallucinated URL earns nothing and can leak equity, so the allowlist is
# deliberately short rather than a general URL validator.
_REFERENCE_HOSTS = (
    "pubchem.ncbi.nlm.nih.gov", "echa.europa.eu", "cdc.gov", "osha.gov",
    "who.int", "fao.org", "epa.gov", "nist.gov", "inchem.org",
)


def _is_allowed_reference(url: str) -> bool:
    match = re.match(r"https://([^/]+)/?", url.strip(), re.I)
    if not match:
        return False
    host = match.group(1).lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in _REFERENCE_HOSTS)


def coerce_image_seo(data: dict, product_name: str = "") -> dict:
    """Alt/title/caption/filename for the product photo."""
    data = data if isinstance(data, dict) else {}
    filename = _text(data.get("filename") or data.get("file_name"), 120)
    if filename:
        filename = re.sub(r"[^a-z0-9.-]+", "-", filename.lower()).strip("-")
        if not filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            filename = re.sub(r"\.[a-z0-9]{1,5}$", "", filename) + ".jpg"
    return {
        "alt": _text(data.get("alt") or data.get("image_alt"), 160),
        "title": _text(data.get("title"), 160) or product_name,
        "caption": _text(data.get("caption"), 300),
        "filename": filename,
    }


# --- company facts (never AI-originated) ---------------------------------

def company_facts(site: dict) -> dict:
    """Trust/delivery/credibility claims, read from configured business data.

    These are the claims most likely to be fabricated ("ISO 9001 certified",
    "over 20 years of experience") and the most damaging to get wrong, so they
    are assembled from settings.SITE rather than generated. The model is shown
    this block as fact and told not to add to it.
    """
    regions = [r for r in (site.get("regions") or []) if r]
    return {
        "company": site.get("name", ""),
        "regions": regions,
        "delivery": [d for d in (site.get("delivery_nairobi", ""),
                                 site.get("delivery_regional", "")) if d],
        "documentation": site.get("certifications", ""),
        "hours": site.get("hours", ""),
        "phone": site.get("phone", ""),
        "email": site.get("email", ""),
    }


def why_choose_us(site: dict) -> list[str]:
    """Deterministic 'Why Choose Us' bullets built only from configured facts.

    Deliberately not a model output. Every bullet traces to a value in
    settings.SITE, so the section can never claim a certification the business
    does not hold.
    """
    facts = company_facts(site)
    out: list[str] = []

    # E-E-A-T signals, each rendered ONLY when configured. Blank by default:
    # an unset founding year or certification simply produces no bullet, which
    # is the correct behaviour — these are the claims where inventing one is
    # most damaging, and the absence of a bullet costs far less than a false
    # one. Set them in .env once you can evidence them.
    from datetime import date

    if site.get("founded_year"):
        try:
            years = date.today().year - int(site["founded_year"])
            if years > 0:
                out.append(f"Supplying industrial chemicals since {site['founded_year']} "
                           f"— {years} years in the trade.")
        except (TypeError, ValueError):
            pass
    if site.get("industries_served"):
        out.append("Serving " + ", ".join(site["industries_served"]) + ".")
    if facts["regions"]:
        out.append(f"Direct supply across {', '.join(facts['regions'])}.")
    out.extend(facts["delivery"])
    if facts["documentation"]:
        out.append(facts["documentation"])
    if site.get("quality_statement"):
        out.append(site["quality_statement"])
    if site.get("compliance"):
        out.append(site["compliance"])
    if facts["hours"]:
        out.append(f"Technical and sales support {facts['hours']}.")
    out.append("Bulk and repeat-order pricing quoted per consignment.")
    return out
