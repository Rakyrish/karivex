import logging
import mimetypes
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from cloudinary.exceptions import Error as CloudinaryError

from ai_tools import services as ai_services
from ai_tools.utils import (
    PageFetchError,
    fetch_page_content_from_url,
    fetch_page_text_from_url,
    to_vision_data_uri,
)
from catalog.models import BlogPost, Category, Order, Product, QuoteRequest

from .authentication import make_token
from .utils import ImageFetchError, fetch_image_from_url
from .serializers import (
    AdminBlogPostSerializer,
    AdminCategorySerializer,
    AdminOrderSerializer,
    AdminProductListSerializer,
    AdminProductSerializer,
    AdminQuoteSerializer,
    LoginSerializer,
    MediaLibraryItemSerializer,
    ComposeProductRequestSerializer,
    NewProductDraftRequestSerializer,
)

logger = logging.getLogger(__name__)


class MediaStorageUnavailable(APIException):
    """Media storage (Cloudinary) rejected the upload.

    Worth its own class because the failure is a server misconfiguration, not
    bad staff input: without it a rejected upload escapes as an unhandled
    exception, Django returns an HTML 500, and the admin UI can only show a
    generic "Something went wrong" — hiding the one detail (e.g. "api_secret
    mismatch") that actually says how to fix it.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "The image could not be uploaded to Cloudinary, so nothing was saved. "
        "This is a server configuration problem, not something you did — check "
        "the CLOUDINARY_* credentials."
    )


def save_with_media_errors(serializer):
    """serializer.save(), but turn a media-storage rejection into a clear 503.

    The upload happens inside the model INSERT, so a failure here means the
    row was never written — safe to report as 'nothing was saved'.
    """
    try:
        serializer.save()
    except CloudinaryError as exc:
        logger.exception("Cloudinary rejected an upload")
        raise MediaStorageUnavailable(
            f"{MediaStorageUnavailable.default_detail} Cloudinary said: {exc}"
        )


class LoginThrottle(AnonRateThrottle):
    """Mirrors catalog.views.QuoteBurstThrottle's pattern — cost/abuse control
    on the new public attack surface this feature adds."""
    rate = "10/hour"


class LoginView(APIView):
    """Staff login for the Next.js admin control center — the SAME
    credentials as Django admin (django.contrib.auth.authenticate() against
    the same User table, same is_staff gate). No separate account system."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active or not user.is_staff:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        hours = getattr(settings, "DASHBOARD_SESSION_HOURS", 12)
        return Response({
            "token": make_token(user),
            "expires_in": hours * 3600,
            "user": {
                "username": user.username,
                "email": user.email,
                "is_superuser": user.is_superuser,
            },
        })


class MeView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        u = request.user
        return Response({"username": u.username, "email": u.email, "is_superuser": u.is_superuser})


class AdminProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["category", "grade", "in_stock", "featured", "is_small_pack"]
    search_fields = ["name", "cas_number", "synonyms"]

    def get_serializer_class(self):
        if self.action == "list":
            return AdminProductListSerializer
        return AdminProductSerializer

    def destroy(self, request, *args, **kwargs):
        # Order.product is on_delete=PROTECT — same rationale as
        # AdminCategoryViewSet.destroy below.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Can't delete a product that has existing orders."},
                status=status.HTTP_409_CONFLICT,
            )

    def _maybe_attach_image_from_url(self, serializer):
        """`image_url` isn't a Product field — it's a write-only convenience
        param recognized only here, letting staff paste a URL instead of
        uploading a file. The fetched bytes flow through the exact same
        ImageField (and therefore the exact same Cloudinary/local storage
        pipeline) as a real upload. No-ops if a file was already uploaded."""
        image_url = self.request.data.get("image_url")
        if not image_url or serializer.validated_data.get("image"):
            return
        try:
            serializer.validated_data["image"] = fetch_image_from_url(image_url)
        except ImageFetchError as exc:
            raise ValidationError({"image_url": str(exc)})

    def _maybe_attach_image_from_library(self, serializer):
        """`library_image_id` isn't a Product field — a write-only
        convenience param letting staff reuse a photo already uploaded for
        another product (see MediaLibraryView) instead of re-uploading the
        same file from disk. Copies the file bytes directly via Django's
        storage API rather than an HTTP round trip, so it works identically
        whether storage is local MEDIA or Cloudinary, with none of
        fetch_image_from_url's SSRF surface."""
        library_image_id = self.request.data.get("library_image_id")
        if not library_image_id or serializer.validated_data.get("image"):
            return
        try:
            source = Product.objects.get(pk=library_image_id)
        except (Product.DoesNotExist, ValueError, TypeError):
            raise ValidationError({"library_image_id": "That library image no longer exists."})
        if not source.image:
            raise ValidationError({"library_image_id": "That library image no longer exists."})
        with source.image.open("rb") as f:
            raw = f.read()
        name = source.image.name.rsplit("/", 1)[-1]
        content_type = mimetypes.guess_type(name)[0] or "image/jpeg"
        serializer.validated_data["image"] = SimpleUploadedFile(name, raw, content_type=content_type)

    def perform_create(self, serializer):
        self._maybe_attach_image_from_url(serializer)
        self._maybe_attach_image_from_library(serializer)
        save_with_media_errors(serializer)

    def perform_update(self, serializer):
        self._maybe_attach_image_from_url(serializer)
        self._maybe_attach_image_from_library(serializer)
        save_with_media_errors(serializer)


class AdminCategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = AdminCategorySerializer
    permission_classes = [permissions.IsAdminUser]

    def destroy(self, request, *args, **kwargs):
        # Product.category is on_delete=PROTECT — without this, deleting a
        # category that still has products raises ProtectedError, an
        # unhandled 500 rather than a real, actionable error message.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Can't delete a category that still has products. Move or delete its products first."},
                status=status.HTTP_409_CONFLICT,
            )


class AdminBlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.all().order_by("-created_at")
    serializer_class = AdminBlogPostSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["published"]
    search_fields = ["title", "excerpt", "body"]

    # cover_image lands in the same storage backend as product images.
    def perform_create(self, serializer):
        save_with_media_errors(serializer)

    def perform_update(self, serializer):
        save_with_media_errors(serializer)


class AdminQuoteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """List/retrieve/patch only — quotes are customer-submitted, staff can
    only triage (toggle `handled`), never create/delete via this API."""
    queryset = QuoteRequest.objects.select_related("product").all()
    serializer_class = AdminQuoteSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["handled", "country"]
    search_fields = ["name", "company", "email", "phone"]
    http_method_names = ["get", "patch", "head", "options"]


class AdminOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Order.objects.select_related("product").all()
    serializer_class = AdminOrderSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status"]
    search_fields = ["customer_name", "phone"]
    http_method_names = ["get", "patch", "head", "options"]


