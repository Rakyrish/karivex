from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Category, Product


def make_category(**kw):
    defaults = dict(name="Water Treatment Chemicals")
    defaults.update(kw)
    return Category.objects.create(**defaults)


def make_product(category, **kw):
    defaults = dict(
        category=category,
        name="Poly Aluminium Chloride",
        description="x" * 300,
    )
    defaults.update(kw)
    return Product.objects.create(**defaults)


class RevalidationSignalTests(TestCase):
    """Django post_save/post_delete -> Next.js /api/revalidate webhook."""

    @patch("catalog.signals.requests.post")
    def test_product_save_revalidates_product_category_home_and_sitemap(self, mock_post):
        category = make_category()
        mock_post.reset_mock()
        product = make_product(category)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        paths = kwargs["json"]["paths"]
        self.assertIn(f"/products/{product.slug}", paths)
        self.assertIn(f"/categories/{category.slug}", paths)
        self.assertIn("/", paths)
        self.assertIn("/sitemap.xml", paths)

    @patch("catalog.signals.requests.post")
    def test_product_delete_revalidates(self, mock_post):
        category = make_category()
        product = make_product(category)
        mock_post.reset_mock()
        slug = product.slug
        product.delete()

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn(f"/products/{slug}", kwargs["json"]["paths"])

    @patch("catalog.signals.requests.post")
    def test_webhook_failure_does_not_raise(self, mock_post):
        import requests
        mock_post.side_effect = requests.RequestException("connection refused")
        category = make_category()  # should not raise despite webhook failure
        self.assertTrue(Category.objects.filter(pk=category.pk).exists())

    @patch("catalog.signals.requests.post")
    def test_blog_post_save_revalidates_blog_paths(self, mock_post):
        from .models import BlogPost
        mock_post.reset_mock()
        post = BlogPost.objects.create(
            title="Where to Buy Hydrogen Peroxide in Nairobi",
            excerpt="A buyer's guide.",
            body="Body text.",
        )
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        paths = kwargs["json"]["paths"]
        self.assertIn(f"/blog/{post.slug}", paths)
        self.assertIn("/blog", paths)
        self.assertIn("/", paths)


class QuoteThrottleTests(APITestCase):
    """Public quote form is limited to 10 requests/hour per IP."""

    def setUp(self):
        cache.clear()

    def _payload(self):
        return {
            "name": "Jane Trader",
            "email": "jane@example.com",
            "phone": "+254700000000",
            "quantity": "10 x 25kg bags",
            "country": "Kenya",
        }

    def test_eleventh_request_in_an_hour_is_throttled(self):
        for _ in range(10):
            res = self.client.post("/api/quotes/", self._payload(), format="json")
            self.assertEqual(res.status_code, 201)

        res = self.client.post("/api/quotes/", self._payload(), format="json")
        self.assertEqual(res.status_code, 429)

    def test_quote_without_product_is_accepted(self):
        """General inquiries (no product) must be allowed — not every quote
        is tied to a single SKU."""
        res = self.client.post("/api/quotes/", self._payload(), format="json")
        self.assertEqual(res.status_code, 201)


class ProductMetaTitleTests(TestCase):
    def setUp(self):
        self.category = make_category()

    def test_auto_generated_meta_title_respects_cap(self):
        long_name = "Sodium Dodecylbenzene Sulfonate Technical Grade Surfactant Concentrate"
        product = make_product(self.category, name=long_name, meta_title="")
        self.assertLessEqual(len(product.meta_title), 70)
        self.assertTrue(product.meta_title.startswith("Buy "))

    def test_explicit_meta_title_is_not_overwritten(self):
        product = make_product(self.category, meta_title="Custom Title | Karivex")
        self.assertEqual(product.meta_title, "Custom Title | Karivex")

    def test_short_name_meta_title_is_within_cap(self):
        product = make_product(self.category, name="Alum", meta_title="")
        self.assertEqual(product.meta_title, "Buy Alum in Kenya | Karivex")
        self.assertLessEqual(len(product.meta_title), 70)
