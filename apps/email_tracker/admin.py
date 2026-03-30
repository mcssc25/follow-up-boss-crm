from django.contrib import admin

from .models import TrackedEmail, TrackedRecipient, OpenEvent, TrackedLink, ClickEvent


class TrackedRecipientInline(admin.TabularInline):
    model = TrackedRecipient
    extra = 0
    readonly_fields = ('tracking_id',)


class TrackedLinkInline(admin.TabularInline):
    model = TrackedLink
    extra = 0


@admin.register(TrackedEmail)
class TrackedEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sent_at', 'gmail_message_id')
    search_fields = ('subject', 'gmail_message_id')
    inlines = [TrackedRecipientInline, TrackedLinkInline]


@admin.register(OpenEvent)
class OpenEventAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'opened_at', 'ip_address')
    list_filter = ('opened_at',)


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'link', 'clicked_at', 'ip_address')
    list_filter = ('clicked_at',)
