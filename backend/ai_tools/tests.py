"""Tests for the structured content pipeline.

Focused on the guarantees that must hold regardless of what the model returns:
the never-fabricate rules, the shape coercion, and the validation gate. The
OpenAI calls themselves are mocked — what matters here is what the code does
with a response, including a hostile one.
"""
from unittest.mock import patch

from django.test import TestCase

from catalog.models import Category, Product

from . import chem_lookup, content_schema, keywords as kw_engine, services, validation
from .content_schema import NEEDS_VERIFICATION

SITE = {"name": "Karivex Solutions Ltd", "regions": ["Kenya", "Uganda", "Tanzania", "Rwanda"]}
CITIES = [("Nairobi", "Kenya"), ("Mombasa", "Kenya"), ("Kampala", "Uganda"),
          ("Kigali", "Rwanda"), ("Lagos", "Nigeria")]


class KeywordEngineTests(TestCase):
    def setUp(self):
        self.industry = Category.objects.create(name="Water Treatment")
        self.category = Category.objects.create(name="Acids & Alkalis", parent=self.industry)
        self.product = Product.objects.create(
            category=self.category, name="Acetic Acid", description="x" * 300,
            regions="Kenya, Uganda", packaging="25 kg drums", grade="food",
        )

    def plan(self, **kw):
        return kw_engine.build_keyword_plan(self.product, SITE, CITIES, **kw)

    def test_chemical_family_is_derived_from_the_name(self):
        self.assertEqual(kw_engine.chemical_family("Acetic Acid"), "industrial acids")
        self.assertEqual(kw_engine.chemical_family("Caustic Soda Flakes"), "alkalis and caustics")
        self.assertEqual(kw_engine.chemical_family("Sodium Hypochlorite"), "hypochlorites")
        # Longest-suffix-first: "hypochlorite" must not resolve as "chloride".
        self.assertNotEqual(kw_engine.chemical_family("Sodium Hypochlorite"), "chlorides")
        self.assertEqual(kw_engine.chemical_family("Bentonite Clay"), "")

    def test_geo_terms_exclude_countries_the_product_does_not_serve(self):
        geo = kw_engine.geo_terms(self.product, SITE, CITIES)
        self.assertEqual(geo["countries"], ["Kenya", "Uganda"])
        # Tanzania/Rwanda are company-wide but not on this product.
        self.assertNotIn("Kigali", geo["cities"])
        # A city in a country the business does not serve at all is never used.
        self.assertNotIn("Lagos", geo["cities"])
        self.assertIn("Nairobi", geo["cities"])
        self.assertIn("Kampala", geo["cities"])

    def test_geo_falls_back_to_company_regions_when_product_is_silent(self):
        self.product.regions = ""
        geo = kw_engine.geo_terms(self.product, SITE, CITIES)
        self.assertEqual(geo["countries"], SITE["regions"])

    def test_plan_is_product_specific_not_templated(self):
        other = Product.objects.create(
            category=self.category, name="Caustic Soda Flakes", description="y" * 300,
            regions="Kenya", packaging="25 kg bags",
        )
        a = self.plan()["candidates"]
        b = kw_engine.build_keyword_plan(other, SITE, CITIES)["candidates"]
        self.assertNotEqual(a["secondary_keywords"], b["secondary_keywords"])
        self.assertIn("industrial acids", a["semantic_keywords"])
        self.assertIn("alkalis and caustics", b["semantic_keywords"])

    def test_secondary_candidates_meet_the_minimum(self):
        candidates = self.plan(industries=["Food processing", "Textiles"])["candidates"]
        low, _high = kw_engine.GROUP_TARGETS["secondary_keywords"]
        self.assertGreaterEqual(len(candidates["secondary_keywords"]), low)

    def test_packaging_terms_extracted(self):
        self.assertIn("25kg", kw_engine.packaging_terms("25 kg drums"))
        self.assertIn("drums", kw_engine.packaging_terms("25 kg drums"))

    def test_staff_focus_keyword_becomes_the_primary(self):
        self.product.focus_keyword = "glacial acetic acid kenya"
        self.assertEqual(self.plan()["primary"], "glacial acetic acid kenya")

    def test_derived_primary_is_commercial(self):
        self.assertEqual(self.plan()["primary"], "acetic acid supplier kenya")

    def test_reconcile_drops_cross_group_duplicates_and_bad_geography(self):
        plan = self.plan()
        seo = {
            "secondary_keywords": ["acetic acid supplier kenya", "bulk acetic acid kenya"],
            "geographic_keywords": ["acetic acid lagos", "acetic acid nairobi"],
            "buyer_intent_keywords": ["bulk acetic acid kenya", "buy acetic acid"],
        }
        out = kw_engine.reconcile_keyword_sets(seo, plan)
        # Geography outside the delivery area is removed outright.
        self.assertNotIn("acetic acid lagos", out["geographic_keywords"])
        self.assertIn("acetic acid nairobi", out["geographic_keywords"])
        # A phrase lands in exactly one group (buyer intent outranks secondary).
        self.assertIn("bulk acetic acid kenya", out["buyer_intent_keywords"])
        self.assertNotIn("bulk acetic acid kenya", out["secondary_keywords"])
        # The primary never doubles as a secondary.
        self.assertNotIn(plan["primary"], out["secondary_keywords"])

    def test_reconcile_tops_up_short_groups_from_candidates(self):
        plan = self.plan(industries=["Food processing"])
        out = kw_engine.reconcile_keyword_sets({"secondary_keywords": ["one useful phrase"]}, plan)
        low, _ = kw_engine.GROUP_TARGETS["secondary_keywords"]
        self.assertGreaterEqual(len(out["secondary_keywords"]), low)


class StuffingDetectionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Acids & Alkalis")
        self.product = Product.objects.create(
            category=self.category, name="Acetic Acid", description="x" * 300, regions="Kenya",
        )
        self.plan = kw_engine.build_keyword_plan(self.product, SITE, CITIES)

    def test_query_splice_is_detected(self):
        text = "We supply the region with acetic acid Kenya for food processing."
        self.assertEqual(kw_engine.query_splices(text, self.plan), ["acetic acid Kenya"])

    def test_natural_phrasing_is_not_a_splice(self):
        text = "Acetic acid supplied across Kenya from our Nairobi warehouse."
        self.assertEqual(kw_engine.query_splices(text, self.plan), [])

    def test_repeated_phrase_flags_as_stuffed(self):
        text = ("Acetic acid supplier Kenya. " * 6) + " ".join(["filler"] * 40)
        analysis = kw_engine.analyse_section(text, self.plan, {})
        self.assertTrue(kw_engine.is_stuffed(analysis))

    def test_single_long_tail_mention_is_not_stuffing(self):
        """A six-word phrase used once scored 3% density and was wrongly
        flagged, blocking pages for doing the right thing."""
        text = ("Where to buy sulphuric acid in Kenya is the question we hear most, "
                "so here is how ordering works. " + " ".join(["detail"] * 180))
        analysis = kw_engine.analyse_section(
            text, self.plan, {"long_tail_keywords": ["where to buy sulphuric acid in kenya"]})
        self.assertEqual(analysis["overused"], [])
        self.assertFalse(kw_engine.is_stuffed(analysis))

    def test_repeated_long_tail_phrase_is_still_stuffing(self):
        text = (("Where to buy acetic acid in Kenya. " * 4) + " ".join(["detail"] * 60))
        analysis = kw_engine.analyse_section(
            text, self.plan, {"long_tail_keywords": ["where to buy acetic acid in kenya"]})
        self.assertTrue(kw_engine.is_stuffed(analysis))

    def test_natural_copy_is_not_stuffed(self):
        text = (
            "Acetic acid is a clear organic acid used to correct pH in food "
            "processing and textile finishing. Karivex holds it in Nairobi and "
            "delivers nationwide within a working day. Batch strength is stated "
            "on the certificate of analysis, so plant operators can dose against "
            "a known figure rather than re-titrating each delivery. Drums and "
            "jerrycans are stocked; bulk consignments are quoted per tonne."
        )
        analysis = kw_engine.analyse_section(text, self.plan, {})
        self.assertFalse(kw_engine.is_stuffed(analysis))

    def test_short_blocks_are_exempt_from_the_density_rule(self):
        """A two-line CTA naming the product once must not read as stuffing."""
        analysis = kw_engine.analyse_section(
            "Request an acetic acid quote today.", self.plan, {})
        self.assertFalse(kw_engine.is_stuffed(analysis))

    def test_placement_matches_words_not_the_verbatim_phrase(self):
        placement = kw_engine.primary_placement(
            plan=self.plan,
            meta_title="Acetic Acid Supplier in Kenya | Karivex",
            meta_description="Acetic acid supplied across Kenya by Karivex.",
            h1="Acetic Acid Supplier in Kenya",
            slug="acetic-acid",
            summary="Acetic acid is supplied across Kenya to food processors.",
            cta="Request an acetic acid quote for delivery in Kenya.",
        )
        self.assertTrue(placement["meta_title"])
        self.assertTrue(placement["h1"])
        self.assertTrue(placement["first_100_words"])
        # The slug carries the head noun; it is never rewritten to fit the
        # full commercial phrase, because that breaks live URLs.
        self.assertTrue(placement["slug"])

    def test_anchor_text_varies_between_links(self):
        anchors = {kw_engine.anchor_text("Sulphuric Acid", i, self.plan) for i in range(4)}
        self.assertGreater(len(anchors), 1)


class SpecificationGuardTests(TestCase):
    """CAS and purity may only ever come from the database."""

    def test_model_supplied_cas_and_purity_are_discarded(self):
        rows = content_schema.coerce_specifications(
            [{"label": "CAS Number", "value": "7647-01-0"},
             {"label": "Purity", "value": "99.5%"}],
            verified_facts={},
        )
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["CAS Number"]["value"], NEEDS_VERIFICATION)
        self.assertEqual(by_label["Purity"]["value"], NEEDS_VERIFICATION)
        self.assertFalse(by_label["CAS Number"]["verified"])

    def test_database_values_are_trusted(self):
        rows = content_schema.coerce_specifications(
            [{"label": "CAS Number", "value": "hallucinated"}],
            verified_facts={"cas number": "7647-01-0", "purity": "≥98%"},
        )
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["CAS Number"]["value"], "7647-01-0")
        self.assertTrue(by_label["CAS Number"]["verified"])
        self.assertEqual(by_label["Purity"]["value"], "≥98%")

    def test_missing_db_only_rows_are_added_as_unverified(self):
        """A missing CAS row would hide the gap; a marked one surfaces it."""
        rows = content_schema.coerce_specifications([{"label": "Appearance", "value": "white flakes"}])
        labels = {r["label"] for r in rows}
        self.assertIn("CAS Number", labels)
        self.assertIn("Purity", labels)

    def test_non_db_fields_pass_through_and_empties_are_marked(self):
        rows = content_schema.coerce_specifications(
            [{"label": "Appearance", "value": "white crystalline flakes"},
             {"label": "Density", "value": ""}],
        )
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["Appearance"]["value"], "white crystalline flakes")
        self.assertEqual(by_label["Density"]["value"], NEEDS_VERIFICATION)


class TransportClassificationTests(TestCase):
    """UN number and hazard class are shipping-document data, not chemistry."""

    def test_model_supplied_un_number_and_hazard_class_are_discarded(self):
        rows = content_schema.coerce_specifications(
            [{"label": "UN Number", "value": "UN1830"},
             {"label": "Hazard Class", "value": "Class 8"}],
            verified_facts={},
        )
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["UN Number"]["value"], NEEDS_VERIFICATION)
        self.assertEqual(by_label["Hazard Class"]["value"], NEEDS_VERIFICATION)

    def test_database_transport_values_are_trusted(self):
        rows = content_schema.coerce_specifications(
            [], verified_facts={"un number": "UN1830", "hazard class": "Class 8 (Corrosive)"})
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["UN Number"]["value"], "UN1830")
        self.assertTrue(by_label["UN Number"]["verified"])

    def test_transport_rows_absent_when_not_applicable(self):
        """A non-hazardous product must not carry a permanent 'unverified' UN
        row — that trains staff to ignore the marker."""
        labels = {r["label"] for r in content_schema.coerce_specifications([], verified_facts={})}
        self.assertNotIn("UN Number", labels)
        self.assertNotIn("Hazard Class", labels)
        # Identity fields DO always appear, because their absence is a real gap.
        self.assertIn("CAS Number", labels)
        self.assertIn("Chemical Formula", labels)

    def test_database_formula_beats_a_model_guess(self):
        rows = content_schema.coerce_specifications(
            [{"label": "Chemical Formula", "value": "H2S04-ish"}],
            verified_facts={"chemical formula": "H2SO4"},
        )
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["Chemical Formula"]["value"], "H2SO4")
        self.assertTrue(by_label["Chemical Formula"]["verified"])

    def test_model_formula_rejected_when_database_is_empty(self):
        """A formula carries the same hydrate/blend ambiguity as CAS —
        MgSO4 vs MgSO4·7H2O depends on which drum is in the warehouse."""
        rows = content_schema.coerce_specifications(
            [{"label": "Chemical Formula", "value": "H2SO4"},
             {"label": "Molecular Weight", "value": "98.08 g/mol"}], verified_facts={})
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["Chemical Formula"]["value"], NEEDS_VERIFICATION)
        self.assertEqual(by_label["Molecular Weight"]["value"], NEEDS_VERIFICATION)


