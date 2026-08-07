from django.db.models import Q
from rest_framework import viewsets, mixins
from rest_framework.throttling import AnonRateThrottle

from .models import Category, Product, BlogPost, QuoteRequest, Order
from .serializers import (CategorySerializer, ProductListSerializer,
                          ProductDetailSerializer, BlogPostListSerializer,
                          BlogPostDetailSerializer, QuoteRequestSerializer, OrderSerializer)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.prefetch_related("children", "products").all()
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        """`?top_level=1` returns just the industries (each with its children
        nested) — what the mega-menu, homepage grid and footer all want.
        Without it the flat list also contains all 50+ sub-categories."""
        qs = super().get_queryset()
        top_level = self.request.query_params.get("top_level")
        if top_level and top_level.lower() not in ("0", "false", "no"):
            qs = qs.filter(parent__isnull=True)
        return qs


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related("category").all()
    lookup_field = "slug"
    filterset_fields = ["category__slug", "is_small_pack", "grade", "featured"]
    search_fields = ["name", "cas_number", "synonyms"]

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    def get_queryset(self):
        """`?category_tree=<slug>` matches a category *and its children*.

        `category__slug` is an exact match, which is right for a leaf but wrong
        for a top-level industry: products hang off the sub-categories, never
        off the industry itself. So /categories/paints-inks-coatings rendered
        an empty grid under a meta description advertising "43 products in
        stock", and /categories/pulp-paper-packaging did the same with 5 —
        both of them URLs the sitemap actively asks Google to index. A page
        that contradicts its own snippet is the "Soft 404" / "Crawled –
        currently not indexed" verdict the rest of this codebase works to
        avoid.

        The taxonomy is exactly two deep (see Category.parent), so one level of
        `parent__slug` covers every descendant. For a leaf category — which has
        no children — this returns exactly what `category__slug` did.
        """
        qs = super().get_queryset()
        tree = self.request.query_params.get("category_tree")
        if tree:
            qs = qs.filter(Q(category__slug=tree) | Q(category__parent__slug=tree))
        return qs


class BlogPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Public API only ever exposes published posts, ordered newest first."""
    queryset = BlogPost.objects.filter(published=True).prefetch_related("related_products").order_by("-published_at")
    lookup_field = "slug"

    def get_serializer_class(self):
        return BlogPostDetailSerializer if self.action == "retrieve" else BlogPostListSerializer


class QuoteBurstThrottle(AnonRateThrottle):
    rate = "10/hour"  # spam protection on public form


class QuoteRequestViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = QuoteRequest.objects.all()
    serializer_class = QuoteRequestSerializer
    throttle_classes = [QuoteBurstThrottle]


class OrderViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Creates a pending order record. No payment is taken on the site."""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    throttle_classes = [QuoteBurstThrottle]
