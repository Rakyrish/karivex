"""Keyword research and semantic SEO engine.

Replaces the single `focus_keyword` with a per-product keyword *plan*: a
primary term plus secondary, semantic, long-tail, buyer-intent and geographic
groups, all derived from that specific product rather than a shared template.

The central design decision is that keywords are derived **deterministically,
before any copy is written**, and handed to the model as *intents to satisfy*
rather than strings to insert. Handing a model a list of twenty phrases and
asking it to include them produces precisely the keyword-stuffed prose the
whole exercise is meant to avoid — the failure is well documented in this
codebase already, where requiring the verbatim focus phrase produced openings
like "used in regions such as acetic acid Kenya" on 58 of 148 live pages.

So the flow is: derive candidates here -> tell the model what buyers are
looking for -> let it write naturally -> come back and *verify* placement and
density -> rewrite anything that drifted into stuffing. Detection and repair
sit downstream of writing, never upstream of it.

Nothing here is hardcoded per product. Every phrase is composed from facts the
product itself carries: its name, category, chemical family, grade, packaging,
the industries its content covers, and the catalogue around it.
"""
from __future__ import annotations

import re

# Commercial modifiers a procurement buyer actually types. Combined with
# product facets below, never used alone.
SUPPLY_MODIFIERS = ("supplier", "distributor", "wholesale", "bulk", "manufacturer and distributor")
# Split by the side of the noun they sit on: buyers type "buy acetic acid" but
# "acetic acid price", never "price acetic acid". Generating both from one list
# produced phrases no one searches for.
PURCHASE_PREFIXES = ("buy", "order", "wholesale", "bulk supply")
PURCHASE_SUFFIXES = ("price", "quote", "for sale", "suppliers")

# Suffix -> chemical family. Derivation, not a keyword list: it maps a name to
# the family term buyers and search engines use for topical grouping, and any
# product whose name ends in the suffix gets it. Ordered longest-first so
# "hypochlorite" is not swallowed by "chlorite".
_FAMILY_SUFFIXES = (
    ("hypochlorite", "hypochlorites"),
    ("bicarbonate", "bicarbonates"),
    ("permanganate", "permanganates"),
    ("metabisulphite", "sulphite salts"),
    ("metabisulfite", "sulphite salts"),
    ("hydroxide", "alkalis and caustics"),
    ("carbonate", "carbonates"),
    ("phosphate", "phosphates"),
    ("silicate", "silicates"),
    ("sulphate", "sulphates"),
    ("sulfate", "sulphates"),
    ("chloride", "chlorides"),
    ("nitrate", "nitrates"),
    ("peroxide", "peroxides"),
    ("alcohol", "industrial alcohols"),
    ("acetate", "acetates"),
    ("citrate", "citrates"),
    ("oxide", "metal oxides"),
    ("acid", "industrial acids"),
    ("soda", "alkalis and caustics"),
    ("wax", "waxes"),
    ("oil", "industrial oils"),
)

# Topical vocabulary for the semantic group. These establish subject relevance
# rather than target a query — they are deliberately generic, and are always
# emitted *after* the product-specific semantic terms so a page never leads
# with vocabulary shared across the catalogue.
_DOMAIN_SEMANTICS = (
    "industrial chemicals",
    "chemical distribution",
    "chemical raw materials",
    "chemical procurement",
    "industrial supply",
    "chemical warehousing",
    "bulk chemical supply",
)

_STOPWORDS = {"and", "the", "for", "of", "in", "with", "&"}

# Commercial terms whose natural inflections must all count as the same word
# when checking keyword placement.
#
# Without this, a primary keyword of "acetic acid supplier kenya" fails its
# own placement check against the sentence "acetic acid supplied across
# Kenya" — which is the *better* copy, and exactly the phrasing the rest of
# this module works to produce. A checker that rewards "supplier" over
# "supplied" would push writers straight back into the stilted, query-shaped
# prose the engine exists to prevent. Deliberately a short explicit map rather
# than a general stemmer: predictable, and it cannot collapse "kenya" into
# something shorter.
_STEM_FAMILIES = (
    ("suppl", ("supplier", "suppliers", "supply", "supplies", "supplied", "supplying")),
    ("distribut", ("distributor", "distributors", "distribution", "distribute", "distributed")),
    ("manufactur", ("manufacturer", "manufacturers", "manufacturing", "manufacture")),
    ("wholesal", ("wholesale", "wholesaler", "wholesalers", "wholesaling")),
    ("deliver", ("delivery", "deliveries", "deliver", "delivered", "delivering")),
    ("stock", ("stock", "stocks", "stocked", "stockist", "stockists")),
)
_STEM_LOOKUP = {word: stem for stem, words in _STEM_FAMILIES for word in words}


