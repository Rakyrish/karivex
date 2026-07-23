from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, BlogPostViewSet, QuoteRequestViewSet, OrderViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet)
router.register("blog", BlogPostViewSet)
router.register("quotes", QuoteRequestViewSet)
router.register("orders", OrderViewSet)
urlpatterns = router.urls
