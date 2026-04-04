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
    access_token = models.TextField(help_text='Encrypted Page Access Token')
    instagram_account_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Instagram Business Account ID (for IG-specific calls)',
    )
    is_active = models.BooleanField(default=True)
    webhook_verified = models.BooleanField(default=False)
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
    is_active = models.BooleanField(default=True)
    reply_text = models.TextField(help_text='Auto-reply message body')
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
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=255, blank=True, default='')
    message_text = models.TextField()
    platform = models.CharField(max_length=20)
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
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender_name}: {self.message_text[:50]}"
