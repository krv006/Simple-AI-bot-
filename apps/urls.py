from rest_framework.routers import DefaultRouter
from apps.views import OrderViewSet, DatasetEntryViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"dataset", DatasetEntryViewSet, basename="dataset")

urlpatterns = router.urls
