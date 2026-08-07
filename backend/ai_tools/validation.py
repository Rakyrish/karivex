"""Pre-publication validation and SEO quality scoring for structured content.

Every check here exists because prompt instructions alone did not hold. The
generation prompts already ask for correct lengths, unique phrasing and no
invented credentials; measured compliance on the previous catalogue ran between
26% and 74% depending on the field. This module is the gate that runs
afterwards, so the guarantee does not depend on which model produced the text
or how it drifts.

Issues carry a severity:

* ``error``   — blocks publishing. Something is missing, fabricated, or
                structurally wrong.
* ``warning`` — publishable, but the page is weaker for it. Verification
                markers land here: an honestly-marked gap is a to-do, not a
                defect.

`score_content` returns 0-100. It is a measure of *this page's* on-page
completeness, not a ranking prediction — structured data and on-page hygiene
are eligibility and CTR factors, not ranking factors, and the score should
never be presented to staff as "how well this will rank".
"""
from __future__ import annotations

import re

from . import keywords as kw_engine
from .content_schema import (
    NEEDS_VERIFICATION, is_generic_benefit_title, is_non_answer, needs_verification,
)

# Which prose surfaces get scanned for stuffing, and the label used when one
# is reported. Lists are joined before analysis: a phrase repeated once in
# every bullet is exactly the pattern a per-bullet check would miss.
STUFFABLE_SECTIONS = (
    ("summary", "Product summary"),
    ("key_features", "Key features"),
    ("benefits", "Benefits"),
    ("applications", "Applications"),
    ("industries", "Industries served"),
    ("typical_uses", "Typical industrial uses"),
    ("faqs", "FAQs"),
    ("storage_guidelines", "Storage guidelines"),
    ("cta", "Call to action"),
)


def section_text(sections: dict, key: str) -> str:
    """Flatten one section to plain prose for density analysis."""
    value = (sections or {}).get(key)
    return " ".join(iter_text(value))

# --- claims the business must be able to substantiate --------------------
#
# These are the fabrications with real consequences: a buyer choosing a food or
# pharma supplier on a certification claim, or a regulator reading it. The
# model is told not to write them; this catches it when it does anyway.
_UNSUPPORTED_CLAIM_PATTERNS = (
    (re.compile(r"\bISO[\s-]?\d{4,5}\b", re.I), "an ISO certification"),
    (re.compile(r"\b(?:FDA|EPA|KEBS|NEMA|USP|BP|EP)[\s-]?(?:approved|certified|registered|compliant)\b", re.I),
     "a regulatory approval"),
    (re.compile(r"\b(?:GMP|HACCP|HALAL|KOSHER|REACH)[\s-]?(?:certified|compliant|approved)\b", re.I),
     "a compliance certification"),
    (re.compile(r"\bover \d+\+? years(?: of)? experience\b", re.I), "a company age claim"),
    (re.compile(r"\b(?:cheapest|lowest price|best price|number one|no\.?\s?1|market leader|"
                r"largest supplier|leading supplier)\b", re.I), "a superlative market claim"),
    (re.compile(r"\b(?:guarantee[ds]?|guaranteed)\s+(?:purity|quality|delivery|results)\b", re.I),
     "a guarantee"),
    (re.compile(r"\b(?:cures?|treats?|prevents?)\s+(?:disease|illness|infection)\b", re.I),
     "a medical claim"),
)

# Functional-role claims about the SUBSTANCE, as opposed to the certification
# patterns above, which are claims about the company. These are the errors a
# technical buyer spots first, and the first structured run shipped two of them
# on one page: potassium iodide described as "a pharmaceutical excipient" (it is
# an active ingredient, not an excipient) and as "a nutrient in fertilizers to
# promote plant growth" (iodine is not a plant nutrient — agricultural iodine is
# biofortification and livestock supplementation).
#
# A regex cannot judge whether a role is CORRECT, so these are flagged for a
# human rather than rewritten — the same treatment the ISO patterns get.
# Anything the product's own database record already states is suppressed via
# `supported`, so a genuinely food-grade product does not flag "food additive".
_ROLE_CLAIM_PATTERNS = (
    (re.compile(r"\bexcipients?\b", re.I), "a formulation-role claim"),
    (re.compile(r"\bactive pharmaceutical ingredients?\b", re.I), "a drug-role claim"),
    (re.compile(r"\b(?:plant|essential|primary|key)\s+nutrients?\b", re.I),
     "a plant-nutrition claim"),
    (re.compile(r"\bnutrients?\s+in\s+fertili[sz]ers?\b", re.I), "a plant-nutrition claim"),
    (re.compile(r"\bpromotes?\s+plant\s+growth\b", re.I), "a plant-nutrition claim"),
    (re.compile(r"\b(?:food|feed)\s+additive\b", re.I), "a food/feed-role claim"),
    (re.compile(r"\bdietary supplements?\b", re.I), "a supplement-role claim"),
)

