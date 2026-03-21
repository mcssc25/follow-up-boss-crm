from django.contrib.auth.models import AbstractUser
from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=100)
    lead_routing_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('agent', 'Agent'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='agent')
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    phone = models.CharField(max_length=20, blank=True)
    gmail_access_token = models.TextField(blank=True)
    gmail_refresh_token = models.TextField(blank=True)
    gmail_token_expiry = models.DateTimeField(null=True, blank=True)
    gmail_connected = models.BooleanField(default=False)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __str__(self):
        return self.get_full_name() or self.username
