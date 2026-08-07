"""Import CAS number / purity / packaging from the filled-in worklist CSV.

This is the return leg of the round trip that `missing_specs --csv` starts:

    python manage.py missing_specs --csv > todo.csv   # export the gaps
    # ... staff fill the MISSING cells from each supplier's SDS ...
    python manage.py import_specs todo.csv --dry-run  # show what would change
    python manage.py import_specs todo.csv            # apply

Why this command is deliberately paranoid: a CAS number is the identifier a
buyer orders against, and a plausible-looking wrong one names a completely
different chemical. `missing_specs` has no --fix flag for that reason, and this
importer is the only writer — so every guard that would have gone there lives
here instead:

  * A row is only applied if the CSV's slug matches a real product.
  * Cells still reading MISSING (or blank) are SKIPPED, never written as empty.
    A half-filled sheet is the normal case, not an error.
  * A value that would OVERWRITE an existing different value is refused unless
    --overwrite is passed, and is always reported. Silent clobbering of a spec
    someone already verified is the worst outcome here.
  * CAS numbers are checked against the registry's own check-digit rule, which
    catches transcription slips (a digit dropped or two transposed) before they
    reach a product page. This validates the FORMAT, not the SUBSTANCE — it
    cannot tell you the number is the right chemical, only that it is a
    well-formed CAS. Rejected rows are listed and skipped, never guessed at.
  * --dry-run reports the full outcome and writes nothing.

Nothing here infers, completes or corrects a value. If the cell is empty this
command leaves the field empty.
"""

import csv
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Product

# CSV header -> model field. These are the labels missing_specs writes.
COLUMNS = {
    "CAS number": "cas_number",
    "Purity": "purity",
    "Packaging": "packaging",
}

PLACEHOLDERS = {"", "missing", "n/a", "na", "none", "-", "tbc", "tbd", "?", "unknown"}

CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def cas_check_digit_ok(value: str) -> bool:
    """True if `value` satisfies the CAS registry check-digit rule.

    The last digit is the sum of every preceding digit weighted by its position
    counting from the right, modulo 10. This is the standard integrity check
    published by CAS, and it is what catches "7647-01-0" mistyped as
    "7647-10-0". It says nothing about whether the substance is the right one.
    """
    m = CAS_RE.match(value)
    if not m:
        return False
    digits = (m.group(1) + m.group(2))[::-1]
    total = sum(int(d) * (i + 1) for i, d in enumerate(digits))
    return total % 10 == int(m.group(3))


class Command(BaseCommand):
    help = "Import CAS / purity / packaging from a filled-in missing_specs CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the filled-in CSV.")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change and write nothing.",
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help=(
                "Allow a CSV value to replace an existing, different value. "
                "Off by default so an already-verified spec is never silently "
                "clobbered by a stale sheet."
            ),
        )
        parser.add_argument(
            "--allow-bad-cas", action="store_true",
            help=(
                "Import CAS values that fail the check-digit test. Only for the "
                "rare legitimate case; the default is to skip and report them."
            ),
        )

    def handle(self, *args, **opts):
        path = opts["csv_path"]
        try:
            with open(path, newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except FileNotFoundError:
            raise CommandError(f"No such file: {path}")

        if not rows:
            raise CommandError("CSV is empty.")

        present = [c for c in COLUMNS if c in rows[0]]
        if not present:
            raise CommandError(
                f"CSV has none of the expected columns {list(COLUMNS)}. "
                f"Found: {list(rows[0])}"
            )
        if "slug" not in rows[0]:
            raise CommandError("CSV has no 'slug' column — products cannot be matched.")

        by_slug = {p.slug: p for p in Product.objects.all()}

        applied, skipped_blank, conflicts, bad_cas, unknown = [], 0, [], [], []
        to_save = {}

        for i, row in enumerate(rows, start=2):  # header is line 1
            slug = (row.get("slug") or "").strip()
            product = by_slug.get(slug)
            if not product:
                unknown.append((i, slug or "(blank)"))
                continue

            for column in present:
                field = COLUMNS[column]
                value = (row.get(column) or "").strip()

                if value.lower() in PLACEHOLDERS:
                    skipped_blank += 1
                    continue

                if field == "cas_number" and not cas_check_digit_ok(value):
                    if opts["allow_bad_cas"]:
                        self.stdout.write(self.style.WARNING(
                            f"  line {i}: {product.name} — CAS {value} fails the "
                            f"check digit, importing anyway (--allow-bad-cas)"
                        ))
                    else:
                        bad_cas.append((i, product.name, value))
                        continue

                current = str(getattr(product, field, "") or "").strip()
                if current and current != value:
                    if not opts["overwrite"]:
                        conflicts.append((i, product.name, column, current, value))
                        continue
                if current == value:
                    continue

                setattr(product, field, value)
                to_save.setdefault(product.pk, (product, set()))[1].add(field)
                applied.append((product.name, column, current or "(blank)", value))

        # -- report ---------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nRead {len(rows)} rows from {path}"
        ))

        if applied:
            self.stdout.write(self.style.MIGRATE_LABEL(
                f"\n{len(applied)} value(s) to set:"
            ))
            for name, column, old, new in applied[:60]:
                self.stdout.write(f"  {name[:38]:<40} {column:<12} {old} -> {new}")
            if len(applied) > 60:
                self.stdout.write(f"  … and {len(applied) - 60} more")
        else:
            self.stdout.write(self.style.WARNING("\nNothing to set."))

        if skipped_blank:
            self.stdout.write(self.style.HTTP_INFO(
                f"\n{skipped_blank} cell(s) still blank or MISSING — left untouched."
            ))

        if conflicts:
            self.stdout.write(self.style.ERROR(
                f"\n{len(conflicts)} conflict(s) — CSV disagrees with a value already "
                f"in the database. Skipped; re-run with --overwrite to apply:"
            ))
            for i, name, column, old, new in conflicts:
                self.stdout.write(f"  line {i}: {name[:34]:<36} {column}: db={old!r} csv={new!r}")

        if bad_cas:
            self.stdout.write(self.style.ERROR(
                f"\n{len(bad_cas)} CAS value(s) failed the registry check digit — "
                f"almost always a transcription slip. Skipped; fix the sheet and re-run:"
            ))
            for i, name, value in bad_cas:
                self.stdout.write(f"  line {i}: {name[:34]:<36} {value}")

        if unknown:
            self.stdout.write(self.style.ERROR(
                f"\n{len(unknown)} row(s) matched no product by slug — skipped:"
            ))
            for i, slug in unknown[:20]:
                self.stdout.write(f"  line {i}: {slug}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n--dry-run: nothing written.\n"))
            return

        if not to_save:
            self.stdout.write("")
            return

        # One transaction: a partial import would leave the catalogue in a state
        # nobody can reason about, and re-running the same sheet is meant to be
        # safe. Product.save() fires the post_save signal that revalidates the
        # affected pages, so the site picks these up without a deploy.
        with transaction.atomic():
            for product, fields in to_save.values():
                product.save(update_fields=sorted(fields) + ["updated_at"]
                             if hasattr(product, "updated_at") else sorted(fields))

        self.stdout.write(self.style.SUCCESS(
            f"\nUpdated {len(to_save)} product(s). Affected pages revalidate via "
            f"the post_save signal.\n"
        ))