# Formulaic connectives. Duplicated intent with services.BANNED_PROSE_PHRASES,
# which runs at generation time on the description; this pass covers every
# structured section, which that one never sees.
_FILLER_PATTERNS = (
    re.compile(r"\b(?:furthermore|moreover|additionally|in addition|in conclusion|"
               r"it is important to note|it is worth noting|in today'?s world|"
               r"when specifying or)\b", re.I),
    re.compile(r"\b(?:versatile|many different uses|state[- ]of[- ]the[- ]art|"
               r"cutting[- ]edge|high[- ]quality product|superior quality)\b", re.I),
    # The vague-quantifier family. The first live pilot shipped "various
    # industrial applications" across the sulphuric acid page — the old
    # pattern only listed "various industries" and "wide range of
    # applications", so the exact phrasing that appeared slipped through.
    # Matched generically now: any vague quantifier attached to a noun a buyer
    # wanted the specifics of.
    re.compile(r"\b(?:various|a\s+(?:wide\s+)?(?:range|variety)\s+of|numerous|many|"
               r"multiple|several|different|a\s+number\s+of)\s+"
               # Up to three intervening adjectives — "various pharmaceutical
               # and industrial applications" got past the narrower version.
               r"(?:\w+\s+){0,3}"
               r"(?:applications?|industries|uses|sectors|purposes|needs|fields)\b", re.I),
)

# Surfaces beyond the content sections that must also be free of filler. The
# meta description is the highest-value text on the page and was never being
# scanned; the image caption feeds alt/caption text that Google reads too.
def _extra_filler_surfaces(meta_title: str, meta_description: str, image_seo: dict) -> list[str]:
    return [t for t in (meta_title, meta_description,
                        (image_seo or {}).get("caption", ""),
                        (image_seo or {}).get("alt", "")) if t]

# Coercion already drops interchangeable benefit headings and question-
# restating answers before they are stored. These stay as a second pass because
# staff edit sections by hand in the admin, which never goes through coercion.
_REQUIRED_SECTIONS = (
    ("summary", "Product summary"),
    ("key_features", "Key features"),
    ("specifications", "Technical specifications"),
    ("applications", "Applications"),
    ("industries", "Industries served"),
    ("storage_guidelines", "Storage guidelines"),
    ("faqs", "FAQs"),
)

# Benefits is deliberately NOT required, and the reason is worth keeping:
# coercion drops interchangeable headings, so on a product where the model
# produced nothing but boilerplate the section comes back empty. Requiring it
# then blocked the page over a section the pipeline had itself just emptied —
# 2 of the first 12 products in the full-catalogue run were held that way, each
# with no other error. Holding a whole page for that is the wrong trade: the
# rest of the content is good, and the alternative is the product keeps
# rendering from its flat fields. It warns instead, so the gap is visible and
# someone can write real benefits.
_BENEFITS_SECTION = ("benefits", "Benefits")

_REQUIRED_SEO = (
    ("h1", "H1"),
    ("focus_keyword", "Focus keyword"),
    ("secondary_keywords", "Secondary keywords"),
    ("buyer_intent_keywords", "Buyer-intent keywords"),
    ("geographic_keywords", "Geographic keywords"),
)


