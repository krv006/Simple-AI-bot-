# orders/models.py
from django.db import models


class Order(models.Model):
    user_message_id = models.BigIntegerField(null=True, blank=True)
    user_id = models.BigIntegerField()
    username = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)

    group_id = models.BigIntegerField()
    group_title = models.CharField(max_length=255, null=True, blank=True)

    order_text = models.TextField()
    phones = models.JSONField(null=True, blank=True)  # yoki ArrayField
    location = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.id} - {self.chat_title or ''}"


class DatasetEntry(models.Model):
    """
    AI dataset uchun minimal model:
    - qaysi guruhdan kelgan
    - kim roli (client/operator/...)
    - real sms matn
    """
    chat_id = models.BigIntegerField()
    chat_title = models.CharField(max_length=255, null=True, blank=True)

    role = models.CharField(max_length=50)  # 'client', 'operator', ...
    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.chat_title} | {self.role}"