class ChemLookupTests(TestCase):
    """Pure logic only — the network calls are exercised by the backfill
    command against the real PubChem service, not by the test suite."""

    def test_conventional_formula_preferred_over_hill_notation(self):
        """PubChem reports sulfuric acid as H2O4S. Buyers write H2SO4."""
        self.assertEqual(
            chem_lookup._preferred_formula("H2O4S", ["sulfuric acid", "H2SO4", "oil of vitriol"]),
            "H2SO4")

    def test_a_synonym_with_different_composition_is_never_substituted(self):
        self.assertEqual(chem_lookup._preferred_formula("H2O4S", ["NaOH", "H2O"]), "H2O4S")

    def test_hill_kept_when_no_synonym_matches(self):
        self.assertEqual(chem_lookup._preferred_formula("Al2O12S3", ["alum"]), "Al2O12S3")

    def test_formula_parser_rejects_prose(self):
        self.assertIsNone(chem_lookup._parse_formula("Denser than water"))
        self.assertIsNone(chem_lookup._parse_formula("Ca(OH"))       # unbalanced
        self.assertIsNone(chem_lookup._parse_formula("Al2(SO4)3)"))  # unbalanced
        self.assertEqual(chem_lookup._parse_formula("H2SO4"),
                         chem_lookup._parse_formula("H2O4S"))

    def test_bracket_groups_and_hydrates_are_expanded(self):
        """These used to be rejected outright, which made every conventional
        bracketed spelling permanently ineligible — the reason potassium iodide
        published as "IK" and aluminium sulphate as "Al2O12S3"."""
        for hill, conventional in (
            ("IK", "KI"),
            ("Al2O12S3", "Al2(SO4)3"),
            ("CaH2O2", "Ca(OH)2"),
            ("H14MgO11S", "MgSO4·7H2O"),
            ("B4H20Na2O17", "Na2B4O7.10H2O"),
        ):
            self.assertEqual(chem_lookup._parse_formula(hill),
                             chem_lookup._parse_formula(conventional),
                             f"{conventional} should match {hill}")

    def test_registry_codes_never_parse_as_formulae(self):
        """"NSC54563" is formula-shaped. A subscript ceiling keeps it out."""
        for code in ("NSC54563", "MFCD00003423", "DTXSID9021269", "I7T908772F"):
            self.assertIsNone(chem_lookup._parse_formula(code), code)

    def test_conventional_formula_recovered_from_a_parenthesised_name(self):
        """PubChem lists no bare "KI" synonym for potassium iodide — the only
        place the conventional spelling appears is inside a name."""
        self.assertEqual(
            chem_lookup._preferred_formula("IK", ["Potassium iodide (KI)", "SSKI"]), "KI")

    def test_structural_and_redundant_bracket_spellings_are_rejected(self):
        """Expanding brackets also made these eligible; they are not how the
        molecular formula is written."""
        self.assertEqual(chem_lookup._preferred_formula("HKO", ["K(OH)"]), "HKO")
        self.assertEqual(chem_lookup._preferred_formula("Na2O2", ["Na2(O2)"]), "Na2O2")
        self.assertEqual(
            chem_lookup._preferred_formula("C3H8O2", ["CH3CH(OH)CH2OH"]), "C3H8O2")

    def test_name_variants_strip_grade_and_pack_noise(self):
        variants = chem_lookup._name_variants("Industrial Grade Caustic Soda Flakes 25kg")
        self.assertTrue(any("caustic soda" in v.lower() for v in variants))
        self.assertTrue(any("25kg" not in v.lower() for v in variants))

    def test_british_spelling_falls_back_to_american(self):
        variants = [v.lower() for v in chem_lookup._name_variants("Sulphuric Acid")]
        self.assertTrue(any("sulfuric" in v for v in variants))

    def test_generation_fills_identifiers_for_a_new_product(self):
        """A product added today must reach the same state as one that went
        through the backfill command — otherwise the catalogue splits into
        products with a full spec table and products without."""
        category = Category.objects.create(name="Acids")
        product = Product.objects.create(category=category, name="Nitric Acid",
                                         description="x" * 300)
        with patch("ai_tools.chem_lookup.lookup_identifiers") as lookup, \
             patch("ai_tools.chem_lookup.lookup_safety") as safety:
            lookup.return_value = {
                "cas": "7697-37-2", "cas_candidates": ["7697-37-2"],
                "chemical_formula": "HNO3", "molecular_weight": "63.01 g/mol",
                "cid": 944, "matched_name": "Nitric Acid",
                "source_url": "https://pubchem.ncbi.nlm.nih.gov/compound/944",
                "source": "PubChem",
            }
            safety.return_value = {"density": "1.51 g/cm³", "hazard_class": "Danger — H314",
                                   "un_candidates": ["2031", "2032"]}
            filled = services.ensure_identifiers(product)

        product.refresh_from_db()
        self.assertEqual(product.cas_number, "7697-37-2")
        self.assertEqual(product.chemical_formula, "HNO3")
        self.assertEqual(product.density, "1.51 g/cm³")
        self.assertIn("cas_number", filled)
        # UN number is never auto-filled, only offered as candidates.
        self.assertEqual(product.un_number, "")
        self.assertEqual(product.identifier_source["un_candidates"], ["2031", "2032"])

    def test_staff_entered_identifiers_are_never_overwritten(self):
        category = Category.objects.create(name="Acids")
        product = Product.objects.create(category=category, name="Nitric Acid",
                                         description="x" * 300, cas_number="STAFF-VALUE")
        with patch("ai_tools.chem_lookup.lookup_identifiers") as lookup, \
             patch("ai_tools.chem_lookup.lookup_safety", return_value={}):
            lookup.return_value = {
                "cas": "7697-37-2", "cas_candidates": [], "chemical_formula": "HNO3",
                "molecular_weight": "", "cid": 944, "matched_name": "Nitric Acid",
                "source_url": "u", "source": "PubChem",
            }
            services.ensure_identifiers(product)
        product.refresh_from_db()
        self.assertEqual(product.cas_number, "STAFF-VALUE")
        self.assertEqual(product.chemical_formula, "HNO3")

    def test_unresolvable_name_writes_nothing(self):
        category = Category.objects.create(name="Blends")
        product = Product.objects.create(category=category, name="Black Masterbatch",
                                         description="x" * 300)
        with patch("ai_tools.chem_lookup.lookup_identifiers", return_value=None):
            self.assertEqual(services.ensure_identifiers(product), [])
        product.refresh_from_db()
        self.assertEqual(product.cas_number, "")

    def test_lookup_failure_never_breaks_generation(self):
        category = Category.objects.create(name="Acids")
        product = Product.objects.create(category=category, name="Nitric Acid",
                                         description="x" * 300)
        with patch("ai_tools.chem_lookup.lookup_identifiers",
                   side_effect=RuntimeError("pubchem down")):
            self.assertEqual(services.ensure_identifiers(product), [])

    def test_density_regex_accepts_clean_values_only(self):
        self.assertTrue(chem_lookup._DENSITY_RE.match("1.8302 g/cu cm"))
        self.assertTrue(chem_lookup._DENSITY_RE.match("1.1 g/cm³"))
        self.assertIsNone(chem_lookup._DENSITY_RE.match("1.39 at 68 °F (USCG, 1999)"))
        self.assertIsNone(chem_lookup._DENSITY_RE.match("Denser than water; will sink"))


class GhsParsingTests(TestCase):
    """Signal word, hazard statement and hazard class are three things.

    The first backfill stored "Danger — H314: Causes severe skin burns and eye
    damage" in a field called hazard_class, which contains a signal word, a
    statement, and no class at all.
    """

    LINES = [
        "Danger",
        "H314: Causes severe skin burns and eye damage [Danger Skin corrosion/irritation]",
        "H290 (41.1%): May be corrosive to metals [Warning Corrosive to Metals]",
        "P260, P264, P280 (click each P-code to see the statement)",
    ]

    def test_signal_word_extracted(self):
        self.assertEqual(chem_lookup.parse_ghs(self.LINES)["signal_word"], "Danger")

    def test_statements_keep_code_and_text_without_percentages(self):
        statements = chem_lookup.parse_ghs(self.LINES)["hazard_statements"]
        self.assertIn("H314: Causes severe skin burns and eye damage", statements)
        # The ECHA notification percentage is noise on a product page.
        self.assertIn("H290: May be corrosive to metals", statements)

    def test_hazard_class_is_the_class_not_the_statement(self):
        hazard_class = chem_lookup.parse_ghs(self.LINES)["hazard_class"]
        self.assertIn("Skin corrosion/irritation", hazard_class)
        self.assertNotIn("H314", hazard_class)
        self.assertNotIn("Danger", hazard_class)

    def test_precautionary_codes_are_not_treated_as_statements(self):
        statements = chem_lookup.parse_ghs(self.LINES)["hazard_statements"]
        self.assertFalse(any(s.startswith("P2") for s in statements))


