from django.contrib import admin

from apps.tasks.models import Task, TaskAssignment, TaskAttachment


class TaskAssignmentInline(admin.TabularInline):
    model = TaskAssignment
    extra = 1
    raw_id_fields = ['user']


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    readonly_fields = ['filename', 'uploaded_by', 'created_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'due_date', 'status', 'priority', 'team']
    list_filter = ['status', 'priority', 'team']
    search_fields = ['title', 'description']
    raw_id_fields = ['contact']
    inlines = [TaskAssignmentInline, TaskAttachmentInline]
