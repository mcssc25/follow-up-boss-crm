from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Team, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'team', 'gmail_connected', 'is_staff',
    )
    list_filter = BaseUserAdmin.list_filter + ('role', 'team', 'gmail_connected')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('CRM Profile', {
            'fields': ('role', 'team', 'phone', 'gmail_connected'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('CRM Profile', {
            'fields': ('role', 'team', 'phone'),
        }),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