def token_regex(token: str) -> str:
    """Word-boundary pattern for a token, widened to its inflection family."""
    stem = _STEM_LOOKUP.get(token)
    return rf"\b{re.escape(stem)}\w*" if stem else rf"\b{re.escape(token)}\b"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _phrase(*parts: str) -> str:
    """Join non-empty parts into a lowercase search phrase."""
    return " ".join(p for p in (_clean(p) for p in parts) if p).lower()


def _singular(text: str) -> str:
    """Crude singulariser for using an industry name as a modifier."""
    word = _clean(text).lower()
    if word.endswith("ss") or not word.endswith("s"):
        return word
    return word[:-1]


def chemical_family(name: str) -> str:
    """The family term for a product name, or "" when nothing matches.

    Matches on a word boundary so "Acetic Acid" -> industrial acids but
    "Acidity Regulator" does not.
    """
    low = (name or "").lower()
    for suffix, family in _FAMILY_SUFFIXES:
        if re.search(rf"\b{suffix}s?\b", low):
            return family
    return ""


def head_noun(name: str) -> str:
    """The product name with pack sizes and grade words stripped — what the
    phrase generator treats as 'the product'."""
    low = (name or "").lower()
    low = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|l|ml|kgs|litres?|liters?|t|tonnes?)\b", "", low)
    low = re.sub(r"\b(?:industrial|food|technical|laboratory|lab|pharmaceutical|pharma|cosmetic)\s+grade\b", "", low)
    return _clean(low)


def packaging_terms(packaging: str) -> list[str]:
    """Pack descriptors buyers search by, e.g. '25kg', 'drums', 'ibc'."""
    low = (packaging or "").lower()
    out: list[str] = []
    for size in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*(kg|l|litres?|liters?|ml|g|t|tonnes?)\b", low):
        out.append(f"{size[0]}{'kg' if size[1] == 'kg' else size[1][0] if size[1] != 'ml' else 'ml'}")
    for word in ("drum", "jerrycan", "ibc", "bag", "sack", "bottle", "tanker", "carboy"):
        if word in low:
            out.append(word + "s" if not word.endswith("s") else word)
    seen: set[str] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


def geo_terms(product, site: dict, delivery_cities: list) -> dict:
    """Places this product is genuinely supplied to.

    Countries come from the product's own `regions` field intersected with the
    business-wide configured regions — a product may serve fewer markets than
    the company, never more. Cities are only included when their country
    survives that intersection, which is what stops the generator inventing a
    market the business does not serve.
    """
    configured = [_clean(r) for r in (site.get("regions") or []) if _clean(r)]
    configured_low = {r.lower() for r in configured}

    product_regions = [_clean(r) for r in (product.regions or "").split(",") if _clean(r)]
    # Fall back to the company-wide list when the product says nothing.
    countries = [r for r in product_regions if r.lower() in configured_low] or configured

    country_low = {c.lower() for c in countries}
    cities = [
        _clean(city) for city, country in delivery_cities
        if _clean(country).lower() in country_low and _clean(city)
    ]

    macro = ["East Africa"] if len(countries) >= 2 else []
    return {"countries": countries, "cities": cities, "macro": macro,
            "all": countries + cities + macro}


