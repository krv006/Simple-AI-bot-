# orders/admin.py
from django.contrib import admin

from apps.models import Order, DatasetEntry


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass


@admin.register(DatasetEntry)
class DatasetEntryAdmin(admin.ModelAdmin):
    pass
