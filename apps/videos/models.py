import uuid as uuid_lib

from django.conf import settings
from django.db import models
from django.urls import reverse


class Video(models.Model):
    STORAGE_LOCAL = 'local'
    STORAGE_YOUTUBE = 'youtube'
    STORAGE_CHOICES = [
        (STORAGE_LOCAL, 'Local'),
        (STORAGE_YOUTUBE, 'YouTube'),
    ]
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    video_file = models.FileField(upload_to='videos/', blank=True, null=True)
    youtube_id = models.CharField(max_length=20, blank=True)
    storage_type = models.CharField(max_length=10, choices=STORAGE_CHOICES, default=STORAGE_LOCAL)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    thumbnail = models.ImageField(upload_to='video_thumbnails/', blank=True, null=True)
    duration = models.PositiveIntegerField(default=0, help_text='Duration in seconds')
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='videos')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='videos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('videos:detail', kwargs={'pk': self.pk})

    def get_landing_url(self):
        return reverse('videos_public:landing', kwargs={'uuid': self.uuid})

    def get_full_landing_url(self):
        return f"https://crm.bigbeachal.com/v/{self.uuid}"

    def get_thumbnail_url(self):
        if self.thumbnail:
            return f"https://crm.bigbeachal.com{self.thumbnail.url}"
        return ''

    def get_email_snippet(self):
        landing = self.get_full_landing_url()
        thumb = self.get_thumbnail_url()
        return (
            f'<a href="{landing}">'
            f'<img src="{thumb}" alt="Click to watch video" '
            f'style="max-width:100%;border-radius:8px;">'
            f'</a>'
        )


class VideoView(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='views')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='video_views')
    tracking_token = models.UUIDField(default=uuid_lib.uuid4, unique=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    watched_duration = models.PositiveIntegerField(default=0, help_text='Seconds watched')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        who = self.contact or self.ip_address or 'Anonymous'
        return f"{who} viewed {self.video.title}"