def build_keyword_plan(product, site: dict, delivery_cities: list,
                       industries: list[str] | None = None,
                       related_names: list[str] | None = None) -> dict:
    """Derive this product's keyword strategy from its own facts.

    Returns the facets the copy should cover plus candidate phrases per group.
    Candidates are a menu for the SEO pass to choose from and for validation to
    check against — not a list to paste into prose.
    """
    name = _clean(product.name)
    head = head_noun(name) or name.lower()
    category = _clean(getattr(product.category, "name", ""))
    parent = _clean(getattr(getattr(product.category, "parent", None), "name", ""))
    family = chemical_family(name)
    grade = _clean(product.get_grade_display()) if hasattr(product, "get_grade_display") else ""
    packs = packaging_terms(product.packaging)
    industries = [_clean(i) for i in (industries or []) if _clean(i)]
    related_names = [_clean(r) for r in (related_names or []) if _clean(r)]

    geo = geo_terms(product, site, delivery_cities)
    primary_country = geo["countries"][0] if geo["countries"] else ""
    primary_city = geo["cities"][0] if geo["cities"] else ""

    # Primary: staff intent wins. Otherwise the commercial head term, which is
    # the shape a procurement buyer types — "<product> supplier <country>".
    primary = (product.focus_keyword or "").strip().lower()
    if not primary:
        primary = _phrase(head, "supplier", primary_country)

    # --- Secondary: product x commercial modifier x place. Ordered so the
    # highest-intent, most specific phrases come first, because the SEO pass is
    # told to keep the leading ones.
    secondary: list[str] = []
    for modifier in SUPPLY_MODIFIERS:
        secondary.append(_phrase(head, modifier, primary_country))
    if primary_city:
        secondary.append(_phrase("buy", head, primary_city))
        secondary.append(_phrase(head, "supplier", primary_city))
    for macro in geo["macro"]:
        secondary.append(_phrase(head, macro))
    if grade:
        secondary.append(_phrase(grade.split("/")[0], head, primary_country))
    for pack in packs[:2]:
        secondary.append(_phrase(head, pack, primary_country))
    if category:
        secondary.append(_phrase(category, "supplier", primary_country))
    if parent:
        secondary.append(_phrase(parent, "supplier", primary_country))
    for industry in industries[:4]:
        secondary.append(_phrase(head, "for", industry))

    # --- Semantic: topical context, product-specific first.
    semantic: list[str] = []
    if family:
        semantic.append(family)
    if category:
        semantic.append(category.lower())
    if parent:
        semantic.append(parent.lower())
    # "Textiles" -> "textile chemicals": an industry name used as a modifier
    # reads as a singular. Guarded against "ss" so "Glass" survives intact.
    semantic += [_phrase(_singular(i), "chemicals") for i in industries[:4]]
    semantic += list(_DOMAIN_SEMANTICS)

    # --- Long-tail: full questions and qualified phrases.
    long_tail: list[str] = []
    if primary_country:
        long_tail.append(_phrase("where to buy", head, "in", primary_country))
        long_tail.append(_phrase(head, "manufacturer and distributor", primary_country))
    if primary_city:
        long_tail.append(_phrase(head, "supplier in", primary_city))
    for industry in industries[:3]:
        long_tail.append(_phrase(head, "supplier for", industry, primary_country))
    if grade:
        long_tail.append(_phrase(grade.split("/")[0], head, "supplier", primary_country))
    for pack in packs[:2]:
        long_tail.append(_phrase("bulk", head, pack, "supplier", primary_country))
    if geo["macro"]:
        long_tail.append(_phrase("chemical supplier delivering across", geo["macro"][0]))

    # --- Buyer intent: transactional.
    buyer_intent = [_phrase(m, head) for m in PURCHASE_PREFIXES]
    buyer_intent += [_phrase(head, m) for m in PURCHASE_SUFFIXES]
    if primary_country:
        buyer_intent.append(_phrase(head, "price", primary_country))
        buyer_intent.append(_phrase("industrial chemical supplier", primary_country))
    buyer_intent.append(_phrase("request", head, "quote"))
    buyer_intent.append("chemical supplier near me")

    # --- Geographic.
    geographic = [_phrase(head, place) for place in geo["all"]]
    geographic += [_phrase(head, "supplier", place) for place in geo["cities"][:3]]

    plan = {
        "primary": primary,
        "facets": {
            "head": head, "name": name, "category": category, "parent_category": parent,
            "family": family, "grade": grade, "packaging": packs,
            "industries": industries, "related_products": related_names[:6],
        },
        "geo": geo,
        "candidates": {
            "secondary_keywords": _dedupe(secondary, exclude={primary})[:20],
            "semantic_keywords": _dedupe(semantic, exclude={primary})[:12],
            "long_tail_keywords": _dedupe(long_tail, exclude={primary})[:10],
            "buyer_intent_keywords": _dedupe(buyer_intent, exclude={primary})[:10],
            "geographic_keywords": _dedupe(geographic, exclude={primary})[:10],
        },
    }
    return plan


