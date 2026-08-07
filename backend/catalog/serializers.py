from rest_framework import serializers
from .models import Category, Product, BlogPost, QuoteRequest, Order


class CategoryChildSerializer(serializers.ModelSerializer):
    """Minimal shape for mega-menu children — no recursion, since the
    taxonomy is deliberately only two levels deep."""
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "product_count", "image", "image_alt"]


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)
    total_product_count = serializers.SerializerMethodField()
    children = CategoryChildSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "meta_title", "meta_description",
                  "product_count", "total_product_count", "parent", "display_order",
                  "image", "image_alt", "children"]

    def get_total_product_count(self, obj) -> int:
        """Products in this category *and* its sub-categories.

        Products are filed on the leaf ("Solvents & Thinners"), so an industry
        would otherwise report zero and read as empty in menus and cards even
        though it has stock. Two levels deep by design, so one hop covers it —
        and `children`/`products` are prefetched, so this costs no extra query.
        """
        return obj.products.count() + sum(c.products.count() for c in obj.children.all())


class ProductListSerializer(serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    canonical_path = serializers.SerializerMethodField()

    class Meta:
        model = Product
        # cas_number and synonyms are here for the site search: buyers search
        # by registry number ("7647-01-0") and by alternative names as often as
        # by the catalogue name, and the search filters this list client-side.
        fields = ["name", "slug", "category_slug", "category_name", "purity", "packaging",
                  "featured", "cas_number", "synonyms", "is_small_pack", "price_kes",
                  "in_stock", "stock_status", "image", "image_alt", "updated_at",
                  "canonical_path"]

    def get_canonical_path(self, obj) -> str | None:
        """The one field the sitemap needs out of `seo_assets`.

        The sitemap has to know which products canonicalise elsewhere so it can
        stop advertising duplicates, but this list is fetched by the frontend's
        root layout on every render and paged over in full. Serialising the
        whole `seo_assets` blob (headings, keyword sets, external references)
        for 182 products to read one short string would put tens of kilobytes
        on every page render. This exposes just the string.
        """
        return (obj.seo_assets or {}).get("canonical_path") or None


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
