from rest_framework.serializers import ModelSerializer

from apps.models import Order, DatasetEntry


class OrderSerializer(ModelSerializer):
    class Meta:
        model = Order
        fields = "__all__"


class DatasetEntrySerializer(ModelSerializer):
    class Meta:
        model = DatasetEntry
        fields = "__all__"
