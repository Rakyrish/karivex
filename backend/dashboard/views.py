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
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from ai_tools import services as ai_services
from ai_tools.utils import PageFetchError, fetch_page_text_from_url
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
    NewProductDraftRequestSerializer,
)

logger = logging.getLogger(__name__)


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
        serializer.save()

    def perform_update(self, serializer):
        self._maybe_attach_image_from_url(serializer)
        self._maybe_attach_image_from_library(serializer)
        serializer.save()


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
        except Exception:
            logger.exception("New-product AI draft generation failed")
            return Response({"detail": "AI content generation failed. Try again shortly."},
                             status=status.HTTP_502_BAD_GATEWAY)

        return Response(draft)
