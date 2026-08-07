"""Fill CAS number, chemical formula and molecular weight from PubChem.

The companion to `missing_specs`, which reports the gap. This closes the part
of it that can be closed from an authoritative public registry — roughly the
"SINGLE SUBSTANCE QUICK LOOKUP" tranche of that command's triage.

What it will not do:

* **Overwrite anything.** Only blank fields are filled. A value a human typed
  always wins, and re-running is safe.
* **Guess.** A name that does not resolve to exactly one PubChem compound is
  skipped and reported. Mixtures ("Xylene"), blends and trade names land here
  by design — those are the products where a wrong CAS ships the wrong drum,
  and they still need the SDS.
* **Touch purity or UN number.** Purity is a property of the specific stock,
  and the UN number depends on concentration and packing group — PubChem lists
  1830, 1832 and 2796 for sulphuric acid alone. UN candidates are printed for a
  human to choose from; nothing is written.

GHS data is split into its three real fields — `signal_word` ("Danger"),
`hazard_statements` (["H314: ..."]) and `hazard_class`
("Skin corrosion/irritation"). They are different concepts and are not merged.

Dry run by default. Nothing is written without --apply.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from ai_tools import chem_lookup
from catalog.models import Product

FIELDS = ("cas_number", "chemical_formula", "molecular_weight", "density",
          "signal_word", "hazard_statements", "hazard_class")
# Fields that need the slower PUG View calls, so those are only made when
# something in this set is actually being filled.
SAFETY_FIELDS = {"density", "signal_word", "hazard_statements", "hazard_class"}


class Command(BaseCommand):
    help = "Fill blank identifiers (CAS, formula, weight, density, GHS) from PubChem. Dry run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the results. Without this, only reports.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after this many products (0 = all).")
        parser.add_argument("--slug", action="append", default=[],
                            help="Only this product slug. Repeatable.")
        parser.add_argument("--field", action="append", default=[], choices=list(FIELDS),
                            help="Only fill these fields. Repeatable. Default: all three.")
        parser.add_argument("--refresh", action="store_true",
                            help="Also re-pull fields THIS command previously wrote, per "
                                 "identifier_source provenance. Staff-entered values still "
                                 "win — they carry no provenance and are never touched. Use "
                                 "after a lookup bug fix.")

    def handle(self, *args, **options):
        fields = options["field"] or list(FIELDS)
        refresh = options["refresh"]
        products = Product.objects.all().order_by("name")
        if options["slug"]:
            products = products.filter(slug__in=options["slug"])
        elif not refresh:
            # Only products actually missing something we could fill.
            missing = Q()
            for field in fields:
                # hazard_statements is a JSON list, so "blank" is [] not "".
                missing |= Q(**{field: [] if field == "hazard_statements" else ""})
            products = products.filter(missing)
        if options["limit"]:
            products = products[: options["limit"]]

        filled = skipped = unresolved = 0
        for product in products:
            result = chem_lookup.lookup_identifiers(product.name)
            if not result:
                unresolved += 1
                self.stdout.write(self.style.WARNING(
                    f"  ?  {product.name} — no single PubChem match (mixture, blend or "
                    f"trade name). Needs the SDS."))
                continue

            # Density and hazard class live behind extra PUG View calls, so
            # only pay for them when they are wanted and still blank.
            wants_safety = [f for f in fields
                            if f in SAFETY_FIELDS and not getattr(product, f)]
            safety = chem_lookup.lookup_safety(result["cid"]) if wants_safety else {}
            result = {**result, **safety}

            provenance_fields = set(product.identifier_source or {})
            updates = {}
            for field in fields:
                value = result.get(_source_key(field))
                if not value:
                    continue
                current = getattr(product, field)
                if not current:
                    updates[field] = value
                elif refresh and field in provenance_fields and current != value:
                    # We wrote this one; a human did not. Safe to correct.
                    updates[field] = value
            if not updates:
                skipped += 1
                continue

            summary = ", ".join(
                f"{k}: {getattr(product, k)} -> {v}" if getattr(product, k) else f"{k}={v}"
                for k, v in updates.items())
            note = ""
            if len(result["cas_candidates"]) > 1 and "cas_number" in updates:
                # Worth a human glance: more than one registry number exists,
                # usually because the substance has hydrate or grade variants.
                note = self.style.WARNING(
                    f"  [multiple CAS: {', '.join(result['cas_candidates'])}]")
            self.stdout.write(f"  ✓  {product.name}: {summary}  (CID {result['cid']}){note}")

            un_candidates = result.get("un_candidates") or []
            if un_candidates and not product.un_number:
                # Never auto-filled: the correct UN number depends on the
                # concentration in the drum (sulphuric acid is UN1830 above
                # 51% and UN2796 at or below). Recorded so staff choose from a
                # shortlist instead of researching it.
                self.stdout.write(self.style.WARNING(
                    f"       UN candidates (pick one against your SDS): "
                    f"{', '.join(un_candidates)}"))

            if options["apply"]:
                for field, value in updates.items():
                    setattr(product, field, value)
                provenance = {"source": result["source"], "cid": result["cid"],
                              "url": result["source_url"],
                              "matched_name": result["matched_name"],
                              "cas_candidates": result["cas_candidates"]}
                product.identifier_source = {
                    **(product.identifier_source or {}),
                    **{field: provenance for field in updates},
                    **({"un_candidates": un_candidates} if un_candidates else {}),
                }
                # save() rather than update() so the revalidation signal fires
                # and the affected product pages are actually purged.
                product.save()
            filled += 1

        verb = "Filled" if options["apply"] else "Would fill"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} {filled} product(s). {skipped} already complete, "
            f"{unresolved} unresolved (need the SDS)."))
        if not options["apply"] and filled:
            self.stdout.write("Re-run with --apply to write these values.")


def _source_key(field: str) -> str:
    """Model field name -> key in the lookup result."""
    return {"cas_number": "cas"}.get(field, field)
