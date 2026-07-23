from rest_framework import viewsets, mixins
from rest_framework.throttling import AnonRateThrottle

from .models import Category, Product, BlogPost, QuoteRequest, Order
from .serializers import (CategorySerializer, ProductListSerializer,
                          ProductDetailSerializer, BlogPostListSerializer,
                          BlogPostDetailSerializer, QuoteRequestSerializer, OrderSerializer)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related("category").all()
    lookup_field = "slug"
    filterset_fields = ["category__slug", "is_small_pack", "grade", "featured"]
    search_fields = ["name", "cas_number", "synonyms"]

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer


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
    """Creates a pending order. M-Pesa STK push wired in milestone 3."""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    throttle_classes = [QuoteBurstThrottle]
