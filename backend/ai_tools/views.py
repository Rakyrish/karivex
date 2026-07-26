import logging

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from catalog.models import Product

from . import services
from .serializers import ChatRequestSerializer, ProductDraftRequestSerializer
from .utils import PageFetchError, fetch_page_text_from_url

logger = logging.getLogger(__name__)


class ChatThrottle(AnonRateThrottle):
    """Cost control on the public, unauthenticated chatbot endpoint."""
    rate = "20/hour"


class ProductAIDraftView(APIView):
    """Staff-only. Generates a content draft and stores it on
    Product.ai_draft — never touches the live published fields, so a human
    always reviews before anything reaches a public page."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = ProductDraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product: Product = serializer.validated_data["product"]
        image_url = serializer.validated_data.get("image_url") or None
        notes = serializer.validated_data.get("notes", "")
        source_url = serializer.validated_data.get("source_url") or None

        source_text = None
        if source_url:
            try:
                source_text = fetch_page_text_from_url(source_url)
            except PageFetchError as exc:
                return Response({"detail": f"Source URL: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            draft = services.generate_product_draft(product, image_url=image_url, notes=notes, source_text=source_text)
        except services.AIConfigError:
            return Response({"detail": "AI content generation is not configured (missing OPENAI_API_KEY)."},
                             status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("AI draft generation failed for product %s", product.pk)
            return Response({"detail": "AI content generation failed. Try again shortly."},
                             status=status.HTTP_502_BAD_GATEWAY)

        Product.objects.filter(pk=product.pk).update(ai_draft=draft, ai_draft_generated_at=timezone.now())
        return Response(draft)


class InternalLinkSuggestionsView(APIView):
    """Staff-only. Deterministic (no OpenAI call) related-content suggestions
    for manual internal linking."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, product_id: int):
        try:
            product = Product.objects.select_related("category").get(pk=product_id)
        except Product.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(services.suggest_internal_links(product))


class ChatView(APIView):
    """Public FAQ/product chatbot, answers only from company data — see
    ai_tools/services.py CHAT_SYSTEM_TEMPLATE for the safety guardrails."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ChatThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.answer_chat(
                serializer.validated_data["message"],
                serializer.validated_data.get("history", []),
            )
        except services.AIConfigError:
            return Response({"detail": "Chat is not configured right now — please call or WhatsApp us instead."},
                             status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Chat request failed")
            return Response({"detail": "Something went wrong — please call or WhatsApp us instead."},
                             status=status.HTTP_502_BAD_GATEWAY)

        return Response(result)
