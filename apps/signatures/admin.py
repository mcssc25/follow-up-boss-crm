from django.contrib import admin
from apps.signatures.models import (
    Document, DocumentSigner, DocumentField, SignerFieldValue,
    AuditEvent, DocumentTemplate, TemplateField,
)


class DocumentSignerInline(admin.TabularInline):
    model = DocumentSigner
    extra = 0


class DocumentFieldInline(admin.TabularInline):
    model = DocumentField
    extra = 0


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'created_by', 'created_at']
    list_filter = ['status']
    inlines = [DocumentSignerInline, DocumentFieldInline]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['document', 'event_type', 'signer', 'created_at']
    list_filter = ['event_type']


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'created_at']
