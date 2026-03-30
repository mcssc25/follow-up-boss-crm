from django.contrib import admin

from .models import Video, VideoView


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'storage_type', 'status', 'team', 'created_at']
    list_filter = ['storage_type', 'status', 'team']
    search_fields = ['title']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(VideoView)
class VideoViewAdmin(admin.ModelAdmin):
    list_display = ['video', 'contact', 'watched_duration', 'viewed_at']
    list_filter = ['viewed_at']
    readonly_fields = ['tracking_token', 'viewed_at']