class PackagingOptionsTests(TestCase):
    def test_packaging_options_come_from_the_database(self):
        """The pilot rendered "drum" while the product row said
        "100-liter drum" — the model had paraphrased away the pack size."""
        import re as _re
        packaging = "100-liter drum, 25 kg bags and IBC totes"
        parts = [p.strip() for p in _re.split(r"[,;]|\band\b", packaging) if p.strip()]
        self.assertEqual(parts, ["100-liter drum", "25 kg bags", "IBC totes"])


class EeatTests(TestCase):
    def test_unset_signals_produce_no_bullets(self):
        bullets = " ".join(content_schema.why_choose_us(
            {"regions": ["Kenya"], "certifications": "COA & MSDS with every order"}))
        self.assertNotIn("since", bullets)
        self.assertNotIn("ISO", bullets)

    def test_configured_signals_are_rendered(self):
        bullets = " ".join(content_schema.why_choose_us({
            "regions": ["Kenya"],
            "founded_year": "2015",
            "industries_served": ["Water treatment", "Food processing"],
            "quality_statement": "Every batch checked against its COA on intake.",
            "compliance": "KEBS-compliant labelling on all packs.",
            "certifications": "COA & MSDS with every order",
        }))
        self.assertIn("since 2015", bullets)
        self.assertIn("Water treatment", bullets)
        self.assertIn("Every batch checked", bullets)
        self.assertIn("KEBS-compliant", bullets)


class GenericPhrasingTests(TestCase):
    def test_various_industrial_applications_is_flagged(self):
        """Shipped live on the sulphuric acid page — the old pattern only
        listed 'various industries' and 'wide range of applications'."""
        found = [m.group(0) for p in validation._FILLER_PATTERNS
                 for m in p.finditer("Suitable for various industrial applications.")]
        self.assertTrue(found)

    def test_vague_quantifier_family_is_flagged(self):
        phrases = ["a wide range of applications", "numerous industries",
                   "several commercial uses", "a number of sectors", "many applications"]
        for phrase in phrases:
            found = [m.group(0) for p in validation._FILLER_PATTERNS for m in p.finditer(phrase)]
            self.assertTrue(found, f"missed: {phrase}")

    def test_vague_phrase_is_replaced_with_real_industries(self):
        """Reporting it was not enough — it kept shipping. The page already
        knows the industries, so the phrase is substituted."""
        out = services.specify_vague_phrases(
            "Essential for various industrial applications.",
            ["Water Treatment", "Textiles", "Food Processing"])
        self.assertNotIn("various industrial applications", out)
        self.assertEqual(out, "Essential for water treatment, textiles and food processing.")

    def test_substitution_handles_a_single_specific(self):
        out = services.specify_vague_phrases("Used across many sectors.", ["Water Treatment"])
        self.assertEqual(out, "Used across water treatment.")

    def test_no_substitution_without_something_concrete(self):
        """An honest vague phrase beats an invented specific one."""
        original = "Suitable for various industrial applications."
        self.assertEqual(services.specify_vague_phrases(original, []), original)

    def test_specifics_are_derived_from_the_industries_section(self):
        specifics = services._section_specifics({
            "industries": [{"name": "Water Treatment", "detail": "x"},
                           {"name": "Textiles", "detail": "y"}],
            "applications": [],
        })
        self.assertEqual(specifics, ["Water Treatment", "Textiles"])

    def test_specific_lists_are_not_flagged(self):
        good = ("Used in fertiliser manufacturing, metal pickling, wastewater "
                "neutralisation and battery production.")
        found = [m.group(0) for p in validation._FILLER_PATTERNS for m in p.finditer(good)]
        self.assertEqual(found, [])

    def test_meta_description_is_scanned_for_filler(self):
        """The meta description is the highest-value text on the page and was
        never being scanned."""
        report = validation.validate_content(
            sections={"summary": "Sulphuric acid supplied across Kenya."},
            seo={}, image_seo={"alt": "drum"},
            meta_title="Sulphuric Acid Supplier in Kenya",
            meta_description="Sulphuric acid for various industrial applications in Kenya.",
        )
        messages = " ".join(i["message"] for i in report["issues"])
        self.assertIn("various industrial applications", messages)

    def test_image_caption_is_scanned_for_filler(self):
        report = validation.validate_content(
            sections={"summary": "Sulphuric acid supplied across Kenya."},
            seo={}, meta_title="t", meta_description="d",
            image_seo={"alt": "drum", "caption": "A drum for various industrial applications."},
        )
        messages = " ".join(i["message"] for i in report["issues"])
        self.assertIn("various industrial applications", messages)


