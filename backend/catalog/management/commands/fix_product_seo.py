"""Repair the SEO meta fields on products drafted by the old AI prompts.

The prompts in ai_tools.services now demand the focus keyword in the title and
a product-led snippet, and ai_tools.services.enforce_meta_* guarantee it for
anything generated from here on. Neither helps the 148 products already in the
database, which were written under the prompt that made these optional.

Measured on the live catalogue before this ran:
    109/148 (74%) meta descriptions opened with the word "Discover"
     60/148 (41%) meta titles contained no region term at all
     83/148 (56%) meta titles contained every word of their focus keyword

This is deliberately deterministic — no OpenAI call. Rewriting 148 snippets
through a model costs money, is non-reproducible, and risks changing claims
about purity or packaging. Stripping filler and appending a region is a
mechanical edit that cannot invent a fact.

    python manage.py fix_product_seo --dry-run    # show the diff, change nothing
    python manage.py fix_product_seo              # apply
"""

import time

from django.core.management.base import BaseCommand

from ai_tools.services import (
    MIN_DESCRIPTION_WORDS,
    enforce_meta_title,
    enforce_meta_description,
    has_banned_prose,
    restyle_description,
)
from catalog.models import Product


class Command(BaseCommand):
    help = "Normalise product meta_title / meta_description for search."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would change without writing to the database.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Only process the first N products (for spot-checking).",
        )
        parser.add_argument(
            "--rewrite-prose", action="store_true",
            help=(
                "Also send descriptions carrying templated AI phrasing back "
                "through the model for a style-only rewrite. Costs one API "
                "call per affected product — opt-in for that reason."
            ),
        )
        parser.add_argument(
            "--retries", type=int, default=2,
            help="Attempts per description before giving up and keeping the original.",
        )
        parser.add_argument(
            "--slugs", default="",
            help="Comma-separated slugs to restrict the run to (for reprocessing a subset).",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        qs = Product.objects.all().order_by("slug")
        if opts["slugs"]:
            wanted = [s.strip() for s in opts["slugs"].split(",") if s.strip()]
            qs = qs.filter(slug__in=wanted)
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        changed_title = changed_desc = 0
        touched = []

        if opts["rewrite_prose"]:
            self._rewrite_prose(qs, dry, opts["retries"])

        for p in qs:
            new_title = enforce_meta_title(p.meta_title, p.name, p.focus_keyword)
            new_desc = enforce_meta_description(p.meta_description, p.name, p.focus_keyword)

            t_diff = new_title != p.meta_title
            d_diff = new_desc != p.meta_description
            if not (t_diff or d_diff):
                continue

            if t_diff:
                changed_title += 1
                self.stdout.write(f"\n{p.slug}")
                self.stdout.write(f"  title  - {p.meta_title}")
                self.stdout.write(self.style.SUCCESS(f"  title  + {new_title}"))
            if d_diff:
                changed_desc += 1
                if not t_diff:
                    self.stdout.write(f"\n{p.slug}")
                self.stdout.write(f"  desc   - {p.meta_description}")
                self.stdout.write(self.style.SUCCESS(f"  desc   + {new_desc}"))

            p.meta_title = new_title
            p.meta_description = new_desc
            touched.append(p)

        if not dry and touched:
            # bulk_update deliberately: Product.save() fires the revalidation
            # webhook per row, which would mean 148 HTTP calls to Next.js for
            # what is one catalogue-wide edit. Callers revalidate once after.
            Product.objects.bulk_update(touched, ["meta_title", "meta_description"], batch_size=50)

        verb = "would change" if dry else "changed"
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            f"{verb}: {changed_title} titles, {changed_desc} descriptions "
            f"({len(touched)} products of {qs.count()})"
        ))
        if dry:
            self.stdout.write("Dry run — nothing written. Re-run without --dry-run to apply.")
        elif touched:
            self.stdout.write("Applied. Revalidate the affected pages so Next.js re-renders them.")

    def _rewrite_prose(self, qs, dry: bool, retries: int) -> None:
        """Style-only pass over descriptions still carrying templated phrasing.

        Every safeguard here exists because this is the one operation in the
        command that can lose content: it replaces 500+ words of live product
        copy with model output. restyle_description() already refuses anything
        short or still-templated and returns the original instead, so a failed
        call is a no-op rather than a regression.
        """
        candidates = [p for p in qs if has_banned_prose(p.description)]
        self.stdout.write(self.style.WARNING(
            f"\nProse rewrite: {len(candidates)} of {qs.count()} products carry templated phrasing."
        ))
        if dry:
            for p in candidates[:10]:
                hits = [ph for ph in ("when specifying or", "furthermore", "moreover",
                                      "additionally,", "in addition,")
                        if ph in p.description.lower()]
                self.stdout.write(f"  {p.slug}: {', '.join(hits)}")
            if len(candidates) > 10:
                self.stdout.write(f"  ... and {len(candidates) - 10} more")
            self.stdout.write("Dry run — no API calls made, nothing written.")
            return

        rewritten = failed = 0
        for i, p in enumerate(candidates, 1):
            original = p.description
            new = original
            for attempt in range(1, retries + 1):
                try:
                    new = restyle_description(original, p.focus_keyword, MIN_DESCRIPTION_WORDS)
                except Exception as exc:  # network/rate-limit/refusal
                    self.stderr.write(f"  {p.slug}: attempt {attempt} failed — {exc}")
                    time.sleep(2 * attempt)
                    continue
                if new != original:
                    break
            if new == original:
                failed += 1
                self.stdout.write(f"  [{i}/{len(candidates)}] {p.slug}: kept original")
                continue
            p.description = new
            p.save(update_fields=["description"])  # fires the revalidation webhook
            rewritten += 1
            before, after = len(original.split()), len(new.split())
            self.stdout.write(self.style.SUCCESS(
                f"  [{i}/{len(candidates)}] {p.slug}: rewritten ({before} → {after} words)"
            ))

        self.stdout.write(self.style.WARNING(
            f"Prose rewrite complete: {rewritten} rewritten, {failed} left unchanged."
        ))
