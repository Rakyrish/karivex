from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminBlogPostViewSet,
    AdminCategoryViewSet,
    AdminOrderViewSet,
    AdminProductViewSet,
    AdminQuoteViewSet,
    LoginView,
    MediaLibraryView,
    MeView,
    NewProductDraftView,
    SeoAuditView,
    StatsView,
)

router = DefaultRouter()
router.register("products", AdminProductViewSet, basename="admin-products")
router.register("categories", AdminCategoryViewSet, basename="admin-categories")
router.register("blog", AdminBlogPostViewSet, basename="admin-blog")
router.register("quotes", AdminQuoteViewSet, basename="admin-quotes")
router.register("orders", AdminOrderViewSet, basename="admin-orders")

urlpatterns = [
    path("auth/login/", LoginView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("stats/", StatsView.as_view()),
    path("seo-audit/", SeoAuditView.as_view()),
    path("media-library/", MediaLibraryView.as_view()),
    # Top-level segment (not nested under products/) so it can never collide
    # with the router's products/<pk>/ detail route.
    path("ai/new-product-draft/", NewProductDraftView.as_view()),
] + router.urls