class StatsView(APIView):
    """Real, live-computed operational numbers for the dashboard home —
    no cached/mock data, one query per aggregate."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        products = Product.objects.aggregate(
            total=Count("id"),
            in_stock_count=Count("id", filter=Q(in_stock=True)),
            out_of_stock_count=Count("id", filter=Q(in_stock=False)),
            featured_count=Count("id", filter=Q(featured=True)),
        )
        categories_total = Category.objects.count()
        blog = BlogPost.objects.aggregate(
            published_count=Count("id", filter=Q(published=True)),
            draft_count=Count("id", filter=Q(published=False)),
        )
        since = timezone.now() - timedelta(days=7)
        quotes = QuoteRequest.objects.aggregate(
            total=Count("id"),
            unhandled=Count("id", filter=Q(handled=False)),
            last_7_days=Count("id", filter=Q(created_at__gte=since)),
        )
        orders = Order.objects.aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            paid=Count("id", filter=Q(status="paid")),
            delivered=Count("id", filter=Q(status="delivered")),
            cancelled=Count("id", filter=Q(status="cancelled")),
            revenue_kes=Sum("amount_kes", filter=Q(status__in=["paid", "delivered"])),
        )
        orders["revenue_kes"] = orders["revenue_kes"] or Decimal("0")

        recent_quotes = QuoteRequest.objects.select_related("product").order_by("-created_at")[:10]
        recent_orders = Order.objects.select_related("product").order_by("-created_at")[:10]
        activity = sorted(
            [
                {
                    "type": "quote", "id": q.id, "created_at": q.created_at, "handled": q.handled,
                    "summary": f"{q.name} — {q.product.name if q.product else 'general inquiry'} ({q.quantity})",
                }
                for q in recent_quotes
            ] + [
                {
                    "type": "order", "id": o.id, "created_at": o.created_at, "status": o.status,
                    "summary": f"{o.customer_name} — {o.product.name} × {o.quantity}",
                }
                for o in recent_orders
            ],
            key=lambda x: x["created_at"], reverse=True,
        )[:15]

        return Response({
            "products": products,
            "categories": {"total": categories_total},
            "blog": blog,
            "quotes": quotes,
            "orders": orders,
            "recent_activity": activity,
        })


class SeoAuditView(APIView):
    """Live, per-request SEO health audit across all public content — the
    dashboard's headline SEO feature, not an afterthought."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        issues = []
        checks = 0

        for p in Product.objects.select_related("category").all():
            checks += 4
            if not p.meta_title or len(p.meta_title) > 70:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "meta_title", "issue": "Missing or exceeds 70 characters"})
            if not p.meta_description or len(p.meta_description) > 160:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "meta_description", "issue": "Missing or exceeds 160 characters"})
            if not p.image:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "image", "issue": "No product image"})
            elif not p.image_alt:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "image_alt", "issue": "Missing alt text"})
            words = len((p.description or "").split())
            checks += 1
            if words < 400:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "description",
                                "issue": f"Only {words} words — competitor product pages commonly run "
                                         "1000+ words; aim for 400+ substantive, factual words"})
            checks += 1
            if not p.focus_keyword:
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "focus_keyword",
                                "issue": "No focus keyword set — needed to target a specific search phrase"})
            elif p.focus_keyword.lower() not in (p.meta_title or "").lower() and \
                    p.focus_keyword.lower() not in (p.meta_description or "").lower():
                issues.append({"type": "product", "id": p.id, "slug": p.slug, "name": p.name,
                                "field": "focus_keyword",
                                "issue": f"Focus keyword \"{p.focus_keyword}\" doesn't appear in the meta "
                                         "title or meta description"})

        for c in Category.objects.all():
            checks += 2
            if not c.meta_title or len(c.meta_title) > 70:
                issues.append({"type": "category", "id": c.id, "slug": c.slug, "name": c.name,
                                "field": "meta_title", "issue": "Missing or exceeds 70 characters"})
            if not c.meta_description or len(c.meta_description) > 160:
                issues.append({"type": "category", "id": c.id, "slug": c.slug, "name": c.name,
                                "field": "meta_description", "issue": "Missing or exceeds 160 characters"})

        for b in BlogPost.objects.filter(published=True):
            checks += 3
            if not b.meta_title or len(b.meta_title) > 70:
                issues.append({"type": "blog", "id": b.id, "slug": b.slug, "name": b.title,
                                "field": "meta_title", "issue": "Missing or exceeds 70 characters"})
            if not b.meta_description or len(b.meta_description) > 160:
                issues.append({"type": "blog", "id": b.id, "slug": b.slug, "name": b.title,
                                "field": "meta_description", "issue": "Missing or exceeds 160 characters"})
            if b.cover_image and not b.cover_image_alt:
                issues.append({"type": "blog", "id": b.id, "slug": b.slug, "name": b.title,
                                "field": "cover_image_alt", "issue": "Missing alt text"})

        score = round(100 * (1 - len(issues) / checks)) if checks else 100
        return Response({
            "score": max(score, 0),
            "checked_at": timezone.now(),
            "issue_count": len(issues),
            "issues": issues,
        })


class MediaLibraryView(APIView):
    """Staff-only. Read-only listing of products that already have a photo,
    for the product form's 'choose from library' image picker — lets staff
    reuse an existing upload instead of pulling the same file off their
    computer again. Actually attaching a picked image is handled by
    AdminProductViewSet._maybe_attach_image_from_library."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = Product.objects.exclude(image="").order_by("-updated_at")
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        serializer = MediaLibraryItemSerializer(qs[:60], many=True, context={"request": request})
        return Response(serializer.data)


class ResolveImageView(APIView):
    """Cheap, AI-free lookup so the UI can show the photo the moment a URL is
    pasted, before committing to the (slow, paid) drafting call. Handles both
    things staff paste: a direct image URL, or a product page whose photo we
    pull out of its og:image."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        url = str(request.data.get("url") or "").strip()
        if not url:
            return Response({"detail": "No URL supplied."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            page = fetch_page_content_from_url(url)
        except PageFetchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "image_url": page.image_url,
            "image_candidates": page.image_candidates,
            "is_image": page.is_image,
            "title": page.title,
        })


