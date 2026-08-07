"""Report products missing the identifier fields buyers actually search by.

Measured on the live catalogue when this was written:
    133/148 (90%) have no CAS number
    127/148 (86%) have no purity
     10/148  (7%) have no packaging

CAS is the specific gap worth closing first. It is the identifier an industrial
buyer searches with ("CAS 64-19-7 supplier Kenya"), it is the one term a
competitor's marketing copy will not outrank you on, and the product page
template already has a `CAS Number` PropertyValue wired into its Product schema
— it simply never renders because the field is blank.

This command only reports. It deliberately cannot write, and there is no
--fix flag, because a plausible-looking wrong CAS number identifies a
completely different substance: for a chemical distributor that is a safety
problem, not an SEO one. These values must come from supplier documentation.

    python manage.py missing_specs                     # summary + worklist
    python manage.py missing_specs --field cas         # one field only
    python manage.py missing_specs --category solvents # one category
    python manage.py missing_specs --csv > todo.csv    # for a spreadsheet
    python manage.py missing_specs --with-products     # skip empty categories
"""

import csv
import re
import sys

from django.core.management.base import BaseCommand

from catalog.models import Product

# Triage buckets for the CAS backlog. These are name heuristics, not chemistry
# — they exist to sort 133 products into "what do I have to do about this one",
# never to decide what the answer is. Correct them freely as the catalogue
# grows; a product in the wrong bucket costs a moment, a wrong CAS costs more.
NO_CAS = re.compile(
    r"durox|kadpol|maxheat|foam plus|antiscalant|defoam|descal|stabilizer"
    r"|\bagent\b|homopolymer|resin|retardant|fertilizer|\bfoam\b",
    re.I,
)
FORM_DEPENDENT = re.compile(
    r"cellulose|polyvinyl|\bwax\b|octoate|bentonite|castor oil|pine oil|gypsum"
    r"|sulphate|sulfate|phosphate|silicate|oxalic|lactate|aluminium|edta"
    r"|benzalkonium|formalin|glycol|cetearyl|liquid$",
    re.I,
)

BUCKETS = [
    (
        "NO CAS EXISTS",
        "Trade names, blends and formulations. A CAS identifies one substance; "
        "these are recipes. Leave the field blank permanently — do not invent one.",
    ),
    (
        "FORM MUST BE READ OFF THE SDS",
        "Real substances, but the salt, hydrate or concentration you stock "
        "decides the number. Magnesium sulphate alone has three. Open the SDS.",
    ),
    (
        "SINGLE SUBSTANCE — QUICK LOOKUP",
        "The product name identifies one substance. Still copy the CAS from the "
        "supplier's SDS rather than a search result: grade and form vary.",
    ),
]

# Field -> (human label, why it matters). Order is the order staff should work
# through them: CAS first because it unlocks search traffic nothing else can.
TRACKED = {
    "cas_number": ("CAS number", "primary search identifier + Product schema"),
    "purity": ("Purity", "buyer filter + Product schema"),
    "packaging": ("Packaging", "quote accuracy + Product schema"),
}


