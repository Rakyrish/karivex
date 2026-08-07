"""Chemical identifier lookup against PubChem (NIH).

Why a database lookup rather than the language model: CAS numbers, formulae
and molecular weights are registry facts, and a model reciting them from
memory is guessing with a confident voice. PubChem is the authority, the
answer is reproducible, and every value we store carries the CID and URL it
came from so a human can check it.

**This never invents.** A name that does not resolve to exactly one compound
returns None and the field stays empty. That is the common case for the parts
of this catalogue that were always ambiguous — "Xylene" is a mixture of three
isomers and correctly 404s here, trade names and blends resolve to nothing.
Failing empty is the whole point: it is what separates this from asking a model
to fill the gap.

Nothing here overwrites a value a human entered. The backfill command only
touches blank fields.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter

import requests

logger = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PUBCHEM_WEB = "https://pubchem.ncbi.nlm.nih.gov/compound"

# PubChem asks for no more than 5 requests/second. Each lookup makes two, so
# this keeps a full-catalogue backfill comfortably inside their limit.
REQUEST_DELAY_SECONDS = 0.35
TIMEOUT = 20

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
# A formula-shaped synonym: element symbols and digits only, no spaces.
_FORMULA_RE = re.compile(r"^[A-Z][A-Za-z0-9()·.*]{1,24}$")
_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
# Hydrate separators. PubChem writes the same salt as MgSO4.7H2O, MgSO4*7H2O
# and MgSO4·7H2O depending on which synonym you read.
_HYDRATE_SPLIT_RE = re.compile(r"[·.*]")
# Registry codes are formula-shaped: "NSC54563" parses as N·S·C54563, and
# "DTXSID9021269" as D·T·X·S·I·D9021269. Composition equality already rejects
# them, but a subscript ceiling makes that safe by construction rather than by
# coincidence. No real formula in this catalogue comes near it.
_MAX_SUBSCRIPT = 999

# PubChem indexes American spellings. British forms are what this catalogue
# uses, so a failed lookup is retried with the spelling swapped rather than
# giving up on a product that does resolve perfectly well.
_SPELLING_SWAPS = (
    ("sulphur", "sulfur"), ("sulph", "sulf"), ("aluminium", "aluminum"),
    ("caesium", "cesium"), ("phosphorous acid", "phosphorous acid"),
)

# Words that describe the pack or the grade, not the substance. Left in, they
# turn a resolvable name into a 404.
_NOISE_RE = re.compile(
    r"\b(?:industrial|technical|food|laboratory|lab|pharmaceutical|pharma|cosmetic|"
    r"reagent|analytical|pure|grade|powder|flakes?|pellets?|granules?|crystals?|"
    r"liquid|solution|anhydrous|solid|"
    # Second tranche, added after a full-catalogue run left 65 products
    # unresolved: these describe processing or presentation, not the substance,
    # and each one was singlehandedly stopping a name PubChem knows. "Refined
    # Sodium Bicarbonate" is sodium bicarbonate; "Refined Castor Oil" is castor
    # oil. Words that change WHICH substance is meant — "meta", "mono", "di",
    # isomer prefixes — are deliberately NOT here.
    r"refined|purified|commercial|synthetic|natural|edible|premium|extra)\b", re.I)

# Orthography fixes, applied before the noise strip. These are spelling
# variants of one substance, never substitutions of one substance for another:
# "Normal Butyl Acetate" is the trade spelling of n-butyl acetate, and "n
# hexane" is n-hexane with the hyphen lost. Each entry has to be a pure
# renaming — if a swap could change the compound, it does not belong here, and
# PubChem's single-match rule is still the thing that decides.
_NAME_FIXES = (
    (re.compile(r"^normal\s+", re.I), "n-"),
    (re.compile(r"^n\s+(?=[a-z])", re.I), "n-"),
    (re.compile(r"^iso\s+", re.I), "iso"),
    (re.compile(r"^sec\s+", re.I), "sec-"),
    (re.compile(r"^tert\s+", re.I), "tert-"),
    (re.compile(r"\bmeta\s+silicate\b", re.I), "metasilicate"),
    (re.compile(r"\bortho\s+phosphoric\b", re.I), "orthophosphoric"),
    (re.compile(r"\btri\s+sodium\b", re.I), "trisodium"),
    (re.compile(r"\bdi\s+sodium\b", re.I), "disodium"),
    (re.compile(r"\bmono\s+propylene\b", re.I), "monopropylene"),
    (re.compile(r"\bbi\s+carbonate\b", re.I), "bicarbonate"),
    (re.compile(r"\bhydro\s+sulphite\b", re.I), "hydrosulfite"),
)
_PACK_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|l|ml|%|kgs|litres?|liters?)\b", re.I)


def _parse_group(text: str) -> Counter | None:
    """Element counts for one bracketed fragment, or None if it isn't one.

    Bracket groups are expanded rather than rejected: the conventional
    spellings this module exists to recover — Al2(SO4)3, Ca(OH)2 — are exactly
    the ones that carry brackets, so refusing to parse them made them
    permanently ineligible.
    """
    stack: list[Counter] = [Counter()]
    position = 0
    while position < len(text):
        char = text[position]
        if char == "(":
            stack.append(Counter())
            position += 1
            continue
        if char == ")":
            if len(stack) == 1:  # unbalanced
                return None
            group = stack.pop()
            match = re.compile(r"\)(\d*)").match(text, position)
            multiplier = int(match.group(1) or 1)
            if multiplier > _MAX_SUBSCRIPT:
                return None
            position = match.end()
            for element, count in group.items():
                stack[-1][element] += count * multiplier
            continue
        match = _ELEMENT_RE.match(text, position)
        if not match or match.end() == position:
            return None
        count = int(match.group(2) or 1)
        if count > _MAX_SUBSCRIPT:
            return None
        stack[-1][match.group(1)] += count
        position = match.end()
    return stack[0] if len(stack) == 1 and stack[0] else None


def _parse_formula(formula: str) -> Counter | None:
    """Element counts for a formula string, or None if it isn't one.

    Used only to compare two spellings of the SAME formula. Bracket groups and
    hydrate parts are expanded exactly, so the comparison stays arithmetic —
    it can reject a valid pair, but it can never accept a wrong one.
    """
    if not formula or not _FORMULA_RE.match(formula):
        return None
    total: Counter = Counter()
    # "Na2B4O7.10H2O" -> the salt, then ten waters. Each part may carry its own
    # leading multiplier.
    for part in _HYDRATE_SPLIT_RE.split(formula):
        if not part:
            return None
        leading = re.match(r"\d+", part)
        multiplier = 1
        if leading:
            multiplier = int(leading.group())
            part = part[leading.end():]
        counts = _parse_group(part)
        if counts is None:
            return None
        for element, count in counts.items():
            total[element] += count * multiplier
    return total or None


# PubChem often carries the conventional formula ONLY inside a name —
# "Potassium iodide (KI)", "Aluminum sulfate (Al2(SO4)3)" — with the bare
# spelling absent from the synonym list altogether. KI is such a case, which
# is why potassium iodide published as "IK".
_TRAILING_PAREN_RE = re.compile(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$")


def _formula_candidates(synonym: str) -> list[str]:
    """Formula-shaped strings a synonym offers: itself, and any trailing
    parenthetical. Both are still verified against the Hill composition before
    they can win, so a mis-extraction cannot be published."""
    text = synonym.strip()
    out: list[str] = []
    if _FORMULA_RE.match(text):
        out.append(text)
    match = _TRAILING_PAREN_RE.search(text)
    if match:
        inner = match.group(1).strip()
        if inner and inner != text and _FORMULA_RE.match(inner):
            out.append(inner)
    return out


def _is_conventional(candidate: str) -> bool:
    """Reject bracketed spellings that are not how the molecular formula is
    written.

    Making bracket groups parseable also made two unwanted classes eligible,
    both observed on the first refresh run:

    * **Redundant brackets** — "K(OH)" for KOH, "Na2(O2)" for Na2O2. A bracket
      group earns its place only when it is multiplied, as in Ca(OH)2.
    * **Structural formulas** — "N(CH2CH3)3" for triethylamine,
      "CH3CH(OH)CH2OH" for propylene glycol. These describe connectivity, not
      composition, and this field holds the molecular formula. They give
      themselves away by repeating an element symbol in separate runs.

    Unbracketed candidates are left alone, so the conventional condensed
    spellings already in use (CH3COOH for acetic acid) are unaffected.
    """
    if "(" not in candidate:
        return True
    for match in re.finditer(r"\)(\d*)", candidate):
        if int(match.group(1) or 1) < 2:
            return False
    symbols = [element for element, _ in
               _ELEMENT_RE.findall(candidate.replace("(", "").replace(")", ""))]
    return len(symbols) == len(set(symbols))


def _preferred_formula(hill: str, synonyms: list[str]) -> str:
    """Prefer the conventional formula over PubChem's Hill notation.

    PubChem reports sulfuric acid as H2O4S and potassium iodide as IK. Both are
    correct Hill notation and both look wrong to every buyer who has ever
    written H2SO4 or KI. When a synonym spells the same composition the
    conventional way, that spelling wins — verified by comparing element
    counts, so this can only ever swap between two spellings of an identical
    formula.
    """
    target = _parse_formula(hill)
    if not target:
        return hill
    for synonym in synonyms:
        for candidate in _formula_candidates(synonym):
            if candidate == hill or not _is_conventional(candidate):
                continue
            if _parse_formula(candidate) == target:
                return candidate
    return hill


def _name_variants(name: str) -> list[str]:
    """Progressively broader forms to try, most specific first."""
    base = re.sub(r"\s+", " ", (name or "").strip())
    if not base:
        return []
    # Orthography first: the noise strip can expose a prefix that only reads
    # correctly once respelled ("Refined Normal Butyl Acetate").
    fixed = base
    for pattern, replacement in _NAME_FIXES:
        fixed = pattern.sub(replacement, fixed)
    stripped = _NOISE_RE.sub("", _PACK_RE.sub("", fixed))
    stripped = re.sub(r"\s{2,}", " ", stripped).strip(" -,")

    variants: list[str] = []
    for candidate in (base, fixed, stripped):
        if candidate and candidate not in variants:
            variants.append(candidate)
        low = candidate.lower()
        swapped = low
        for british, american in _SPELLING_SWAPS:
            swapped = swapped.replace(british, american)
        if swapped != low and swapped not in variants:
            variants.append(swapped)
    return variants


def _get(url: str) -> dict | None:
    try:
        response = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("PubChem request failed for %s: %s", url, exc)
        return None
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.warning("PubChem returned %s for %s", response.status_code, url)
        return None
    try:
        return response.json()
    except ValueError:
        return None


# Tokens that name a SPECIFIC form of a substance. If the product says one of
# these and the compound PubChem matched does not, they are not the same thing.
# Deliberately excludes words already treated as noise (grade, powder, refined):
# those describe presentation and do not change the chemistry. Hydration state,
# salt stoichiometry and isomer position all do.
_FORM_QUALIFIERS = frozenset("""
    meta ortho para alpha beta gamma
    mono di tri tetra penta hexa hepta
    anhydrous hydrate monohydrate dihydrate trihydrate heptahydrate
    decahydrate pentahydrate
