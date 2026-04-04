from django.contrib import admin

from .models import KeywordTrigger, MessageLog, SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'platform', 'team', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active']


@admin.register(KeywordTrigger)
class KeywordTriggerAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'match_type', 'platform', 'is_active', 'team']
    list_filter = ['platform', 'is_active', 'match_type']


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ['sender_name', 'platform', 'trigger_matched', 'reply_sent', 'timestamp']
    list_filter = ['platform', 'reply_sent']
    search_fields = ['sender_name', 'message_text']