class ComposeProductView(APIView):
    """AI product composition from any one of three sources — a URL (product
    page or direct image), an uploaded photo, or just a name. Returns the
    extracted facts plus a full content draft. Nothing is saved: the response
    prefills a review form, and staff still create the product themselves."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = ComposeProductRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        url = (d.get("url") or "").strip()
        upload = d.get("image")
        name_hint = (d.get("name") or "").strip()

        categories = list(Category.objects.order_by("name"))
        if not categories:
            return Response(
                {"detail": "Create at least one category before adding products."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        category_names = [c.name for c in categories]

        source_text = source_title = ""
        image_for_vision = None
        image_url = ""
        image_candidates: list[str] = []

        if upload is not None:
            # The upload is only borrowed for vision here; the same file is
            # re-submitted by the browser on create, so nothing is stored yet.
            upload.seek(0)
            image_for_vision = to_vision_data_uri(
                upload.read(), getattr(upload, "content_type", "") or "image/jpeg"
            )
        elif url:
            try:
                page = fetch_page_content_from_url(url)
            except PageFetchError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            source_text, source_title = page.text, page.title
            image_url, image_candidates = page.image_url, page.image_candidates
            if image_url:
                # Fetch and inline the photo rather than handing OpenAI the
                # URL: it reuses the SSRF-hardened downloader, survives hosts
                # that block unknown fetchers, and lets us downscale first.
                try:
                    fetched = fetch_image_from_url(image_url)
                    image_for_vision = to_vision_data_uri(
                        fetched.read(), fetched.content_type or "image/jpeg"
                    )
                except ImageFetchError:
                    logger.info("Could not inline %s for vision; continuing without it", image_url)

        try:
            result = ai_services.generate_product_from_source(
                category_names=category_names,
                source_text=source_text,
                source_title=source_title,
                image=image_for_vision,
                name_hint=name_hint,
                notes=d.get("notes", ""),
                regions=", ".join(settings.SITE["regions"]),
            )
        except ai_services.AIConfigError:
            return Response({"detail": "AI content generation is not configured (missing OPENAI_API_KEY)."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ai_services.AIUnidentifiedError as exc:
            # Already a complete, staff-facing instruction — pass it straight through.
            logger.info("Compose-product could not identify a product (url=%r, upload=%s)",
                        url, upload is not None)
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ai_services.AIRefusalError as exc:
            # Retrying verbatim would refuse again, so say so plainly and
            # point at what staff can actually change.
            logger.warning("Compose-product refused (url=%r, upload=%s): %s",
                           url, upload is not None, exc)
            return Response(
                {"detail": (
                    "The AI declined to draft from that source. Try a different "
                    "page or photo, or enter the product name instead. "
                    "Reason given: " + str(exc)
                )},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception:
            logger.exception("Compose-product generation failed (url=%r)", url)
            return Response({"detail": "AI content generation failed. Try again shortly."},
                            status=status.HTTP_502_BAD_GATEWAY)

        # Map the AI's category *name* back to a real pk; never trust it blindly.
        by_name = {c.name: c.id for c in categories}
        result["category_id"] = by_name.get(result.get("category") or "", categories[0].id)
        result["source_url"] = url
        result["image_url"] = image_url
        result["image_candidates"] = image_candidates
        return Response(result)


class NewProductDraftView(APIView):
    """The 'create product with AI' entry point. Distinct from ai_tools'
    ProductAIDraftView, which requires an existing product pk — this one
    builds a transient, NEVER-SAVED Product instance from raw facts (plain
    Python object construction doesn't enforce blank=False, so no fake
    placeholder description is ever written to the database) and reuses the
    existing, unmodified ai_tools.services.generate_product_draft()."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = NewProductDraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        transient = Product(
            name=d["name"],
            category=d["category"],
            grade=d.get("grade") or "industrial",
            cas_number=d.get("cas_number", ""),
            synonyms=d.get("synonyms", ""),
            purity=d.get("purity", ""),
            appearance=d.get("appearance", ""),
            packaging=d.get("packaging", ""),
            regions=d.get("regions") or "Kenya, Uganda, Tanzania, Rwanda",
        )

        notes = d.get("notes", "")
        focus_keyword = d.get("focus_keyword", "")
        if focus_keyword:
            notes = (
                f"Target search phrase (work it naturally into the description, "
                f"meta_title and meta_description without keyword-stuffing): \"{focus_keyword}\". "
                + notes
            )

        source_url = d.get("source_url") or None
        source_text = None
        if source_url:
            try:
                source_text = fetch_page_text_from_url(source_url)
            except PageFetchError as exc:
                return Response({"detail": f"Source URL: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            draft = ai_services.generate_product_draft(
                transient, image_url=d.get("image_url") or None, notes=notes, source_text=source_text
            )
        except ai_services.AIConfigError:
            return Response({"detail": "AI content generation is not configured (missing OPENAI_API_KEY)."},
                             status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ai_services.AIRefusalError as exc:
            logger.warning("New-product AI draft refused: %s", exc)
            return Response(
                {"detail": "The AI declined to draft this product. Reason given: " + str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception:
            logger.exception("New-product AI draft generation failed")
            return Response({"detail": "AI content generation failed. Try again shortly."},
                             status=status.HTTP_502_BAD_GATEWAY)

        return Response(draft)