def _dedupe(phrases: list[str], exclude: set[str] | None = None) -> list[str]:
    exclude = {e.lower() for e in (exclude or set())}
    seen: set[str] = set()
    out: list[str] = []
    for phrase in phrases:
        norm = _clean(phrase).lower()
        # Two words minimum: a bare noun is a topic, not a search phrase.
        if not norm or norm in seen or norm in exclude or len(norm.split()) < 2:
            continue
        seen.add(norm)
        out.append(norm)
    return out


# Priority order for cross-group deduplication. A phrase belongs to exactly one
# group; leaving the same term in three groups inflates the counts without
# adding a single new query the page can answer.
GROUP_PRIORITY = (
    "geographic_keywords",
    "buyer_intent_keywords",
    "long_tail_keywords",
    "secondary_keywords",
    "semantic_keywords",
)

GROUP_TARGETS = {
    "secondary_keywords": (10, 20),
    "semantic_keywords": (6, 12),
    "long_tail_keywords": (4, 10),
    "buyer_intent_keywords": (4, 10),
    "geographic_keywords": (4, 10),
}


def reconcile_keyword_sets(seo: dict, plan: dict) -> dict:
    """Merge the model's chosen keywords with the derived candidates.

    The model's selections lead (it has seen the finished copy and knows what
    the page can honestly rank for); derived candidates top each group up to
    its minimum. Cross-group duplicates are removed by priority, and anything
    naming a place the business does not serve is dropped outright.
    """
    allowed_places = {p.lower() for p in plan["geo"]["all"]}
    primary = plan["primary"]

    taken: set[str] = {primary}
    out = dict(seo)

    for group in GROUP_PRIORITY:
        low, high = GROUP_TARGETS[group]
        chosen = _dedupe(list(seo.get(group) or []), exclude=taken)

        if group == "geographic_keywords":
            chosen = [k for k in chosen if any(place in k for place in allowed_places)]

        # Top up from derived candidates when the model came up short.
        if len(chosen) < low:
            for candidate in plan["candidates"].get(group, []):
                if len(chosen) >= low:
                    break
                if candidate not in taken and candidate not in chosen:
                    chosen.append(candidate)

        chosen = chosen[:high]
        taken.update(chosen)
        out[group] = chosen

    out["focus_keyword"] = primary
    return out


# --- density, stuffing and placement -------------------------------------

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def phrase_count(text: str, phrase: str) -> int:
    """Occurrences of a phrase, matched on word boundaries and tolerant of
    whitespace, so "acetic acid" also matches across a line break."""
    tokens = [re.escape(t) for t in _words(phrase)]
    if not tokens:
        return 0
    pattern = re.compile(r"\b" + r"\W+".join(tokens) + r"\b", re.I)
    return len(pattern.findall(text or ""))


def keyword_density(text: str, phrase: str) -> float:
    """Percentage of the text's words taken up by this phrase."""
    total = len(_words(text))
    if not total:
        return 0.0
    return phrase_count(text, phrase) * len(_words(phrase)) / total * 100


# A search query pasted verbatim into prose. "acetic acid kenya" is a query,
# not English — natural copy reads "acetic acid supplied across Kenya". This
# exact defect shipped on 58 of 148 live descriptions under the old prompt, so
# it is checked mechanically rather than trusted to prompt wording.
def query_splices(text: str, plan: dict) -> list[str]:
    head = plan["facets"]["head"]
    if not head:
        return []
    places = [p for p in plan["geo"]["all"] if p]
    if not places:
        return []
    alternation = "|".join(re.escape(p) for p in places)
    # The head noun immediately followed by a bare place name, with no
    # connecting word — "acetic acid kenya", never "acetic acid in Kenya".
    pattern = re.compile(rf"\b{re.escape(head)}\s+({alternation})\b", re.I)
    return sorted({m.group(0).strip() for m in pattern.finditer(text or "")})


