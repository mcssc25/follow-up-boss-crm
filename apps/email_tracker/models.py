import uuid

from django.db import models


class TrackedEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(auto_now_add=True)
    gmail_message_id = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['gmail_message_id']),
        ]

    def __str__(self):
        return f"{self.subject[:50]} ({self.sent_at:%Y-%m-%d %H:%M})"


class TrackedRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.ForeignKey(TrackedEmail, on_delete=models.CASCADE, related_name='recipients')
    recipient_address = models.EmailField()
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    def __str__(self):
        return f"{self.recipient_address} for {self.email.subject[:30]}"


class OpenEvent(models.Model):
    recipient = models.ForeignKey(TrackedRecipient, on_delete=models.CASCADE, related_name='opens')
    opened_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-opened_at']


class TrackedLink(models.Model):
    """Stores the original URL for a rewritten link."""
    email = models.ForeignKey(TrackedEmail, on_delete=models.CASCADE, related_name='links')
    link_hash = models.CharField(max_length=16, db_index=True)
    original_url = models.URLField(max_length=2048)

    class Meta:
        unique_together = [('email', 'link_hash')]

    def __str__(self):
        return f"{self.original_url[:60]}"


class ClickEvent(models.Model):
    recipient = models.ForeignKey(TrackedRecipient, on_delete=models.CASCADE, related_name='clicks')
    link = models.ForeignKey(TrackedLink, on_delete=models.CASCADE, related_name='clicks')
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-clicked_at']