def iter_text(payload) -> list[str]:
    """Every human-readable string in a nested payload, verification markers
    excluded — a marker is a deliberate placeholder and must not count towards
    word count, repetition, or claim scanning."""
    out: list[str] = []
    if isinstance(payload, str):
        if payload.strip() and not needs_verification(payload):
            out.append(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            out.extend(iter_text(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            out.extend(iter_text(item))
    return out


def word_count(payload) -> int:
    return sum(len(t.split()) for t in iter_text(payload))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def repetition_ratio(texts: list[str]) -> float:
    """Fraction of repeated 5-word shingles across the whole page.

    Catches the failure mode the section split introduced: the same sentence
    about 25 kg bags appearing in the summary, the features list and the
    packaging section, which reads as padding to a buyer and as thin content
    to Google.
    """
    words = re.findall(r"[a-z0-9]+", " ".join(texts).lower())
    if len(words) < 40:
        return 0.0
    shingles = [" ".join(words[i:i + 5]) for i in range(len(words) - 4)]
    if not shingles:
        return 0.0
    return 1.0 - (len(set(shingles)) / len(shingles))


def duplicate_openings(texts: list[str]) -> list[str]:
    """Sentence openings (first three words) used three or more times."""
    counts: dict[str, int] = {}
    for text in texts:
        for sentence in _sentences(text):
            opening = " ".join(sentence.split()[:3]).lower()
            if len(opening.split()) == 3:
                counts[opening] = counts.get(opening, 0) + 1
    return sorted(k for k, v in counts.items() if v >= 3)


def _scan_claims(texts: list[str], patterns, supported: str) -> list[str]:
    supported_low = (supported or "").lower()
    found: list[str] = []
    for text in texts:
        for pattern, label in patterns:
            for match in pattern.findall(text):
                phrase = match if isinstance(match, str) else match[0]
                if phrase.lower() in supported_low:
                    continue
                entry = f"{label}: “{phrase.strip()}”"
                if entry not in found:
                    found.append(entry)
    return found


def find_unsupported_claims(texts: list[str], supported: str = "") -> list[str]:
    """Claims needing substantiation that the configured company facts do not
    already make. A claim Karivex genuinely publishes in its own site settings
    is not a fabrication, so `supported` suppresses those."""
    return _scan_claims(texts, _UNSUPPORTED_CLAIM_PATTERNS, supported)


def find_role_claims(texts: list[str], supported: str = "") -> list[str]:
    """Functional-role claims about the substance itself.

    `supported` is the product's OWN database record — name, category, grade
    and staff-written description. A role the business has already vouched for
    there is not the model's invention and is not flagged.
    """
    return _scan_claims(texts, _ROLE_CLAIM_PATTERNS, supported)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def validate_keyword_strategy(*, plan: dict, seo: dict, sections: dict, meta_title: str,
                              meta_description: str, slug: str) -> tuple[list[dict], dict]:
    """Keyword quality control: coverage, placement, density and stuffing.

    Stuffing is an `error` — it is the one keyword defect that makes a page
    actively worse than having no keyword strategy at all, and the pipeline can
    repair it automatically, so there is no reason to let it publish. Thin
    coverage and imperfect placement are `warning`s: the page still helps a
    buyer.
    """
    issues: list[dict] = []

    def add(severity: str, field: str, message: str) -> None:
        issues.append({"severity": severity, "field": field, "message": message})

    if not plan.get("primary"):
        add("error", "focus_keyword", "No primary keyword could be determined.")
        return issues, {}

    # --- group coverage ---
    for group, (low, high) in kw_engine.GROUP_TARGETS.items():
        found = list(seo.get(group) or [])
        if len(found) < low:
            add("warning", group,
                f"{group.replace('_', ' ')}: {len(found)} of {low} minimum.")
        elif len(found) > high:
            add("warning", group, f"{group.replace('_', ' ')}: {len(found)} exceeds the {high} cap.")

    # --- one phrase, one group ---
    seen: dict[str, str] = {}
    for group in kw_engine.GROUP_PRIORITY:
        for phrase in seo.get(group) or []:
            if phrase in seen:
                add("warning", group,
                    f"“{phrase}” appears in both {seen[phrase]} and {group.replace('_', ' ')}.")
            else:
                seen[phrase] = group.replace("_", " ")

    # --- geography must match real delivery areas ---
    allowed = {p.lower() for p in plan["geo"]["all"]}
    for phrase in seo.get("geographic_keywords") or []:
        if not any(place in phrase for place in allowed):
            add("error", "geographic_keywords",
                f"“{phrase}” names a location outside the configured delivery areas.")

    # --- primary keyword placement ---
    placement = kw_engine.primary_placement(
        plan=plan, meta_title=meta_title, meta_description=meta_description,
        h1=seo.get("h1", ""), slug=slug,
        summary=(sections or {}).get("summary", ""),
        cta=section_text(sections, "cta"),
    )
    # The slug is reported but never enforced — renaming a live URL to fit a
    # keyword costs every existing inbound link and bookmark.
    critical = ("meta_title", "h1", "first_100_words", "meta_description")
    for surface in critical:
        if not placement.get(surface):
            add("warning", "focus_keyword",
                f"Primary keyword “{plan['primary']}” is not present in the {surface.replace('_', ' ')}.")

    # --- density and stuffing, section by section ---
    analyses: dict[str, dict] = {}
    stuffed: list[str] = []
    for key, label in STUFFABLE_SECTIONS:
        text = section_text(sections, key)
        if not text:
            continue
        analysis = kw_engine.analyse_section(text, plan, seo)
        analyses[key] = analysis
        if analysis["splices"]:
            add("error", key,
                f"{label}: search queries pasted verbatim into prose — "
                + ", ".join(f"“{s}”" for s in analysis["splices"][:3]))
        if kw_engine.is_stuffed(analysis):
            stuffed.append(key)
            if analysis["overused"]:
                add("error", key,
                    f"{label}: over-repeated — " + ", ".join(f"“{p}”" for p in analysis["overused"][:3]))
            elif not analysis["splices"]:
                add("error", key,
                    f"{label}: keyword density {analysis['total_density']}% exceeds "
                    f"{kw_engine.MAX_TOTAL_KEYWORD_DENSITY}%.")

    metrics = {
        "primary_keyword": plan["primary"],
        "placement": placement,
        "group_counts": {g: len(seo.get(g) or []) for g in kw_engine.GROUP_TARGETS},
        "section_density": {k: v["total_density"] for k, v in analyses.items()},
        "stuffed_sections": stuffed,
        "geo_allowed": sorted(allowed),
    }
    return issues, metrics


def validate_content(
    *,
    sections: dict,
    seo: dict,
    image_seo: dict,
    meta_title: str = "",
    meta_description: str = "",
    product_name: str = "",
    supported_claims: str = "",
    product_record: str = "",
    internal_links: list | None = None,
    plan: dict | None = None,
    slug: str = "",
) -> dict:
    """Full pre-publication check.

    Returns ``{"score", "issues", "metrics", "publishable"}``. `publishable` is
    false whenever any ``error`` issue is present — the admin UI gates the
    "apply to product" action on it.
    """
    sections = sections or {}
    seo = seo or {}
    image_seo = image_seo or {}
    internal_links = internal_links or []
    issues: list[dict] = []

    def add(severity: str, field: str, message: str) -> None:
        issues.append({"severity": severity, "field": field, "message": message})

    texts = iter_text(sections)
    words = word_count(sections)
    kw = (seo.get("focus_keyword") or "").strip().lower()

    # --- completeness ---
    for key, label in _REQUIRED_SECTIONS:
        if not sections.get(key):
            add("error", key, f"{label} is missing.")
    for key, label in _REQUIRED_SEO:
        if not seo.get(key):
            add("error", key, f"{label} is missing.")

    faqs = sections.get("faqs") or []
    if 0 < len(faqs) < 5:
        add("warning", "faqs", f"Only {len(faqs)} FAQs — aim for 5-7 buyer-focused questions.")

    # A warning, not an error: this section helps a comparing buyer but a page
    # without it is still complete and useful.
    if not sections.get("typical_uses"):
        add("warning", "typical_uses",
            "No “typical industrial uses” guidance — buyers comparing options have "
            "nothing telling them when this product is the right choice.")

    # --- metadata lengths. Google truncates near these; the enforcement
    # helpers in services.py should already guarantee them, so a failure here
    # means something bypassed them. ---
    if not meta_title:
        add("error", "meta_title", "SEO title is missing.")
    elif not 40 <= len(meta_title) <= 60:
        add("warning", "meta_title", f"SEO title is {len(meta_title)} characters (aim for 40-60).")
    if not meta_description:
        add("error", "meta_description", "Meta description is missing.")
    elif not 120 <= len(meta_description) <= 160:
        add("warning", "meta_description",
            f"Meta description is {len(meta_description)} characters (aim for 150-160).")

    # Keyword placement. Skipped entirely when a keyword plan is supplied,
    # because validate_keyword_strategy() below does this properly across every
    # surface — running both double-reported the same defect.
    #
    # Matching is on the keyword's WORDS, not the literal phrase. The first
    # live run warned on all five products that "sulphuric acid kenya" was
    # missing from a description reading "Sulphuric acid supplied across
    # Kenya" — which is the better copy. A checker that penalises good prose
    # trains staff to write query-shaped text, the exact defect this codebase
    # spent two rounds removing.
    if kw and not plan:
        tokens = [t for t in re.findall(r"[a-z0-9]+", kw) if t not in {"in", "for", "the"}]

        def covers(text: str) -> bool:
            low = " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))
            return bool(tokens) and all(
                re.search(kw_engine.token_regex(t), low) for t in tokens
            )

        if not covers(meta_title):
            add("warning", "meta_title", f"Focus keyword “{kw}” is not reflected in the SEO title.")
        if not covers(meta_description):
            add("warning", "meta_description",
                f"Focus keyword “{kw}” is not reflected in the meta description.")
        if not covers(sections.get("summary") or ""):
            add("warning", "summary",
                "The opening summary does not cover the focus keyword's subject.")

    # --- depth ---
    if words < 450:
        add("warning" if words >= 300 else "error", "summary",
            f"Total content is {words} words — thin for a competitive product page (aim 600+).")

    # --- image SEO ---
    if not image_seo.get("alt"):
        add("error", "image_seo", "Image alt text is missing.")
    elif len(image_seo["alt"]) > 160:
        add("warning", "image_seo", "Image alt text is over 160 characters.")

    # --- internal linking ---
    if not internal_links:
        add("warning", "internal_links",
            "No internal links suggested — the page has no lateral crawl path.")

    # --- originality / tone ---
    ratio = repetition_ratio(texts)
    if ratio > 0.18:
        add("error" if ratio > 0.30 else "warning", "content",
            f"{ratio * 100:.0f}% of phrasing repeats across sections.")
    openings = duplicate_openings(texts)
    if openings:
        add("warning", "content",
            "Repeated sentence openings: " + ", ".join(f"“{o}…”" for o in openings[:4]))
    scanned = texts + _extra_filler_surfaces(meta_title, meta_description, image_seo)
    filler = sorted({m.group(0).lower() for p in _FILLER_PATTERNS for t in scanned
                     for m in p.finditer(t)})
    if filler:
        add("warning", "content",
            "Vague or filler phrasing — name the actual industries/applications instead: "
            + ", ".join(f"“{f}”" for f in filler[:6]))

    # --- fabrication ---
    claims = find_unsupported_claims(texts, supported_claims)
    for claim in claims:
        add("error", "content", f"Unsupported claim — remove or substantiate {claim}.")

    role_claims = find_role_claims(texts, product_record)
    for claim in role_claims:
        add("error", "content",
            f"Unverified role for this substance — {claim}. Confirm against the supplier "
            "SDS/technical data sheet or reword; misclassifying what a chemical DOES is "
            "the error a technical buyer notices first.")

    # --- sections that exist but say nothing ---
    if not sections.get("benefits"):
        add("warning", "benefits",
            "No benefits section — every heading the generator produced was "
            "interchangeable boilerplate and was dropped. Write two or three that name "
            "the property or service responsible, or leave the section off the page.")

    generic_benefits = [
        (b.get("title") or "").strip() for b in (sections.get("benefits") or [])
        if is_generic_benefit_title(b.get("title") or "")
    ]
    if generic_benefits:
        add("warning", "benefits",
            "Interchangeable benefit heading(s) — "
            + ", ".join(f"“{t}”" for t in generic_benefits)
            + ". Name the property or service responsible for the benefit instead; a "
              "heading that fits every product in the catalogue is duplicate content.")

    non_answers = [(f.get("q") or "").strip() for f in (sections.get("faqs") or [])
                   if is_non_answer(f.get("q", ""), f.get("a", ""))]
    if non_answers:
        add("warning", "faqs",
            "FAQ answer only restates the question — "
            + ", ".join(f"“{q}”" for q in non_answers)
            + ". This publishes as FAQ structured data, so a search result shows the "
              "non-answer. Answer it from the product facts, or ask a different question.")

    # The marker is staff-facing. The renderer suppresses it in the spec table,
    # but nothing suppresses it inside a sentence — one product published the
    # bullet "Requires manual verification for purity and regulatory details."
    leaked = [t for t in iter_text({k: v for k, v in sections.items()
                                    if k != "specifications"})
              if NEEDS_VERIFICATION.lower() in t.lower()]
    if leaked:
        add("error", "content",
            f"“{NEEDS_VERIFICATION}” written into published prose — "
            + "; ".join(f"“{t[:70]}”" for t in leaked[:3])
            + ". That marker is a note to staff and must never render to a buyer.")

    # --- verification debt (a warning by design, never an error) ---
    pending = [row["label"] for row in (sections.get("specifications") or [])
               if needs_verification(row.get("value"))]
    if pending:
        add("warning", "specifications",
            f"{NEEDS_VERIFICATION} — {', '.join(pending)}. Fill from the supplier SDS/COA "
            "before publishing; never estimate these.")

    # --- keyword strategy ---
    keyword_metrics: dict = {}
    if plan:
        keyword_issues, keyword_metrics = validate_keyword_strategy(
            plan=plan, seo=seo, sections=sections, meta_title=meta_title,
            meta_description=meta_description, slug=slug,
        )
        issues.extend(keyword_issues)

    metrics = {
        "word_count": words,
        "repetition_ratio": round(ratio, 4),
        "faq_count": len(faqs),
        "filler_hits": len(filler),
        "generic_benefits": len(generic_benefits),
        "non_answer_faqs": len(non_answers),
        "unsupported_claims": len(claims) + len(role_claims),
        "role_claims": len(role_claims),
        "pending_verification": pending,
        "sections_present": sum(1 for k, _ in _REQUIRED_SECTIONS if sections.get(k)),
        "sections_required": len(_REQUIRED_SECTIONS),
        "keywords": keyword_metrics,
    }
    score = score_content(sections=sections, seo=seo, image_seo=image_seo,
                          meta_title=meta_title, meta_description=meta_description,
                          internal_links=internal_links, metrics=metrics)
    return {
        "score": score,
        "issues": issues,
        "metrics": metrics,
        "publishable": not any(i["severity"] == "error" for i in issues),
    }


def score_content(*, sections: dict, seo: dict, image_seo: dict, meta_title: str,
                  meta_description: str, internal_links: list, metrics: dict) -> int:
    """0-100 on-page completeness score, weighted by what actually moves CTR
    and crawl comprehension rather than by field count."""
    kw = (seo.get("focus_keyword") or "").strip().lower()

    title_score = 0.0
    if meta_title:
        title_score = 0.4
        if 40 <= len(meta_title) <= 60:
            title_score += 0.3
        if kw and kw in meta_title.lower():
            title_score += 0.3

    desc_score = 0.0
    if meta_description:
        desc_score = 0.4
        if 120 <= len(meta_description) <= 160:
            desc_score += 0.3
        if kw and kw in meta_description.lower():
            desc_score += 0.3

    completeness = metrics["sections_present"] / max(1, metrics["sections_required"])
    depth = _clamp(metrics["word_count"] / 700)
    faq = _clamp(metrics["faq_count"] / 5)

    # Group coverage is scored against each group's MINIMUM rather than mere
    # presence — one token keyword in a group is not a strategy.
    targets = kw_engine.GROUP_TARGETS
    keywords = sum(
        _clamp(len(seo.get(group) or []) / low) for group, (low, _high) in targets.items()
    ) / len(targets)

    # Where the primary keyword actually landed, which is what the placement
    # rules are for. Absent (no plan) scores neutral rather than zero, so a
    # legacy payload is not punished for a feature it predates.
    placement_map = (metrics.get("keywords") or {}).get("placement") or {}
    placement = (sum(1 for v in placement_map.values() if v) / len(placement_map)
                 if placement_map else 0.6)

    headings = _clamp(len(seo.get("headings") or []) / 5)
    image = 1.0 if image_seo.get("alt") else 0.0
    if image and image_seo.get("caption"):
        image = 1.0
    links = _clamp(len(internal_links) / 4)

    verified_rows = [r for r in (sections.get("specifications") or []) if r.get("verified")]
    specs = _clamp(len(verified_rows) / 6)

    weighted = (
        title_score * 12
        + desc_score * 10
        + completeness * 18
        + depth * 10
        + faq * 7
        + keywords * 10
        + placement * 8
        + headings * 5
        + image * 5
        + links * 5
        + specs * 5
    )

    # Penalties. Fabrication is scored hardest: a page that invents a
    # certification is worse than an incomplete one. Stuffing is next — it is
    # the one keyword defect that makes a page worse than having no strategy.
    weighted -= metrics["unsupported_claims"] * 12
    weighted -= min(10, metrics["filler_hits"] * 2)
    # Interchangeable headings and question-restating answers are sections that
    # exist without earning their place. Capped, because they cost a page far
    # less than a fabricated claim does.
    weighted -= min(8, metrics.get("generic_benefits", 0) * 3)
    weighted -= min(8, metrics.get("non_answer_faqs", 0) * 3)
    weighted -= min(15, len((metrics.get("keywords") or {}).get("stuffed_sections") or []) * 5)
    if metrics["repetition_ratio"] > 0.18:
        weighted -= min(12, (metrics["repetition_ratio"] - 0.18) * 100)

    return int(max(0, min(100, round(weighted))))
