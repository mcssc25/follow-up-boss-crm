from django.contrib import admin

from .models import KeywordTrigger, MessageLog, SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = [
        'page_name', 'platform', 'team', 'is_active',
        'app_subscribed', 'webhook_verified', 'created_at',
    ]
    list_filter = ['platform', 'is_active', 'app_subscribed', 'webhook_verified']


@admin.register(KeywordTrigger)
class KeywordTriggerAdmin(admin.ModelAdmin):
    list_display = [
        'keyword', 'trigger_event', 'match_type',
        'platform', 'response_type', 'is_active', 'team',
    ]
    list_filter = ['platform', 'trigger_event', 'response_type', 'is_active', 'match_type']


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = [
        'sender_name', 'platform', 'event_type',
        'trigger_matched', 'reply_sent', 'timestamp',
    ]
    list_filter = ['platform', 'event_type', 'reply_sent']
    search_fields = ['sender_name', 'message_text']
