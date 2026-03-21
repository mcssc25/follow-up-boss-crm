from django.contrib import admin

from apps.tasks.models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'assigned_to', 'due_date', 'status', 'priority', 'team']
    list_filter = ['status', 'priority', 'team']
    search_fields = ['title', 'description']
    raw_id_fields = ['assigned_to', 'contact']
