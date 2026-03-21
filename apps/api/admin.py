from django.contrib import admin

from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'key', 'is_active', 'created_at')
    list_filter = ('is_active', 'team')
    search_fields = ('name', 'team__name')
    readonly_fields = ('key', 'created_at')
