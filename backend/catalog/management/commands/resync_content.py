"""Re-apply the stored content contract to already-published products.

Regeneration is not the right tool for a pipeline bug. When a lookup or a
coercion rule is corrected, the prose on 25 live pages is fine — it is the
derived parts that are stale: the specification table caches the database's
identifiers at generation time, and key features was populated from that same
table.

So this re-runs the deterministic half of the pipeline over stored
`content_sections` and leaves every model-authored section untouched. It is
idempotent, and it never calls the language model.

What it re-derives:

* **specifications** — through `coerce_specifications` with the CURRENT
  database facts, so a corrected CAS number or chemical formula reaches the
  page and the Product JSON-LD. This is what carried "IK" for potassium
  iodide after `chem_lookup` was fixed to return "KI".
* **key features** — through `dedupe_key_features`, dropping bullets that
  merely restate a spec row, and any that leaked the verification marker into
  customer-facing prose.
* **benefits** — interchangeable headings ("Comprehensive Documentation",
  "Reliable Supply Chain") removed.
* **FAQs** — questions whose answer only restates them removed, since they
  publish as FAQPage structured data.

Dry run by default. Nothing is written without --apply.
"""
import json

from django.core.management.base import BaseCommand

from ai_tools import content_schema
from ai_tools.services import verified_facts_for
from catalog.models import Product


class Command(BaseCommand):
    help = ("Re-derive specifications and key features on published products from current "
            "database facts. No model calls. Dry run unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the results. Without this, only reports.")
        parser.add_argument("--slug", action="append", default=[],
                            help="Only this product slug. Repeatable.")

    def handle(self, *args, **options):
        products = Product.objects.all().order_by("name")
        if options["slug"]:
            products = products.filter(slug__in=options["slug"])

        changed = unchanged = 0
        for product in products:
            sections = product.content_sections or {}
            if not sections.get("summary"):
                continue  # renders from the flat columns; nothing to re-derive

            specifications = content_schema.coerce_specifications(
                sections.get("specifications"), verified_facts_for(product))
            key_features = content_schema.dedupe_key_features(
                sections.get("key_features") or [], specifications)
            benefits = [b for b in (sections.get("benefits") or [])
                        if not content_schema.is_generic_benefit_title(b.get("title", ""))]
            faqs = [f for f in (sections.get("faqs") or [])
                    if not content_schema.is_non_answer(f.get("q", ""), f.get("a", ""))]

            spec_changes = _spec_changes(sections.get("specifications") or [], specifications)
            dropped = (
                [f"key feature: {f}" for f in (sections.get("key_features") or [])
                 if f not in key_features]
                + [f"benefit heading: {b.get('title')}" for b in (sections.get("benefits") or [])
                   if b not in benefits]
                + [f"FAQ non-answer: {f.get('q')}" for f in (sections.get("faqs") or [])
                   if f not in faqs]
            )
            if not spec_changes and not dropped:
                unchanged += 1
                continue

            self.stdout.write(f"  {product.name}")
            for line in spec_changes:
                self.stdout.write(f"       spec  {line}")
            for item in dropped:
                self.stdout.write(self.style.WARNING(f"       drop  {item}"))

            if options["apply"]:
                product.content_sections = {
                    **sections,
                    "specifications": specifications,
                    "key_features": key_features,
                    "benefits": benefits,
                    "faqs": faqs,
                }
                # save() rather than update() so the revalidation signal fires
                # and the affected product pages are actually purged.
                product.save()
            changed += 1

        verb = "Updated" if options["apply"] else "Would update"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} {changed} product(s). {unchanged} already current."))
        if not options["apply"] and changed:
            self.stdout.write("Re-run with --apply to write these values.")


def _spec_changes(before: list[dict], after: list[dict]) -> list[str]:
    """Human-readable label-by-label diff of the specification table."""
    old = {row.get("label", ""): row.get("value", "") for row in before}
    new = {row.get("label", ""): row.get("value", "") for row in after}
    out = []
    for label in sorted(set(old) | set(new)):
        if old.get(label) == new.get(label):
            continue
        if label not in old:
            out.append(f"+ {label}: {new[label]}")
        elif label not in new:
            out.append(f"- {label}: {old[label]}")
        else:
            out.append(f"~ {label}: {old[label]} -> {new[label]}")
    return out
