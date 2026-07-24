from django.urls import path

from .views import ChatView, InternalLinkSuggestionsView, ProductAIDraftView

urlpatterns = [
    path("draft-product/", ProductAIDraftView.as_view(), name="ai-draft-product"),
    path("internal-links/<int:product_id>/", InternalLinkSuggestionsView.as_view(), name="ai-internal-links"),
    path("chat/", ChatView.as_view(), name="ai-chat"),
]