# Above this, a phrase is being repeated for the engine rather than the reader.
MAX_PHRASE_DENSITY = 2.5
MAX_PHRASE_REPEATS = 4
# Aggregate ceiling across ALL keyword phrases in one section. A blunt
# backstop, not the primary signal — the per-phrase repeat and density rules
# above do the real work. Raised from 8% after it blocked a legitimate FAQ
# block at 8.4%: an FAQ about zinc stearate names zinc stearate in most of its
# questions and answers, which is what a buyer wants, not stuffing. Reaching
# 12% still requires many distinct keyword phrases repeating, and any single
# abused phrase is caught by MAX_PHRASE_REPEATS long before this fires.
MAX_TOTAL_KEYWORD_DENSITY = 12.0


def analyse_section(text: str, plan: dict, keyword_sets: dict) -> dict:
    """Density and stuffing signals for one block of copy."""
    all_phrases = [plan["primary"]]
    for group in GROUP_PRIORITY:
        all_phrases += list(keyword_sets.get(group) or [])

    total_words = len(_words(text))
    overused: list[str] = []
    hits = 0
    for phrase in set(all_phrases):
        count = phrase_count(text, phrase)
        if not count:
            continue
        hits += count * len(_words(phrase))
        # The density test only applies once a phrase actually REPEATS. A
        # single mention can never be over-repetition, but density is weighted
        # by phrase length, so one occurrence of a six-word long-tail phrase in
        # a 200-word block scores 3% and was being flagged as stuffing — which
        # blocked pages for doing exactly what they should.
        if count >= MAX_PHRASE_REPEATS or (
            count >= 2 and keyword_density(text, phrase) > MAX_PHRASE_DENSITY
        ):
            overused.append(phrase)

    return {
        "word_count": total_words,
        "primary_density": round(keyword_density(text, plan["primary"]), 2),
        "total_density": round(hits / total_words * 100, 2) if total_words else 0.0,
        "overused": sorted(overused),
        "splices": query_splices(text, plan),
    }


def is_stuffed(analysis: dict) -> bool:
    """Whether a section needs an automatic de-stuffing rewrite.

    Short blocks are exempt from the density test: a two-sentence CTA that
    legitimately names the product once can trivially exceed any percentage
    threshold without being spam.
    """
    if analysis["splices"]:
        return True
    if analysis["word_count"] < 40:
        return bool(analysis["overused"])
    return (
        bool(analysis["overused"])
        or analysis["total_density"] > MAX_TOTAL_KEYWORD_DENSITY
        or analysis["primary_density"] > MAX_PHRASE_DENSITY
    )


def primary_placement(*, plan: dict, meta_title: str, meta_description: str, h1: str,
                      slug: str, summary: str, cta: str) -> dict:
    """Where the primary keyword actually landed.

    Matched on the keyword's *words* rather than the verbatim phrase. Requiring
    the exact string is what produced the spliced prose this module exists to
    prevent — "acetic acid supplied across Kenya" satisfies the intent and
    reads like English, and both should count as a pass.
    """
    primary = plan["primary"]
    tokens = [t for t in _words(primary) if t not in _STOPWORDS]

    def covers(text: str) -> bool:
        low = " ".join(_words(text))
        return bool(tokens) and all(re.search(token_regex(t), low) for t in tokens)

    first_100 = " ".join((summary or "").split()[:100])
    # The slug is checked against the head noun only, and never rewritten:
    # changing a live slug breaks every external link and bookmark to the page,
    # which costs more than the marginal gain of a longer URL.
    head_tokens = _words(plan["facets"]["head"])
    slug_low = (slug or "").lower()

    return {
        "meta_title": covers(meta_title),
        "meta_description": covers(meta_description),
        "h1": covers(h1),
        "first_100_words": covers(first_100),
        "summary": covers(summary),
        "cta": covers(cta),
        "slug": bool(head_tokens) and all(t in slug_low for t in head_tokens),
    }


def anchor_text(title: str, index: int, plan: dict) -> str:
    """Varied, keyword-aware anchor text for an internal link.

    Varied on purpose: 148 pages all linking out as "Read more" wastes the
    anchor signal, and 148 pages all using the identical keyword anchor is a
    footprint. The rotation is deterministic so a regeneration does not reshuffle
    every link on the site.
    """
    country = plan["geo"]["countries"][0] if plan["geo"]["countries"] else ""
    forms = [
        title,
        _phrase(title, "supplier", country).title() if country else title,
        f"{title} — bulk supply",
        f"{title} specifications",
    ]
    return forms[index % len(forms)]
