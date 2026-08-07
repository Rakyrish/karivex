from django.urls import path

from .views import (
    BulkGenerateView,
    ChatView,
    InternalLinkSuggestionsView,
    ProductAIDraftView,
    StructuredProductContentView,
)

urlpatterns = [
    path("draft-product/", ProductAIDraftView.as_view(), name="ai-draft-product"),
    path("structured-content/", StructuredProductContentView.as_view(), name="ai-structured-content"),
    path("bulk-generate/", BulkGenerateView.as_view(), name="ai-bulk-generate"),
    path("internal-links/<int:product_id>/", InternalLinkSuggestionsView.as_view(), name="ai-internal-links"),
    path("chat/", ChatView.as_view(), name="ai-chat"),
]
