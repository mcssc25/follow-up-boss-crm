from django.contrib import admin

from .models import Contact, ContactActivity, ContactNote, SmartList


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'source', 'assigned_to', 'team', 'created_at')
    list_filter = ('source', 'team', 'assigned_to', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    list_display = ('contact', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content',)
    readonly_fields = ('created_at',)


@admin.register(ContactActivity)
class ContactActivityAdmin(admin.ModelAdmin):
    list_display = ('contact', 'activity_type', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('description',)
    readonly_fields = ('created_at',)


@admin.register(SmartList)
class SmartListAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'created_at')
    list_filter = ('team',)
    search_fields = ('name',)
    readonly_fields = ('created_at',)
