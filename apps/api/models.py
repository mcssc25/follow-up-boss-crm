import secrets

from django.db import models


class APIKey(models.Model):
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='api_keys',
    )
    key = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    name = models.CharField(max_length=100, help_text='e.g. "Landing Page"')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'

    def __str__(self):
        return f"{self.name} ({self.team})"
