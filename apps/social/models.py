from django.db import models


class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
    ]

    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='social_accounts',
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    page_id = models.CharField(max_length=100)
    page_name = models.CharField(max_length=255)
    access_token = models.TextField(help_text='Page Access Token from Meta OAuth')
    instagram_account_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Instagram Business Account ID (for IG-specific calls)',
    )
    is_active = models.BooleanField(default=True)
    webhook_verified = models.BooleanField(default=False)
    app_subscribed = models.BooleanField(default=False)
    last_webhook_at = models.DateTimeField(null=True, blank=True)
    last_webhook_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['team', 'page_id']

    def __str__(self):
        return f"{self.page_name} ({self.platform})"


class KeywordTrigger(models.Model):
    MATCH_TYPE_CHOICES = [
        ('exact', 'Exact Match'),
        ('contains', 'Contains'),
        ('starts_with', 'Starts With'),
    ]
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('both', 'Both'),
    ]
    TRIGGER_EVENT_CHOICES = [
        ('message', 'DM'),
        ('comment', 'Comment'),
        ('both', 'DM or Comment'),
    ]
    RESPONSE_TYPE_CHOICES = [
        ('message', 'Send DM'),
        ('private_reply', 'Private Reply to Comment'),
    ]

    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='keyword_triggers',
    )
    keyword = models.CharField(max_length=100)
    match_type = models.CharField(
        max_length=20, choices=MATCH_TYPE_CHOICES, default='contains',
    )
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, default='both',
    )
    trigger_event = models.CharField(
        max_length=20, choices=TRIGGER_EVENT_CHOICES, default='message',
    )
    is_active = models.BooleanField(default=True)
    reply_text = models.TextField(help_text='Auto-reply message body')
    response_type = models.CharField(
        max_length=20, choices=RESPONSE_TYPE_CHOICES, default='message',
    )
    reply_link = models.URLField(
        blank=True, default='',
        help_text='Optional link to include (PDF, video, landing page)',
    )
    tags = models.JSONField(default=list, blank=True)
    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='keyword_triggers',
    )
    create_contact = models.BooleanField(default=True)
    notify_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['keyword']

    def __str__(self):
        return f"{self.keyword} ({self.platform})"


class MessageLog(models.Model):
    EVENT_TYPE_CHOICES = [
        ('message', 'DM'),
        ('comment', 'Comment'),
    ]

    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=255, blank=True, default='')
    message_text = models.TextField()
    platform = models.CharField(max_length=20)
    event_type = models.CharField(
        max_length=20, choices=EVENT_TYPE_CHOICES, default='message',
    )
    external_event_id = models.CharField(max_length=100, blank=True, default='')
    comment_id = models.CharField(max_length=100, blank=True, default='')
    post_id = models.CharField(max_length=100, blank=True, default='')
    trigger_matched = models.ForeignKey(
        KeywordTrigger,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs',
    )
    contact_created = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_messages',
    )
    reply_sent = models.BooleanField(default=False)
    reply_error = models.TextField(blank=True, default='')
    raw_payload = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender_name}: {self.message_text[:50]}"
