from rest_framework import serializers
from .models import Category, Product, BlogPost, QuoteRequest, Order


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "meta_title", "meta_description", "product_count"]


class ProductListSerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Product
        fields = ["name", "slug", "category_slug", "purity", "packaging", "featured",
                  "is_small_pack", "price_kes", "in_stock", "image", "image_alt", "updated_at"]


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"


class RelatedProductSerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Product
        fields = ["name", "slug", "category_slug", "image", "image_alt"]


class BlogPostListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = ["title", "slug", "excerpt", "cover_image", "cover_image_alt", "published_at", "updated_at"]


class BlogPostDetailSerializer(serializers.ModelSerializer):
    related_products = RelatedProductSerializer(many=True, read_only=True)

    class Meta:
        model = BlogPost
        fields = ["title", "slug", "excerpt", "body", "cover_image", "cover_image_alt",
                  "related_products", "meta_title", "meta_description", "published_at", "updated_at"]


class QuoteRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteRequest
        fields = ["product", "name", "company", "email", "phone", "quantity", "country", "message"]
        extra_kwargs = {"product": {"required": False, "allow_null": True}}


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["product", "quantity", "amount_kes", "customer_name", "phone", "delivery_address"]