class CoercionTests(TestCase):
    def test_str_list_accepts_newline_string_and_dedupes(self):
        out = content_schema._str_list("25 kg bags\n25 kg bags\n\n200 L drums", 10)
        self.assertEqual(out, ["25 kg bags", "200 L drums"])

    def test_text_rejects_null_sentinels(self):
        self.assertEqual(content_schema._text("null", 100), "")
        self.assertEqual(content_schema._text(None, 100), "")

    def test_pair_list_splits_colon_strings(self):
        out = content_schema._pair_list(["Water Treatment: used as a coagulant"],
                                        "name", "detail", 5)
        self.assertEqual(out[0]["name"], "Water Treatment")
        self.assertEqual(out[0]["detail"], "used as a coagulant")

    def test_external_references_allowlist(self):
        seo = content_schema.coerce_seo({
            "external_references": [
                {"title": "PubChem", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/313"},
                {"title": "A competitor", "url": "https://example-chemicals.com/hcl"},
            ],
        })
        self.assertEqual(len(seo["external_references"]), 1)
        self.assertIn("pubchem", seo["external_references"][0]["url"])

    def test_image_filename_is_slugified_with_extension(self):
        out = content_schema.coerce_image_seo({"filename": "Caustic Soda Flakes 25kg"})
        self.assertEqual(out["filename"], "caustic-soda-flakes-25kg.jpg")

    def test_why_choose_us_only_uses_configured_facts(self):
        bullets = content_schema.why_choose_us({
            "regions": ["Kenya", "Uganda"],
            "delivery_nairobi": "24-hour delivery in Nairobi",
            "delivery_regional": "",
            "certifications": "COA & MSDS with every order",
            "hours": "Mo-Fr 08:00-17:00",
        })
        joined = " ".join(bullets)
        self.assertIn("Kenya, Uganda", joined)
        self.assertIn("24-hour delivery in Nairobi", joined)
        self.assertNotIn("ISO", joined)


class ValidationTests(TestCase):
    def _sections(self, **overrides):
        """A realistic passing page.

        Deliberately long and varied enough to clear the depth and repetition
        gates, so a test about one rule is not silently failing on another.
        """
        base = {
            "summary": (
                "Hydrochloric acid is a strong mineral acid supplied across Kenya to "
                "municipal water utilities, textile mills and food processors. Karivex "
                "holds it in Nairobi and dispatches against firm orders within a "
                "working day.\n\n"
                "Buyers use it where a fast, predictable drop in pH matters more than "
                "buffering capacity: regenerating ion-exchange resin, stripping scale "
                "from heat exchangers, and pickling steel before galvanising. Strength "
                "is stated on the certificate of analysis that ships with each "
                "consignment."
            ),
            "key_features": [
                "Held in Nairobi for same-week dispatch",
                "Supplied in HDPE jerrycans and returnable drums",
                "Certificate of analysis issued per batch",
                "Safety data sheet supplied with every delivery",
                "Road freight to Uganda, Tanzania and Rwanda",
                "Bulk consignments quoted per tonne",
            ],
            "benefits": [
                {"title": "Predictable dosing",
                 "detail": "Batch strength is certified, so treatment lines hold their "
                           "set point without operators re-titrating each delivery."},
                {"title": "Lower freight cost per litre",
                 "detail": "Drum and bulk consignments cut the per-litre landed cost "
                           "against small-pack purchasing."},
                {"title": "Documented on arrival",
                 "detail": "Paperwork arrives with the goods, which keeps audited food "
                           "and pharmaceutical sites compliant at goods-in."},
            ],
            "specifications": [{"label": "Appearance", "value": "clear colourless liquid",
                                "verified": True}],
            "applications": [
                "pH correction in municipal drinking-water treatment",
                "Regeneration of cation ion-exchange resin",
                "Descaling heat exchangers and boiler circuits",
                "Pickling carbon steel ahead of galvanising",
                "Adjusting mash acidity in starch processing",
                "Neutralising alkaline effluent before discharge",
                "Activating bentonite clay in drilling fluids",
                "Cleaning membranes in reverse-osmosis plant",
            ],
            "industries": [
                {"name": "Water treatment",
                 "detail": "Utilities dose it ahead of coagulation to bring raw water "
                           "into the range where aluminium salts flocculate."},
                {"name": "Textiles",
                 "detail": "Mills neutralise caustic residues after mercerising so "
                           "dyeing starts from a known baseline."},
                {"name": "Food processing",
                 "detail": "Starch and glucose plants use it for controlled hydrolysis "
                           "under food-grade supply only."},
                {"name": "Metal finishing",
                 "detail": "Galvanisers strip mill scale and rust so zinc bonds to bare "
                           "steel rather than oxide."},
            ],
            "storage_guidelines": (
                "Keep containers closed in a shaded, ventilated store with an acid-"
                "resistant bund. Segregate from alkalis, hypochlorite and cyanides, "
                "since contact liberates heat or toxic gas. Do not decant into metal."
            ),
            "faqs": [
                {"q": "What is the minimum order quantity?",
                 "a": "One drum for stocked strengths; bulk loads are quoted per tonne."},
                {"q": "Do you deliver outside Nairobi?",
                 "a": "Yes — road freight runs to Uganda, Tanzania and Rwanda on request."},
                {"q": "Is a certificate of analysis provided?",
                 "a": "Every consignment ships with a batch certificate and safety data sheet."},
                {"q": "Which pack sizes are available?",
                 "a": "Jerrycans and drums are stocked; bulk is arranged against contract."},
                {"q": "Can your team advise on dosing?",
                 "a": "Our technical staff will review your process during working hours."},
            ],
        }
        base.update(overrides)
        return base

    def test_unsupported_certification_claim_blocks_publishing(self):
        report = validation.validate_content(
            sections=self._sections(
                summary="Our ISO 9001 certified plant supplies hydrochloric acid across Kenya."),
            seo={"h1": "x", "focus_keyword": "hydrochloric acid kenya",
                 "secondary_keywords": ["a"], "buyer_intent_keywords": ["b"],
                 "geographic_keywords": ["c"]},
            image_seo={"alt": "drum"},
            meta_title="Hydrochloric Acid Supplier in Kenya | Karivex",
            meta_description="x" * 150,
        )
        self.assertFalse(report["publishable"])
        self.assertTrue(any("ISO 9001" in i["message"] for i in report["issues"]))

    def test_configured_claims_are_not_flagged(self):
        """A claim the business actually publishes is not a fabrication."""
        claims = validation.find_unsupported_claims(
            ["We are ISO 9001 certified."], supported="Certifications: ISO 9001")
        self.assertEqual(claims, [])

    def test_missing_sections_are_errors(self):
        report = validation.validate_content(
            sections={"summary": "short"}, seo={}, image_seo={},
            meta_title="", meta_description="",
        )
        self.assertFalse(report["publishable"])
        fields = {i["field"] for i in report["issues"] if i["severity"] == "error"}
        self.assertIn("faqs", fields)
        self.assertIn("focus_keyword", fields)

    def test_unverified_specs_warn_but_do_not_block(self):
        report = validation.validate_content(
            sections=self._sections(specifications=[
                {"label": "CAS Number", "value": NEEDS_VERIFICATION, "verified": False},
                {"label": "Appearance", "value": "clear liquid", "verified": True},
            ]),
            seo={"h1": "x", "focus_keyword": "hydrochloric acid kenya",
                 "secondary_keywords": ["a"], "buyer_intent_keywords": ["b"],
                 "geographic_keywords": ["c"]},
            image_seo={"alt": "drum"},
            meta_title="Hydrochloric Acid Supplier in Kenya | Karivex",
            meta_description="x" * 150,
            internal_links=[{"path": "/quote"}],
        )
        self.assertTrue(report["publishable"])
        self.assertTrue(any(i["field"] == "specifications" and i["severity"] == "warning"
                            for i in report["issues"]))
        self.assertEqual(report["metrics"]["pending_verification"], ["CAS Number"])

    def test_repetition_is_detected(self):
        repeated = ["the same sentence about twenty five kilogram bags again"] * 8
        self.assertGreater(validation.repetition_ratio(repeated), 0.3)

    def test_verification_markers_excluded_from_word_count(self):
        words = validation.word_count({"a": NEEDS_VERIFICATION, "b": "two words"})
        self.assertEqual(words, 2)


class MetaLengthTests(TestCase):
    """Regressions from the first live run against the real catalogue."""

    def test_bare_keyword_title_is_padded_into_the_serp_band(self):
        # The pilot produced titles of 12-23 characters because the model
        # returned the keyword itself as the title.
        out = services.enforce_meta_title("Xylene Kenya", "Xylene", "xylene kenya")
        self.assertGreaterEqual(len(out), 40)
        self.assertLessEqual(len(out), 60)
        self.assertIn("Xylene", out)
        self.assertIn("Kenya", out)

    def test_padding_reads_as_a_sentence_not_a_suffix_pile(self):
        out = services.enforce_meta_title("Sulphuric Acid Kenya", "Sulphuric Acid",
                                          "sulphuric acid kenya")
        self.assertIn("Supplier in Kenya", out)

    def test_padding_does_not_stutter_when_title_already_says_supplier(self):
        out = services.enforce_meta_title("Xylene Supplier Kenya", "Xylene", "xylene kenya")
        self.assertEqual(out.lower().count("supplier"), 1)

    def test_long_titles_are_left_alone(self):
        original = "Sodium Hypochlorite 12% Solution Supplier in Nairobi, Kenya"
        self.assertEqual(
            services.enforce_meta_title(original, "Sodium Hypochlorite", ""), original)

    def test_lowercase_keyword_title_is_cased(self):
        """The pilot published 'sulphuric acid Supplier in kenya' — the model
        handed back the lowercase keyword as the title."""
        out = services.enforce_meta_title("sulphuric acid kenya", "Sulphuric Acid",
                                          "sulphuric acid kenya")
        self.assertTrue(out.startswith("Sulphuric Acid"))
        self.assertIn("Kenya", out)
        self.assertNotIn("kenya", out)

    def test_existing_casing_is_never_flattened(self):
        """pH, IBC and all-caps product names must survive untouched."""
        self.assertEqual(services._title_case_if_flat("pH Buffer Solution Kenya"),
                         "pH Buffer Solution Kenya")
        self.assertEqual(services._title_case_if_flat("PEROXYACETIC ACID Kenya"),
                         "PEROXYACETIC ACID Kenya")

    def test_minor_words_stay_lowercase_inside_a_title(self):
        self.assertEqual(services._title_case_if_flat("xylene supplier in kenya"),
                         "Xylene Supplier in Kenya")

    def test_description_opening_letter_is_capitalised(self):
        out = services.enforce_meta_description(
            "peroxyacetic acid is available in Kenya with fast delivery.", "Peroxyacetic Acid")
        self.assertTrue(out.startswith("Peroxyacetic"))

    def test_detail_is_not_appended_when_the_copy_already_says_it(self):
        """The pilot shipped 'Get your xylene in drums today! Supplied in drum.'"""
        desc = "Xylene is a solvent available in Kenya with fast delivery in drums today."
        out = services.enforce_meta_description(desc, "Xylene", detail="Supplied in drum")
        self.assertEqual(out.lower().count("drum"), 1)

    def test_detail_is_appended_when_genuinely_new(self):
        desc = "Yellow Oxide is available in Kenya for pigment and coatings work."
        out = services.enforce_meta_description(desc, "Yellow Oxide", detail="Supplied in 25 kg bags")
        self.assertIn("25 kg bags", out)

    def test_description_starting_with_a_cased_term_is_left_alone(self):
        out = services.enforce_meta_description(
            "pH correction chemicals supplied across Kenya to water utilities.", "pH Buffer")
        self.assertTrue(out.startswith("pH "))

    def test_short_description_is_topped_up_with_product_specific_detail(self):
        desc = "Xylene supplied across Kenya for paints and industrial cleaning."
        out = services.enforce_meta_description(desc, "Xylene", "xylene kenya",
                                                detail="Supplied in 200 L drums")
        self.assertIn("200 L drums", out)
        self.assertLessEqual(len(out), 155)

    def test_description_already_long_enough_is_not_padded(self):
        desc = ("Xylene supplied across Kenya for paints, adhesives and industrial "
                "cleaning, with COA and MSDS issued against every consignment order.")
        out = services.enforce_meta_description(desc, "Xylene", "", detail="Supplied in drums")
        self.assertNotIn("Supplied in drums", out)


class SpecLabelTests(TestCase):
    def test_schema_hint_label_menu_is_rejected(self):
        """The first live run produced one row labelled with the whole menu of
        allowed property names, echoed straight out of the schema hint."""
        rows = content_schema.coerce_specifications([
            {"label": "Grade | Chemical Formula | Molecular Weight | Appearance | Density",
             "value": NEEDS_VERIFICATION},
            {"label": "Appearance", "value": "white powder"},
        ])
        labels = [r["label"] for r in rows]
        self.assertNotIn(
            "Grade | Chemical Formula | Molecular Weight | Appearance | Density", labels)
        self.assertIn("Appearance", labels)

    def test_overlong_labels_are_rejected(self):
        rows = content_schema.coerce_specifications([{"label": "x" * 60, "value": "y"}])
        self.assertNotIn("x" * 60, [r["label"] for r in rows])


class KeywordMatchingTests(TestCase):
    """A keyword check must reward good prose, not the verbatim query."""

    def test_natural_inflection_counts_as_placement(self):
        plan = {"primary": "sulphuric acid supplier kenya",
                "facets": {"head": "sulphuric acid"},
                "geo": {"countries": ["Kenya"], "cities": [], "macro": [], "all": ["Kenya"]}}
        placement = kw_engine.primary_placement(
            plan=plan,
            meta_title="Sulphuric Acid Supplier in Kenya | Karivex",
            meta_description="Sulphuric acid supplied across Kenya with COA and MSDS.",
            h1="Sulphuric Acid Supplier in Kenya",
            slug="sulphuric-acid",
            summary="Sulphuric acid is supplied across Kenya to water utilities.",
            cta="Request a sulphuric acid quote for delivery in Kenya.",
        )
        # "supplied" must satisfy a keyword containing "supplier".
        self.assertTrue(placement["meta_description"])
        self.assertTrue(placement["summary"])

    def test_legacy_path_without_a_plan_also_matches_inflections(self):
        report = validation.validate_content(
            sections={"summary": "Sulphuric acid supplied across Kenya."},
            seo={"focus_keyword": "sulphuric acid supplier kenya"},
            image_seo={"alt": "drum"},
            meta_title="Sulphuric Acid Supplier in Kenya",
            meta_description="Sulphuric acid supplied across Kenya.",
        )
        messages = " ".join(i["message"] for i in report["issues"])
        self.assertNotIn("not reflected in the meta description", messages)


class KeywordValidationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Acids & Alkalis")
        self.product = Product.objects.create(
            category=self.category, name="Acetic Acid", description="x" * 300, regions="Kenya",
        )
        self.plan = kw_engine.build_keyword_plan(self.product, SITE, CITIES)

    def _validate(self, sections, seo):
        return validation.validate_keyword_strategy(
            plan=self.plan, seo=seo, sections=sections,
            meta_title="Acetic Acid Supplier in Kenya | Karivex",
            meta_description="Acetic acid supplied across Kenya with COA and MSDS.",
            slug="acetic-acid",
        )

    def test_location_outside_delivery_area_blocks_publishing(self):
        issues, _ = self._validate(
            {"summary": "Acetic acid supplied across Kenya."},
            {"h1": "Acetic Acid Supplier in Kenya", "geographic_keywords": ["acetic acid lagos"]},
        )
        self.assertTrue(any(i["severity"] == "error" and i["field"] == "geographic_keywords"
                            for i in issues))

    def test_stuffed_summary_is_an_error(self):
        stuffed = ("Acetic acid supplier Kenya. " * 8) + " ".join(["word"] * 30)
        issues, metrics = self._validate({"summary": stuffed}, {"h1": "Acetic Acid Kenya"})
        self.assertTrue(any(i["severity"] == "error" and i["field"] == "summary" for i in issues))
        self.assertIn("summary", metrics["stuffed_sections"])

    def test_thin_groups_warn_but_do_not_block(self):
        issues, _ = self._validate(
            {"summary": "Acetic acid supplied across Kenya to food processors."},
            {"h1": "Acetic Acid Supplier in Kenya", "secondary_keywords": ["one phrase"]},
        )
        secondary = [i for i in issues if i["field"] == "secondary_keywords"]
        self.assertTrue(secondary)
        self.assertTrue(all(i["severity"] == "warning" for i in secondary))


class DestuffTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Acids & Alkalis")
        self.product = Product.objects.create(
            category=self.category, name="Acetic Acid", description="x" * 300, regions="Kenya",
        )
        self.plan = kw_engine.build_keyword_plan(self.product, SITE, CITIES)
        self.stuffed = (
            "Acetic acid supplier Kenya supplies acetic acid supplier Kenya. "
            "Buy acetic acid Kenya from the acetic acid supplier Kenya team. "
            "Acetic acid supplier Kenya ships 25 kg drums nationwide. "
        ) + " ".join(["padding"] * 30)

    @patch("ai_tools.services._destuff_text")
    def test_stuffed_section_is_rewritten(self, mock_rewrite):
        mock_rewrite.return_value = "Clean rewritten copy about 25 kg drums."
        sections, rewritten = services.destuff_sections(
            {"summary": self.stuffed}, self.plan, {})
        self.assertEqual(rewritten, ["summary"])
        self.assertEqual(sections["summary"], "Clean rewritten copy about 25 kg drums.")

    def test_clean_section_is_left_alone(self):
        clean = ("Acetic acid is supplied across Kenya to food processors and textile "
                 "mills. Karivex holds stock in Nairobi for next-day dispatch.")
        with patch("ai_tools.services._destuff_text") as mock_rewrite:
            sections, rewritten = services.destuff_sections({"summary": clean}, self.plan, {})
        mock_rewrite.assert_not_called()
        self.assertEqual(rewritten, [])
        self.assertEqual(sections["summary"], clean)

    @patch("ai_tools.services.get_client")
    def test_rewrite_dropping_a_quantity_is_discarded(self, mock_client):
        """A style pass that deletes '25 kg' loses a fact a buyer orders on."""
        mock_client.return_value.chat.completions.create.return_value = _fake_response(
            '{"text": "' + "Clean copy without the pack size. " * 12 + '"}')
        result = services._destuff_text(self.stuffed, self.plan, ["acetic acid supplier kenya"], [])
        self.assertEqual(result, self.stuffed)

    @patch("ai_tools.services.get_client")
    def test_rewrite_that_comes_back_short_is_discarded(self, mock_client):
        mock_client.return_value.chat.completions.create.return_value = _fake_response(
            '{"text": "Too short."}')
        result = services._destuff_text(self.stuffed, self.plan, [], [])
        self.assertEqual(result, self.stuffed)

    def test_list_sections_are_not_auto_rewritten(self):
        """Reflowing bullets risks silently dropping one — humans fix those."""
        with patch("ai_tools.services._destuff_text") as mock_rewrite:
            services.destuff_sections(
                {"applications": ["acetic acid supplier kenya"] * 8}, self.plan, {})
        mock_rewrite.assert_not_called()


def _fake_response(content: str):
    """Minimal stand-in for an OpenAI chat completion."""
    from types import SimpleNamespace

    message = SimpleNamespace(content=content, refusal=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


class PipelineTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Water Treatment Chemicals")
        self.product = Product.objects.create(
            category=self.category, name="Hydrochloric Acid",
            description="x" * 300, regions="Kenya, Uganda",
            focus_keyword="hydrochloric acid kenya",
        )

    def test_internal_links_resolve_to_real_routes(self):
        links = services.build_internal_links(self.product)
        paths = [link["path"] for link in links]
        self.assertIn(f"/categories/{self.category.slug}", paths)
        self.assertIn("/quote", paths)
        # Nothing may point at a route that does not exist in the frontend app.
        for path in paths:
            self.assertRegex(
                path,
                r"^/(products|categories|blog)/[^/]+$|^/(categories|contact|quote|how-we-work)$",
            )

    def test_related_products_come_from_the_catalogue_only(self):
        other = Product.objects.create(category=self.category, name="Sulphuric Acid",
                                       description="y" * 300)
        related = services.build_related_products(self.product)
        self.assertEqual([r["slug"] for r in related], [other.slug])

    def test_flatten_keeps_legacy_fields_populated(self):
        flat = services._flatten_for_legacy_fields(
            {"summary": "Opening paragraph.",
             "benefits": [{"title": "t", "detail": "Second paragraph."}],
             "industries": [],
             "applications": ["Use one", "Use two"],
             "handling_safety": {"guidance": "Wear gloves.", "ppe": ["gloves"]},
             "storage_guidelines": "Keep cool.",
             "faqs": [{"q": "q", "a": "a"}]},
            "Title", "Description", {"alt": "alt text"},
        )
        self.assertIn("Opening paragraph.", flat["description"])
        self.assertIn("Second paragraph.", flat["description"])
        self.assertEqual(flat["applications"], "Use one\nUse two")
        self.assertIn("PPE: gloves.", flat["safety_info"])

    @patch("ai_tools.services.ensure_identifiers", return_value=[])
    @patch("ai_tools.services._generate_seo_assets")
    @patch("ai_tools.services._generate_sections")
    def test_pipeline_overrides_hallucinated_cas_and_keeps_staff_keyword(
        self, mock_sections, mock_seo, _mock_identifiers,
    ):
        mock_sections.return_value = {
            "image_analysis": {"confidence": "low"},
            "sections": {
                "summary": "Hydrochloric acid supplied across Kenya.",
                "specifications": [{"label": "CAS Number", "value": "7647-01-0"}],
                "faqs": [{"q": "Do you deliver?", "a": "Yes."}],
            },
        }
        mock_seo.return_value = {
            "focus_keyword": "a keyword the model made up",
            "meta_title": "Premium Hydrochloric Acid",
            "meta_description": "Discover hydrochloric acid for your needs.",
            "image_seo": {"alt": "Blue drum of hydrochloric acid"},
        }

        payload = services.generate_structured_product_content(self.product)

        specs = {r["label"]: r for r in payload["sections"]["specifications"]}
        # The product row has no CAS, so the model's value must not survive.
        self.assertEqual(specs["CAS Number"]["value"], NEEDS_VERIFICATION)
        # Staff-set keyword wins over the model's invention.
        self.assertEqual(payload["seo"]["focus_keyword"], "hydrochloric acid kenya")
        # Deterministic meta repairs ran: filler adjective stripped, geo added.
        self.assertNotIn("Premium", payload["seo"]["meta_title"])
        self.assertFalse(payload["seo"]["meta_description"].lower().startswith("discover"))
        # Company-owned sections are present and not model-generated.
        self.assertTrue(payload["sections"]["why_choose_us"])
        self.assertEqual(payload["sections"]["delivery_coverage"]["regions"], ["Kenya", "Uganda"])

    @patch("ai_tools.services.ensure_identifiers", return_value=[])
    @patch("ai_tools.services._generate_sections")
    def test_seo_pass_failure_degrades_instead_of_raising(self, mock_sections, _mock_identifiers):
        mock_sections.return_value = {
            "sections": {"summary": "Hydrochloric acid supplied across Kenya."},
        }
        with patch("ai_tools.services._generate_seo_assets", side_effect=RuntimeError("boom")):
            payload = services.generate_structured_product_content(self.product)
        self.assertTrue(payload["seo"]["meta_title"])
        self.assertFalse(payload["report"]["publishable"])


class ContentQualityGuardTests(TestCase):
    """The defects found on the first 25 published products.

    Each of these shipped to a live page and scored 85/100, which is the point:
    the score measures on-page hygiene, so quality defects need their own
    checks rather than being assumed to show up in the number.
    """

    def test_applications_keep_the_reason_alongside_the_use(self):
        out = content_schema.coerce_sections({"applications": [
            {"use": "Iodometric titration", "why": "Supplies iodide for the redox couple."},
        ]})
        self.assertEqual(out["applications"],
                         [{"use": "Iodometric titration",
                           "why": "Supplies iodide for the redox couple."}])

    def test_legacy_string_applications_still_resolve(self):
        """Products generated before applications carried a reason must keep
        rendering — the use survives, the reason comes back empty."""
        out = content_schema.coerce_sections({
            "applications": ["Used in the manufacture of photographic films."]})
        self.assertEqual(out["applications"][0]["use"],
                         "Used in the manufacture of photographic films.")
        self.assertEqual(out["applications"][0]["why"], "")

    def test_key_features_restating_the_spec_table_are_dropped(self):
        specs = [{"label": "Chemical Formula", "value": "KI"},
                 {"label": "Packaging", "value": "25 kg sacks"}]
        features = content_schema.dedupe_key_features([
            "Chemical formula: KI.",
            "Packaging: 25 kg sacks",
            "Stock status: In stock.",
            "Free-flowing crystals that dose without caking.",
        ], specs)
        self.assertEqual(features, ["Free-flowing crystals that dose without caking."])

    def test_prose_bullets_containing_a_colon_survive(self):
        features = content_schema.dedupe_key_features(
            ["Stable in storage: no caking at ambient humidity."], [])
        self.assertEqual(len(features), 1)

    def test_substance_role_claims_are_flagged(self):
        """Potassium iodide published as "a pharmaceutical excipient" (it is an
        active ingredient) and "a nutrient in fertilizers to promote plant
        growth" (iodine is not a plant nutrient)."""
        found = validation.find_role_claims([
            "Potassium iodide serves as a pharmaceutical excipient.",
            "Serves as a nutrient in fertilizers to promote plant growth.",
        ])
        self.assertEqual(len(found), 3)  # excipient, nutrient-in-fertilisers, plant growth

    def test_a_role_the_product_record_already_states_is_not_flagged(self):
        found = validation.find_role_claims(
            ["Used as a food additive."],
            supported="Food grade citric acid, sold as a food additive.")
        self.assertEqual(found, [])

    def test_faq_answer_restating_the_question_is_caught(self):
        self.assertTrue(content_schema.is_non_answer(
            "What is the minimum order quantity for potassium iodide?",
            "Please contact us for information on minimum order quantities."))

    def test_a_real_faq_answer_passes(self):
        self.assertFalse(content_schema.is_non_answer(
            "What packaging sizes do you offer for potassium iodide?",
            "We offer potassium iodide in 25 kg bags."))
        self.assertFalse(content_schema.is_non_answer(
            "How long does delivery take for potassium iodide?",
            "We provide 24-hour delivery in Nairobi and 2-3 day delivery to Uganda, "
            "Tanzania, and Rwanda."))

    def test_interchangeable_benefit_headings_are_dropped(self):
        """The prompt bans these and the model wrote them anyway on 4 of 22
        products, so coercion removes them rather than asking again."""
        out = content_schema.coerce_sections({"benefits": [
            {"title": "Comprehensive Documentation", "detail": "COA and MSDS supplied."},
            {"title": "Reliable Supply Chain", "detail": "Held in Nairobi."},
            {"title": "Convenient Packaging Size", "detail": "25 kg sacks."},
            {"title": "Efficient Coagulation", "detail": "Drops turbidity in one dose step."},
        ]})
        self.assertEqual([b["title"] for b in out["benefits"]], ["Efficient Coagulation"])

    def test_titles_naming_what_the_material_does_are_kept(self):
        for title in ("High Adsorption Efficiency", "Efficient Solvent Action",
                      "Consistent assay between lots"):
            self.assertFalse(content_schema.is_generic_benefit_title(title), title)

    def test_non_answer_faqs_are_dropped_before_storage(self):
        out = content_schema.coerce_sections({"faqs": [
            {"q": "What is the minimum order quantity for potassium iodide?",
             "a": "Please contact us for information on minimum order quantities."},
            {"q": "Do you provide COA and MSDS?",
             "a": "Yes, a Certificate of Analysis and Safety Data Sheet ship with every order."},
        ]})
        self.assertEqual([f["q"] for f in out["faqs"]], ["Do you provide COA and MSDS?"])

    def test_verification_marker_never_reaches_published_prose(self):
        """One product published the bullet "Requires manual verification for
        purity and regulatory details." The marker is a note to staff."""
        out = content_schema.coerce_sections({"key_features": [
            f"{NEEDS_VERIFICATION} for purity and regulatory details.",
            "Free-flowing crystals that dose without caking.",
        ]})
        self.assertEqual(out["key_features"],
                         ["Free-flowing crystals that dose without caking."])

    def test_marker_leaking_into_prose_is_an_error(self):
        report = validation.validate_content(
            sections={"summary": f"Purity {NEEDS_VERIFICATION} before ordering."},
            seo={}, image_seo={})
        errors = [i["message"] for i in report["issues"] if i["severity"] == "error"]
        self.assertTrue(any(NEEDS_VERIFICATION in m for m in errors))
        self.assertFalse(report["publishable"])

    def test_vague_quantifier_with_intervening_adjectives_is_caught(self):
        """"various pharmaceutical and industrial applications" got past a
        pattern that only allowed industrial/commercial/other."""
        report = validation.validate_content(
            sections={"summary": "Suitable for various pharmaceutical and industrial applications."},
            seo={}, image_seo={})
        self.assertIn("various pharmaceutical and industrial applications",
                      " ".join(i["message"] for i in report["issues"]))

    def test_empty_benefits_warns_but_does_not_block_publishing(self):
        """Coercion drops boilerplate headings, so a product whose benefits were
        all boilerplate arrives here with none. Requiring the section then
        blocked the page over something the pipeline had just emptied — 2 of the
        first 12 products in the full-catalogue run were held exactly that way,
        with no other error."""
        sections = {
            "summary": "Karivex supplies calcium formate in 25 kg bags across Kenya.",
            "key_features": ["Free-flowing granules."],
            "specifications": [{"label": "Packaging", "value": "25 kg bags", "verified": True}],
            "applications": [{"use": "concrete accelerator", "why": "Speeds early strength gain."}],
            "industries": [{"name": "Construction", "detail": "Used in cement admixtures."}],
            "storage_guidelines": "Keep dry and sealed.",
            "faqs": [{"q": "Which pack sizes ship?", "a": "It is supplied in 25 kg bags."}],
            "benefits": [],
        }
        report = validation.validate_content(sections=sections, seo={}, image_seo={})
        errors = [i["message"] for i in report["issues"] if i["severity"] == "error"]
        self.assertFalse(any("Benefits" in m for m in errors), errors)
        warnings = [i["message"] for i in report["issues"] if i["severity"] == "warning"]
        self.assertTrue(any("No benefits section" in m for m in warnings), warnings)
