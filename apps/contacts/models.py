from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class Tag(models.Model):
    """Reusable tag that can be applied to contacts."""
    name = models.CharField(max_length=100)
    color = models.CharField(
        max_length=7,
        default='#6366f1',
        help_text='Hex color code, e.g. #6366f1',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='tags',
    )

    class Meta:
        ordering = ['name']
        unique_together = ['name', 'team']

    def __str__(self):
        return self.name


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
    tag_objects = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='contacts',
    )
    custom_fields = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse('contacts:detail', kwargs={'pk': self.pk})


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


class SmartList(models.Model):
    name = models.CharField(max_length=200)
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='smart_lists',
    )
    filters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('contacts:smart_list_detail', kwargs={'pk': self.pk})

    def get_contacts(self):
        qs = Contact.objects.filter(team=self.team)
        f = self.filters

        if 'source' in f:
            qs = qs.filter(source=f['source'])

        if 'assigned_to' in f:
            qs = qs.filter(assigned_to_id=f['assigned_to'])

        if 'tags_contain' in f:
            qs = qs.filter(tags__contains=f['tags_contain'])

        if 'last_contacted_days_ago_gt' in f:
            cutoff = timezone.now() - timedelta(days=f['last_contacted_days_ago_gt'])
            qs = qs.filter(
                Q(last_contacted_at__lt=cutoff) | Q(last_contacted_at__isnull=True)
            )

        if 'created_days_ago_lt' in f:
            cutoff = timezone.now() - timedelta(days=f['created_days_ago_lt'])
            qs = qs.filter(created_at__gte=cutoff)

        if 'has_deal_in_stage' in f:
            qs = qs.filter(deals__stage_id=f['has_deal_in_stage'])

        if 'no_deal' in f and f['no_deal']:
            qs = qs.filter(deals__isnull=True)

        return qs.distinct()
