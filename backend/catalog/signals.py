"""
Revalidation webhook: Django post_save -> Next.js /api/revalidate.

Same pattern as your other deployments — admin edits a product, the static
page is purged and regenerated on next request. No stale force-cache pages.
"""
import logging

import requests
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from django.db import transaction

from .models import Product, Category, BlogPost, QuoteRequest

from .emails import send_quote_emails

logger = logging.getLogger(__name__)


def _revalidate(paths: list[str]) -> None:
    url = f"{settings.FRONTEND_INTERNAL_URL}/api/revalidate"
    try:
        requests.post(
            url,
            json={"paths": paths, "secret": settings.REVALIDATE_SECRET},
            timeout=5,
        )
    except requests.RequestException as exc:
        # Never let a webhook failure break an admin save.
        logger.warning("Revalidation failed for %s: %s", paths, exc)


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def revalidate_product(sender, instance: Product, **kwargs):
    _revalidate([
        f"/products/{instance.slug}",
        f"/categories/{instance.category.slug}",
        "/products",   # the catalogue index — omitting it froze this page on
                       # its first render (2 products) while the API served 148
        "/",           # homepage lists featured products
        "/sitemap.xml",
    ])


@receiver(post_save, sender=Category)
def revalidate_category(sender, instance: Category, **kwargs):
    # /products carries the category rail, so it goes stale on category edits
    # too; the sitemap enumerates every category URL.
    _revalidate([
        f"/categories/{instance.slug}",
        "/products",
        "/",
        "/sitemap.xml",
    ])


@receiver(post_save, sender=BlogPost)
@receiver(post_delete, sender=BlogPost)
def revalidate_blog_post(sender, instance: BlogPost, **kwargs):
    _revalidate([
        f"/blog/{instance.slug}",
        "/blog",
        "/",           # homepage lists latest posts
        "/sitemap.xml",
    ])


@receiver(post_save, sender=QuoteRequest)
def notify_on_quote_request(sender, instance: QuoteRequest, created: bool, **kwargs):
    """
    Email staff (and acknowledge the customer) when a quote request comes in.

    Until this existed, QuoteRequestViewSet wrote the row and returned — no one
    was told. Enquiries sat in Postgres until somebody happened to open the
    admin dashboard, which for an inbound-quote business is lost revenue.

    `created` guards against re-sending every time staff tick `handled` in the
    admin. `on_commit` means nothing is emailed for a transaction that later
    rolls back, and guarantees the row is readable if the send path ever needs
    to re-query it.
    """
    if not created:
        return
    transaction.on_commit(lambda: send_quote_emails(instance))
