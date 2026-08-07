import logging
import threading

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from catalog.models import GenerationJob, Product

from . import services
from .serializers import (
    BulkGenerateRequestSerializer,
    ChatRequestSerializer,
    ProductDraftRequestSerializer,
    StructuredContentRequestSerializer,
)
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


class StructuredProductContentView(APIView):
    """Staff-only. Runs the full structured content pipeline.

    Default is preview-only: the payload is returned and parked on
    `ai_draft` for review, exactly like the flat drafter. `apply=true`
    promotes it to the live structured fields, and only if the validator
    passed — `force=true` overrides that, deliberately requiring an explicit
    decision to publish content with known defects.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = StructuredContentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product: Product = data["product"]

        source_text = None
        if data.get("source_url"):
            try:
                source_text = fetch_page_text_from_url(data["source_url"])
            except PageFetchError as exc:
                return Response({"detail": f"Source URL: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = services.generate_structured_product_content(
                product,
                image_url=data.get("image_url") or None,
                notes=data.get("notes", ""),
                source_text=source_text,
            )
        except services.AIConfigError:
            return Response({"detail": "AI content generation is not configured (missing OPENAI_API_KEY)."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except services.AIRefusalError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception("Structured content generation failed for product %s", product.pk)
            return Response({"detail": "AI content generation failed. Try again shortly."},
                            status=status.HTTP_502_BAD_GATEWAY)

        report = payload["report"]
        applied = False
        if data.get("apply"):
            if not report["publishable"] and not data.get("force"):
                return Response(
                    {"detail": "Content did not pass validation — resolve the errors "
                               "below or resend with force=true.",
                     **payload},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            self._apply(product, payload, apply_flat=data.get("apply_flat", False))
            applied = True
        else:
            Product.objects.filter(pk=product.pk).update(
                ai_draft=payload, ai_draft_generated_at=timezone.now()
            )

        return Response({**payload, "applied": applied})

    @staticmethod
    def _apply(product: Product, payload: dict, apply_flat: bool) -> None:
        fields = {
            "content_sections": payload["sections"],
            "seo_assets": payload["seo"],
            "image_seo": payload["image_seo"],
            "internal_links": payload["internal_links"],
            "seo_score": payload["score"],
            "content_report": payload["report"],
            "content_generated_at": timezone.now(),
        }
        if apply_flat:
            # Overwrites human-reviewed prose — only ever on an explicit
            # request from the caller.
            fields.update(payload["flat"])
        # save() rather than queryset.update() so the post_save revalidation
        # signal fires and the public page is actually purged.
        for key, value in fields.items():
            setattr(product, key, value)
        product.save()


class BulkGenerateView(APIView):
    """Staff-only. Regenerates structured content for a batch of products.

    Publishes only what passes validation; anything that fails is parked on
    `ai_draft` with its report so a human can look at it, exactly like the
    single-product path. A bulk run must never be a way to push content onto
    the site that the single-product route would have blocked.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """Progress plus everything the picker needs.

        One request rather than three: the panel shows the overall split, a
        per-category breakdown, and a product list to select from, and fetching
        those separately would let them disagree mid-run.
        """
        products = list(
            Product.objects.select_related("category")
            .only("id", "name", "content_sections", "seo_score", "category__id",
                  "category__name", "category__parent_id")
            .order_by("name")
        )
        done_ids = {p.pk for p in products if p.content_sections}

        categories: dict[int, dict] = {}
        for product in products:
            category = product.category
            # Roll sub-categories up into their industry so the picker mirrors
            # the two-level taxonomy buyers and staff actually see.
            key = category.parent_id or category.id
            name = (category.parent.name if category.parent_id else category.name)
            entry = categories.setdefault(key, {"id": key, "name": name, "total": 0, "done": 0})
            entry["total"] += 1
            entry["done"] += 1 if product.pk in done_ids else 0

        for entry in categories.values():
            entry["remaining"] = entry["total"] - entry["done"]

        # The most recent job, running or not, so the panel can reattach to a
        # run in progress after a page reload — the work continues on the
        # server whether or not the tab that started it is still open.
        job = GenerationJob.objects.first()

        return Response({
            "total": len(products),
            "done": len(done_ids),
            "remaining": len(products) - len(done_ids),
            "job": _job_payload(job) if job else None,
            "categories": sorted(categories.values(), key=lambda c: c["name"]),
            "products": [
                {"id": p.pk, "name": p.name,
                 "category_id": p.category.parent_id or p.category_id,
                 "category_name": p.category.name,
                 "done": p.pk in done_ids,
                 "score": p.seo_score}
                for p in products
            ],
        })

    def post(self, request):
        """Start a background run and return at once.

        The work is NOT done in this request. One product costs 30-60 seconds,
        and holding the connection open for a whole batch produced a 504 at
        nginx's 60-second default `proxy_read_timeout` — with the generation
        already completed and paid for, and the result thrown away. This
        returns a job id in milliseconds; the browser polls GET for progress.
        """
        serializer = BulkGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not settings.OPENAI_API_KEY:
            return Response(
                {"detail": "AI content generation is not configured (missing OPENAI_API_KEY)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # One run at a time. Two concurrent jobs would regenerate the same
        # products twice and pay for both.
        active = GenerationJob.objects.filter(status="running").first()
        if active:
            return Response({"detail": "A generation run is already in progress.",
                             "job": _job_payload(active)},
                            status=status.HTTP_409_CONFLICT)

        queryset = Product.objects.order_by("pk")
        if data.get("product_ids"):
            # An explicit selection is exactly that — "only missing" would
            # silently skip a product the user ticked to regenerate.
            queryset = queryset.filter(pk__in=data["product_ids"])
            scope = f"{len(data['product_ids'])} selected products"
        elif data.get("category"):
            queryset = queryset.filter(
                Q(category_id=data["category"]) | Q(category__parent_id=data["category"]))
            if data["only_missing"]:
                queryset = queryset.filter(content_sections={})
            scope = "category"
        else:
            if data["only_missing"]:
                queryset = queryset.filter(content_sections={})
            scope = "all remaining"

        product_ids = list(queryset.values_list("pk", flat=True))
        if not product_ids:
            return Response({"detail": "Nothing to generate — every product in that "
                                       "scope already has structured content."},
                            status=status.HTTP_400_BAD_REQUEST)

        job = GenerationJob.objects.create(
            scope=scope, product_ids=product_ids, total=len(product_ids))

        # A plain daemon thread rather than a task queue: this stack has no
        # broker, the run is staff-triggered and infrequent, and per-product
        # progress is already durable in the database — so a lost thread costs
        # nothing but a restart.
        threading.Thread(
            target=services.run_generation_job,
            args=(job.pk, product_ids),
            daemon=True,
            name=f"generation-job-{job.pk}",
        ).start()

        return Response(_job_payload(job), status=status.HTTP_202_ACCEPTED)

    def delete(self, request):
        """Ask the running job to stop after the product it is on."""
        updated = GenerationJob.objects.filter(status="running").update(cancel_requested=True)
        return Response({"cancelling": bool(updated)})


def _job_payload(job) -> dict:
    return {
        "id": job.pk,
        "status": job.status,
        "scope": job.scope,
        "total": job.total,
        "processed": job.processed,
        "published": job.published,
        "held": job.held,
        "failed": job.failed,
        "results": job.results or [],
        "detail": job.detail,
        "cancel_requested": job.cancel_requested,
    }


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
