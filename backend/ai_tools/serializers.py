from rest_framework import serializers

from catalog.models import Product


class ProductDraftRequestSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    image_url = serializers.URLField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class StructuredContentRequestSerializer(serializers.Serializer):
    """Request for the full structured pipeline.

    Generation is always a preview by default. `apply` is what moves content
    onto the live product, and `apply_flat` is separate again because
    overwriting the existing `description`/`faqs` columns destroys prose that
    was already human-reviewed — an explicit opt-in, never a side effect.
    """
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    image_url = serializers.URLField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    apply = serializers.BooleanField(required=False, default=False)
    apply_flat = serializers.BooleanField(required=False, default=False)
    # Publishing content the validator rejected requires saying so explicitly.
    force = serializers.BooleanField(required=False, default=False)


class BulkGenerateRequestSerializer(serializers.Serializer):
    """Regenerate structured content for products that do not have it yet.

    Batched rather than run-to-completion: 174 products at roughly four model
    calls each would sit far past any sane HTTP timeout, and a request that
    dies half way leaves no record of where it got to. The caller asks for a
    small batch, gets a progress count back, and calls again — so progress is
    durable and the run can be stopped at any point.
    """
    limit = serializers.IntegerField(required=False, default=3, min_value=1, max_value=10)
    # False regenerates everything, including products already done.
    only_missing = serializers.BooleanField(required=False, default=True)
    # Narrow the run. Both optional; product_ids wins when both are given.
    product_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
        help_text="Regenerate exactly these products, in this order.")
    category = serializers.IntegerField(
        required=False, allow_null=True, default=None,
        help_text="Regenerate this category and its sub-categories.")


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=2000)


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
    history = ChatMessageSerializer(many=True, required=False, default=list)
