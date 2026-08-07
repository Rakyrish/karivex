"""Seed the two-level, industry-first catalogue taxonomy.

Buyers search by the industry they work in ("water treatment chemicals
kenya", "food grade additives nairobi") far more than by chemical family, so
the top level is INDUSTRY and each industry owns chemical-function children.
Every industry becomes a landing page targeting its own query set.

Idempotent by slug, and deliberately non-destructive:

  * Categories that already exist are matched by slug and updated in place,
    never recreated — so their URLs, meta and any products stay put.
  * Nothing is ever deleted. Categories not named here are left alone (and
    reported), because a category may already carry products.

Run:  python manage.py seed_taxonomy [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category

# (industry name, blurb, [sub-category names])
# Ordered as they should appear in the mega-menu.
TAXONOMY: list[tuple[str, str, list[str]]] = [
    (
        "Water Treatment Chemicals",
        "Coagulants, disinfectants and pH regulators for municipal, industrial "
        "and institutional water systems across East Africa.",
        ["Coagulants & Flocculants", "Disinfectants & Chlorination",
         "pH Regulators", "Antiscalants & Corrosion Inhibitors"],
    ),
    (
        "Food-Grade & Additives",
        "Preservatives, acidity regulators and processing aids meeting "
        "food-industry purity standards.",
        ["Preservatives", "Acidity Regulators", "Sweeteners & Bulking Agents",
         "Emulsifiers & Stabilisers"],
    ),
    (
        "Cosmetic & Detergent Raw Materials",
        "Surfactants, emulsifiers, thickeners and preservatives for soap, "
        "detergent and cosmetics producers.",
        ["Surfactants", "Thickeners & Rheology", "Humectants & Emollients",
         "Fragrance & Preservation"],
    ),
    (
        "Construction Chemicals",
        "White cement, PU foams, admixtures and waterproofing chemistry for "
        "East African construction projects.",
        ["Concrete Admixtures", "Waterproofing", "Adhesives & Sealants"],
    ),
    (
        "Paints, Inks & Coatings",
        "Solvents, resins, pigments and additives for paint, ink and coating "
        "manufacturers.",
        ["Solvents & Thinners", "Resins & Binders", "Pigments & Fillers",
         "Driers & Additives"],
    ),
    (
        "Laboratory Reagents",
        "Analytical and technical grade reagents for research, education and "
        "QC laboratories.",
        ["Analytical Reagents", "Indicators & Stains", "Solvents (Lab Grade)",
         "Volumetric Solutions"],
    ),
    (
        "Agriculture & Animal Feed",
        "Fertiliser inputs, feed additives and crop-protection raw materials "
        "for farms and feed millers.",
        ["Fertiliser Inputs", "Feed Additives & Premixes", "Crop Protection Inputs"],
    ),
    (
        "Textiles & Leather",
        "Processing chemicals for dyeing, finishing and tanning operations.",
        ["Dyeing Auxiliaries", "Bleaching & Scouring", "Tanning Chemicals",
         "Finishing Agents"],
    ),
    (
        "Mining & Metallurgy",
        "Reagents for ore processing, flotation and metal finishing.",
        ["Flotation Reagents", "Leaching Chemicals", "Metal Finishing & Plating"],
    ),
    (
        "Oil, Gas & Lubricants",
        "Drilling fluids, base oils and additives for energy and lubricant "
        "blending operations.",
        ["Drilling Fluid Additives", "Base Oils", "Lubricant Additives"],
    ),
    (
        "Pharmaceutical Excipients",
        "Excipients and processing chemicals for pharmaceutical and "
        "nutraceutical manufacturing.",
        ["Excipients & Fillers", "Solvents (Pharma Grade)", "Preservatives (Pharma)"],
    ),
    (
        "Pulp, Paper & Packaging",
        "Bleaching, sizing and coating chemistry for paper and packaging mills.",
        ["Bleaching Chemicals", "Sizing & Retention", "Coating Chemicals"],
    ),
    (
        "Plastics & Rubber",
        "Polymer additives, plasticisers and vulcanising chemistry for "
        "plastics and rubber processors.",
        ["Plasticisers", "Stabilisers & Antioxidants", "Vulcanising Agents"],
    ),
    (
        "Cleaning & Hygiene",
        "Disinfectants, degreasers and sanitising chemistry for hospitality, "
        "healthcare and facility management.",
        ["Disinfectants & Sanitisers", "Degreasers & Descalers", "Laundry Chemicals"],
    ),
    (
        "Swimming Pools & Spas",
        "Chlorination, pH balancing and clarifying chemicals for pools, spas "
        "and leisure facilities.",
        ["Pool Chlorination", "pH & Alkalinity Balancers", "Clarifiers & Algaecides"],
    ),
    (
        "Sugar, Distillery & Beverage",
        "Processing aids and treatment chemicals for sugar mills, distilleries "
        "and beverage plants.",
        ["Processing Aids", "Clarification & Filtration", "CIP & Sanitation"],
    ),
]


class Command(BaseCommand):
    help = "Create/refresh the industry-first two-level category taxonomy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        created = updated = nested = 0
        touched_slugs: set[str] = set()

        with transaction.atomic():
            for order, (industry_name, blurb, children) in enumerate(TAXONOMY, start=1):
                industry, was_created = self._upsert(
                    name=industry_name, description=blurb,
                    parent=None, order=order * 100, dry=dry,
                )
                created += was_created
                updated += (not was_created)
                if industry is not None:
                    touched_slugs.add(industry.slug)

                for child_order, child_name in enumerate(children, start=1):
                    child, child_created = self._upsert(
                        name=child_name, description="",
                        parent=industry, order=child_order, dry=dry,
                    )
                    created += child_created
                    nested += 1
                    if child is not None:
                        touched_slugs.add(child.slug)

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] ' if dry else ''}industries={len(TAXONOMY)} "
            f"sub-categories={nested} created={created} updated={updated}"
        ))

        # Anything pre-existing that this taxonomy doesn't mention is reported,
        # never removed — it may already have products attached.
        leftovers = Category.objects.exclude(slug__in=touched_slugs)
        if leftovers.exists():
            self.stdout.write(self.style.WARNING(
                "Left untouched (not in the taxonomy — move or retire manually):"
            ))
            for c in leftovers:
                self.stdout.write(f"    - {c.name} (slug={c.slug}, products={c.products.count()})")

    def _upsert(self, *, name, description, parent, order, dry):
        """Match on slug so an existing category keeps its URL and products."""
        slug = slugify(name)
        existing = Category.objects.filter(slug=slug).first()

        if existing:
            changes = []
            if existing.parent_id != (parent.id if parent else None):
                existing.parent = parent
                changes.append("re-parented")
            if existing.display_order != order:
                existing.display_order = order
                changes.append("reordered")
            if description and not existing.description:
                existing.description = description
                changes.append("described")
            if changes and not dry:
                existing.save()
            self.stdout.write(
                f"  = {name}" + (f"  ({', '.join(changes)})" if changes else "")
            )
            return existing, False

        self.stdout.write(self.style.SUCCESS(f"  + {name}"))
        if dry:
            # Nothing is persisted, so there's no row to hang children off.
            # Children are still listed below; only the FK link is untested.
            return None, True
        return Category.objects.create(
            name=name, slug=slug, description=description,
            parent=parent, display_order=order,
        ), True