class Command(BaseCommand):
    help = "List products missing CAS number, purity or packaging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--field", choices=list(TRACKED) + ["cas", "all"], default="all",
            help="Restrict to one field. 'cas' is accepted as an alias for cas_number.",
        )
        parser.add_argument(
            "--category", default="",
            help="Restrict to one category slug (matches the product's own category).",
        )
        parser.add_argument(
            "--csv", action="store_true",
            help="Emit CSV on stdout instead of the formatted worklist.",
        )
        parser.add_argument(
            "--with-products", action="store_true",
            help="Only show categories that currently hold products.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Show at most N products (the summary still counts everything).",
        )
        parser.add_argument(
            "--triage", action="store_true",
            help=(
                "Group the CAS backlog by what it would actually take to fill: "
                "products that have no CAS at all, products where the salt or "
                "hydrate form must be read off the SDS, and straightforward "
                "single-substance lookups."
            ),
        )

    def handle(self, *args, **opts):
        field = "cas_number" if opts["field"] == "cas" else opts["field"]
        fields = list(TRACKED) if field == "all" else [field]

        qs = Product.objects.select_related("category").order_by("category__name", "name")
        if opts["category"]:
            qs = qs.filter(category__slug=opts["category"])
        products = list(qs)

        if not products:
            self.stdout.write(self.style.WARNING("No products matched."))
            return

        def missing(p):
            return [f for f in fields if not str(getattr(p, f, "") or "").strip()]

        rows = [(p, missing(p)) for p in products]
        incomplete = [(p, m) for p, m in rows if m]

        if opts["csv"]:
            self._csv(incomplete, fields)
            return

        if opts["triage"]:
            self._summary(products, ["cas_number"])
            self._triage([p for p in products if not str(p.cas_number or "").strip()])
            return

        self._summary(products, fields)
        self._worklist(incomplete, opts["limit"], opts["with_products"])

    # -- output ------------------------------------------------------------

    def _summary(self, products, fields):
        total = len(products)
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nCatalogue: {total} products\n"))
        for f in fields:
            label, why = TRACKED[f]
            n = sum(1 for p in products if not str(getattr(p, f, "") or "").strip())
            pct = (n / total * 100) if total else 0
            # Anything over half the catalogue is worth shouting about; the
            # rest is a normal backlog.
            style = self.style.ERROR if pct >= 50 else (self.style.WARNING if n else self.style.SUCCESS)
            self.stdout.write(
                f"  {label:<12} missing {style(f'{n:>3}/{total}')} ({pct:>4.0f}%)   {why}"
            )

    def _worklist(self, incomplete, limit, only_with_products):
        if not incomplete:
            self.stdout.write(self.style.SUCCESS("\nNothing missing. \n"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nWorklist — {len(incomplete)} products, grouped by category"
        ))
        self.stdout.write(self.style.HTTP_INFO(
            "Grouped so one supplier's range can be filled in a single sitting.\n"
        ))

        shown = 0
        current = None
        for p, miss in incomplete:
            cat = p.category.name if p.category else "(uncategorised)"
            if only_with_products and p.category and p.category.total_product_count == 0:
                continue
            if cat != current:
                current = cat
                self.stdout.write(self.style.MIGRATE_LABEL(f"\n  {cat}"))
            self.stdout.write(
                f"    {p.name[:44]:<46} missing: {', '.join(TRACKED[m][0] for m in miss)}"
            )
            self.stdout.write(self.style.HTTP_INFO(f"      /django-admin/catalog/product/{p.pk}/change/"))
            shown += 1
            if limit and shown >= limit:
                self.stdout.write(self.style.WARNING(
                    f"\n  … stopped at --limit {limit}; {len(incomplete) - shown} more remain."
                ))
                break

        self.stdout.write(self.style.HTTP_INFO(
            "\nCAS numbers must come from supplier documentation or the product's own "
            "SDS — never from memory or a guess. A wrong CAS names a different chemical.\n"
        ))

    def _triage(self, products):
        groups = {0: [], 1: [], 2: []}
        for p in products:
            if NO_CAS.search(p.name):
                groups[0].append(p)
            elif FORM_DEPENDENT.search(p.name):
                groups[1].append(p)
            else:
                groups[2].append(p)

        for i, (title, guidance) in enumerate(BUCKETS):
            items = groups[i]
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{title} — {len(items)} products"))
            self.stdout.write(self.style.HTTP_INFO(f"  {guidance}\n"))
            for p in items:
                self.stdout.write(f"    {p.name[:44]:<46} /django-admin/catalog/product/{p.pk}/change/")

        self.stdout.write(self.style.WARNING(
            "\nNo CAS number in this catalogue may be filled from memory, from a "
            "search engine, or by an assistant. Copy it from the supplier's SDS for "
            "the grade you actually stock. A wrong CAS names a different chemical.\n"
        ))

    def _csv(self, incomplete, fields):
        w = csv.writer(sys.stdout)
        w.writerow(["category", "product", "slug", "admin_url"] + [TRACKED[f][0] for f in fields])
        for p, miss in incomplete:
            w.writerow(
                [
                    p.category.name if p.category else "",
                    p.name,
                    p.slug,
                    f"/django-admin/catalog/product/{p.pk}/change/",
                ]
                # "MISSING" marks the cells to fill; existing values are echoed
                # back so the sheet can be used as the working document.
                + ["MISSING" if f in miss else (str(getattr(p, f, "") or "").strip()) for f in fields]
            )
