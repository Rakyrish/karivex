from rest_framework import serializers

from catalog.models import BlogPost, Category, Product, QuoteRequest, Order


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class AdminProductSerializer(serializers.ModelSerializer):
    """Full read/write Product serializer for the admin control center.

    Unlike catalog.serializers.ProductDetailSerializer, `category` is left as
    the default writable PrimaryKeyRelatedField (that other serializer nests a
    read-only CategorySerializer, which is why it can't be reused for writes).
    SEO/slug fields are required=False + allow_blank (not read_only) so blank
    staff input still falls through to Product.save()'s own auto-fill
    guards, while explicit staff input is respected and persisted verbatim.
    """

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["ai_draft", "ai_draft_generated_at", "created_at", "updated_at"]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "meta_title": {"required": False, "allow_blank": True},
            "meta_description": {"required": False, "allow_blank": True},
            "image_alt": {"required": False, "allow_blank": True},
        }


class AdminProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "category_name", "grade", "price_kes",
                  "is_small_pack", "in_stock", "featured", "image", "updated_at"]


class AdminCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "meta_title", "meta_description", "product_count"]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "meta_title": {"required": False, "allow_blank": True},
        }


class AdminBlogPostSerializer(serializers.ModelSerializer):
    related_products = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), many=True, required=False
    )

    class Meta:
        model = BlogPost
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "published_at"]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "meta_title": {"required": False, "allow_blank": True},
            "meta_description": {"required": False, "allow_blank": True},
            "cover_image_alt": {"required": False, "allow_blank": True},
        }


class AdminQuoteSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)

    class Meta:
        model = QuoteRequest
        fields = ["id", "product", "product_name", "name", "company", "email", "phone",
                  "quantity", "country", "message", "created_at", "handled"]
        read_only_fields = ["id", "product", "product_name", "name", "company", "email",
                             "phone", "quantity", "country", "message", "created_at"]


class AdminOrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "product", "product_name", "quantity", "amount_kes", "customer_name",
                  "phone", "delivery_address", "mpesa_checkout_id", "mpesa_receipt",
                  "status", "created_at"]
        read_only_fields = ["id", "product", "product_name", "quantity", "amount_kes",
                             "customer_name", "phone", "delivery_address",
                             "mpesa_checkout_id", "mpesa_receipt", "created_at"]


class NewProductDraftRequestSerializer(serializers.Serializer):
    """Inputs for AI drafting a brand-new (not-yet-created) product. Notably
    no `description` field — that's the AI's output, not an input."""
    name = serializers.CharField(max_length=200)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    grade = serializers.ChoiceField(choices=Product.GRADE_CHOICES, required=False, default="industrial")
    cas_number = serializers.CharField(required=False, allow_blank=True, max_length=30)
    synonyms = serializers.CharField(required=False, allow_blank=True, max_length=300)
    purity = serializers.CharField(required=False, allow_blank=True, max_length=60)
    appearance = serializers.CharField(required=False, allow_blank=True, max_length=200)
    packaging = serializers.CharField(required=False, allow_blank=True, max_length=200)
    regions = serializers.CharField(required=False, allow_blank=True, max_length=200)
    focus_keyword = serializers.CharField(required=False, allow_blank=True, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    image_url = serializers.URLField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)


class MediaLibraryItemSerializer(serializers.ModelSerializer):
    """Read-only — powers the product form's 'choose from library' image
    picker so staff can reuse a photo already uploaded for another product
    instead of re-uploading the same file from disk."""

    class Meta:
        model = Product
        fields = ["id", "name", "image", "image_alt", "updated_at"]
