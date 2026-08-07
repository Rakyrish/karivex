"""Re-validate parked generation drafts and publish the ones that now pass.

When a generation run finishes, anything failing validation is stored on the
product as `ai_draft` instead of being published. If the validation rule that
blocked it is later corrected, those drafts are still good content sitting
unused — and regenerating them would pay the model a second time for output
that already exists.

So this re-runs `validate_content` over the STORED draft under today's rules and
publishes whatever now passes. No model calls, and nothing is written for a
draft that still fails.

The case it was written for: coercion drops interchangeable benefit headings, so
a product whose benefits were all boilerplate came back with an empty section —
which validation then treated as a missing required section and held the whole
page over. Benefits is a warning now, and these drafts became publishable
without anything being regenerated.

Dry run by default. Nothing is written without --apply.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_tools import validation
from ai_tools.services import _company_block, _product_record
from catalog.models import Product


class Command(BaseCommand):
    help = ("Re-validate parked ai_draft payloads under current rules and publish those "
            "that now pass. No model calls. Dry run unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the results. Without this, only reports.")
        parser.add_argument("--slug", action="append", default=[],
                            help="Only this product slug. Repeatable.")

    def handle(self, *args, **options):
        products = Product.objects.select_related("category").exclude(
            ai_draft={}).order_by("name")
        if options["slug"]:
            products = products.filter(slug__in=options["slug"])

        published = still_failing = skipped = 0
        for product in products:
            draft = product.ai_draft or {}
            sections = draft.get("sections")
            if not sections or not sections.get("summary"):
                skipped += 1
                continue

            seo = draft.get("seo") or {}
            report = validation.validate_content(
                sections=sections,
                seo=seo,
                image_seo=draft.get("image_seo") or {},
                meta_title=seo.get("meta_title", ""),
                meta_description=seo.get("meta_description", ""),
                product_name=product.name,
                supported_claims=_company_block(),
                product_record=_product_record(product),
                internal_links=draft.get("internal_links") or [],
                plan=draft.get("keyword_plan"),
                slug=product.slug,
            )

            if not report["publishable"]:
                still_failing += 1
                errors = [i["message"] for i in report["issues"] if i["severity"] == "error"]
                self.stdout.write(self.style.WARNING(
                    f"  –  {product.name} (score {report['score']}) still blocked:"))
                for message in errors[:3]:
                    self.stdout.write(f"         {message[:150]}")
                continue

            self.stdout.write(self.style.SUCCESS(
                f"  ✓  {product.name}: now publishable (score {report['score']})"))
            if options["apply"]:
                product.content_sections = sections
                product.seo_assets = seo
                product.image_seo = draft.get("image_seo") or {}
                product.internal_links = draft.get("internal_links") or []
                product.seo_score = report["score"]
                product.content_report = report
                product.content_generated_at = timezone.now()
                # The draft has been consumed; leaving it would show the admin a
                # pending suggestion identical to what is already live.
                product.ai_draft = {}
                # save() rather than update() so the revalidation signal fires.
                product.save()
            published += 1

        verb = "Published" if options["apply"] else "Would publish"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} {published} draft(s). {still_failing} still blocked, "
            f"{skipped} incomplete."))
        if not options["apply"] and published:
            self.stdout.write("Re-run with --apply to publish these.")
