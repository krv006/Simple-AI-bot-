# orders/views.py
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny

from apps.models import Order, DatasetEntry
from apps.serializers import OrderSerializer, DatasetEntrySerializer


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]


class DatasetEntryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DatasetEntry.objects.all()
    serializer_class = DatasetEntrySerializer
    permission_classes = [AllowAny]
