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

from .models import Product, Category, BlogPost

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
        "/",           # homepage lists featured products
        "/sitemap.xml",
    ])


@receiver(post_save, sender=Category)
def revalidate_category(sender, instance: Category, **kwargs):
    _revalidate([f"/categories/{instance.slug}", "/"])


@receiver(post_save, sender=BlogPost)
@receiver(post_delete, sender=BlogPost)
def revalidate_blog_post(sender, instance: BlogPost, **kwargs):
    _revalidate([
        f"/blog/{instance.slug}",
        "/blog",
        "/",           # homepage lists latest posts
        "/sitemap.xml",
    ])
