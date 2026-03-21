from django.conf import settings
from django.db import models


class Contact(models.Model):
    SOURCE_CHOICES = [
        ('landing_page', 'Landing Page'),
        ('manual', 'Manual Entry'),
        ('referral', 'Referral'),
        ('zillow', 'Zillow'),
        ('realtor', 'Realtor.com'),
        ('other', 'Other'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    source_detail = models.CharField(max_length=200, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class ContactNote(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.contact} by {self.author}"


class ContactActivity(models.Model):
    ACTIVITY_TYPES = [
        ('email_sent', 'Email Sent'),
        ('email_opened', 'Email Opened'),
        ('email_replied', 'Email Replied'),
        ('call_logged', 'Call Logged'),
        ('note_added', 'Note Added'),
        ('stage_changed', 'Stage Changed'),
        ('campaign_enrolled', 'Campaign Enrolled'),
        ('video_viewed', 'Video Viewed'),
    ]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'activities'

    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.contact}"