""".split())
# Deliberately NOT qualifiers: acid / basic / neutral. They name a compound
# class that is part of the substance's own name, not a form that distinguishes
# two variants of one substance — and an acid and its salt have different stems
# anyway ("Citric Acid" vs "Sodium Citrate"), so PubChem never confuses them by
# name. Including them refused 5 correctly-resolved products (Nitric Acid,
# Oxalic Acid, Stearic Acid and similar) for no safety gain.


def _qualifier_mismatch(product_name: str, title: str) -> bool:
    """True when the product names a form the matched compound's title does not.

    Direction matters and only one direction is a problem. A product called
    "Sodium Metasilicate" matching a title of "Sodium Silicate" is a real
    mismatch — the product is more specific than the match, so the match covers
    other substances too. The reverse ("Hexane" matching "n-Hexane") is fine:
    the registry is simply more precise than the catalogue, which is normal and
    is how "n hexane" correctly resolves to 110-54-3.
    """
    def tokens(text: str) -> set[str]:
        # "Metasilicate" has to yield "meta" — the qualifier is usually fused
        # to the stem, which is why a plain word-split misses it.
        words = re.findall(r"[a-z]+", (text or "").lower())
        found = {w for w in words if w in _FORM_QUALIFIERS}
        for word in words:
            for q in _FORM_QUALIFIERS:
                if len(q) > 3 and word.startswith(q) and word != q:
                    found.add(q)
        return found

    return bool(tokens(product_name) - tokens(title))


def lookup_identifiers(name: str) -> dict | None:
    """Resolve a product name to registry identifiers, or None.

    Returns cas / chemical_formula / molecular_weight plus the provenance
    needed to audit them. None means "not confidently resolvable" — which is
    a correct, expected answer for mixtures, blends and trade names.
    """
    for variant in _name_variants(name):
        data = _get(f"{PUBCHEM_BASE}/name/{requests.utils.quote(variant)}"
                    f"/property/Title,MolecularFormula,MolecularWeight/JSON")
        time.sleep(REQUEST_DELAY_SECONDS)
        properties = ((data or {}).get("PropertyTable") or {}).get("Properties") or []
        # More than one compound means the name is ambiguous. Ambiguity is
        # exactly the failure mode this catalogue suffers from, so it is
        # treated as "no answer" rather than "pick the first".
        if len(properties) != 1:
            continue

        entry = properties[0]
        cid = entry.get("CID")
        hill_formula = str(entry.get("MolecularFormula") or "").strip()
        weight = str(entry.get("MolecularWeight") or "").strip()
        if not cid:
            continue

        # PubChem resolving to ONE compound is not the same as it resolving to
        # the RIGHT one, and this is where that gap bites. "Sodium Meta
        # Silicate" resolves cleanly to CID 23266 — whose title is plain
        # "Sodium Silicate", a generic record carrying both 1344-09-8 (water
        # glass, a solution) and 6834-92-0 (metasilicate, a solid salt). Taking
        # the first CAS would have labelled a metasilicate as water glass.
        #
        # The signal is that the product name carries a form qualifier the
        # matched title does not. When that happens the match is broader than
        # the product, so it is refused outright rather than downgraded — a
        # formula copied off the wrong compound is no safer than its CAS.
        if _qualifier_mismatch(name, str(entry.get("Title") or "")):
            logger.info(
                "Refusing %r -> CID %s (%r): product name carries a form "
                "qualifier the matched compound does not.",
                name, cid, entry.get("Title"),
            )
            continue

        synonyms = _synonyms(cid)
        cas_candidates = [s for s in synonyms if _CAS_RE.match(s.strip())]
        return {
            "cas": cas_candidates[0] if cas_candidates else "",
            # Every CAS PubChem lists, so a reviewer can see when a substance
            # has more than one registry number rather than trusting the first.
            "cas_candidates": cas_candidates[:5],
            "chemical_formula": _preferred_formula(hill_formula, synonyms),
            "molecular_weight": f"{weight} g/mol" if weight else "",
            "cid": cid,
            "matched_name": variant,
            "source_url": f"{PUBCHEM_WEB}/{cid}",
            "source": "PubChem",
        }
    return None


PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"

# A clean numeric density with a unit, e.g. "1.8302 g/cu cm" or "1.1 g/cm³".
# PubChem also carries prose entries ("Denser than water; will sink") and
# values at odd reference temperatures; those are skipped rather than parsed.
_DENSITY_RE = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(?:g/cu\s*cm|g/cm3|g/cm³|g/mL|kg/m3)\s*$", re.I)


def _walk_strings(node: dict, out: list[str]) -> None:
    """Collect every displayed string from a PUG View section tree."""
    for section in node.get("Section") or []:
        _walk_strings(section, out)
    for information in node.get("Information") or []:
        value = information.get("Value") or {}
        for markup in value.get("StringWithMarkup") or []:
            text = markup.get("String")
            if text:
                out.append(str(text))
        for number in value.get("Number") or []:
            out.append(f"{number} {value.get('Unit', '')}".strip())


def _heading(cid: int, heading: str) -> list[str]:
    data = _get(f"{PUG_VIEW}/{cid}/JSON?heading={heading}")
    time.sleep(REQUEST_DELAY_SECONDS)
    if not data:
        return []
    out: list[str] = []
    _walk_strings(data.get("Record") or {}, out)
    return out


def lookup_safety(cid: int) -> dict:
    """Density, GHS hazard classification and UN number candidates.

    UN numbers are returned as CANDIDATES, never as a single answer. PubChem
    lists 1830, 1832 and 2796 against sulphuric acid alone, because the
    correct one depends on concentration and whether the acid is spent —
    UN1830 above 51%, UN2796 at or below it. No amount of lookup resolves that
    without knowing which drum is being shipped, so the choice stays with a
    human and this only narrows it down for them.
    """
    densities = [d for d in (_DENSITY_RE.match(s.strip()) for s in _heading(cid, "Density")) if d]
    ghs = parse_ghs(_heading(cid, "GHS+Classification"))

    un_candidates = sorted({u.strip() for u in _heading(cid, "UN+Number")
                            if re.fullmatch(r"\d{4}", u.strip())})

    return {
        "density": f"{densities[0].group(1)} g/cm³" if densities else "",
        **ghs,
        "un_candidates": un_candidates,
    }


# "H314 (> 99.9%): Causes severe skin burns and eye damage [Danger Skin corrosion/irritation]"
#   code       -> H314
#   statement  -> Causes severe skin burns and eye damage
#   class      -> Skin corrosion/irritation   (the bracket, minus the signal word)
#
# The percentage in parentheses is the share of ECHA notifications reporting
# that classification. It is meaningless on a product page and is dropped.
_GHS_LINE = re.compile(
    r"^(H\d{3}[+H\d]*)\s*(?:\([^)]*\))?\s*:\s*(.+?)\s*(?:\[([^\]]+)\])?\s*$")
_SIGNAL_WORDS = ("Danger", "Warning")


def parse_ghs(lines: list[str]) -> dict:
    """Split PubChem's GHS block into its three distinct concepts.

    These are routinely conflated — an earlier version of this code stored
    "Danger — H314: Causes severe skin burns and eye damage" in a field called
    `hazard_class`, which is three different things in one string and none of
    them a hazard class. Getting safety vocabulary wrong on a chemical supply
    page is a credibility problem at best:

    * **Signal word** — "Danger" or "Warning". One per substance, set by the
      most severe classification.
    * **Hazard statement** — the H-code and its text. There are usually
      several.
    * **Hazard class** — the GHS category, e.g. "Skin corrosion/irritation".
      This is the one that is actually a *class*.
    """
    signal = next((s.strip() for s in lines if s.strip() in _SIGNAL_WORDS), "")

    statements: list[str] = []
    classes: list[str] = []
    for line in lines:
        match = _GHS_LINE.match(line.strip())
        if not match:
            continue
        code, text, bracket = match.group(1), match.group(2).strip(), (match.group(3) or "").strip()
        entry = f"{code}: {text}"
        if entry not in statements:
            statements.append(entry)
        # The bracket leads with the signal word; the remainder is the class.
        for word in _SIGNAL_WORDS:
            if bracket.startswith(word):
                bracket = bracket[len(word):].strip()
                break
        if bracket and bracket not in classes:
            classes.append(bracket)

    return {
        "signal_word": signal,
        "hazard_statements": statements[:6],
        # Several classes can apply (corrosive AND toxic to aquatic life).
        "hazard_class": "; ".join(classes[:3])[:120],
    }


def _synonyms(cid: int) -> list[str]:
    data = _get(f"{PUBCHEM_BASE}/cid/{cid}/synonyms/JSON")
    time.sleep(REQUEST_DELAY_SECONDS)
    information = ((data or {}).get("InformationList") or {}).get("Information") or []
    if not information:
        return []
    return [str(s) for s in (information[0].get("Synonym") or [])]
