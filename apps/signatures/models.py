import uuid
import hashlib
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class DocumentTemplate(models.Model):
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='signature_templates',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='signature_templates',
    )
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='signatures/templates/')
    signer_roles = models.JSONField(default=list, blank=True, help_text='List of role names, e.g. ["Buyer", "Seller"]')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class TemplateField(models.Model):
    FIELD_TYPES = [
        ('signature', 'Signature'),
        ('initials', 'Initials'),
        ('name', 'Name'),
        ('text', 'Text'),
        ('date', 'Date'),
        ('checkbox', 'Checkbox'),
    ]

    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    label = models.CharField(max_length=100, blank=True)
    signer_role = models.CharField(max_length=100, help_text='Role name this field is assigned to')
    page = models.PositiveIntegerField()
    x = models.FloatField(help_text='X position as percentage of page width')
    y = models.FloatField(help_text='Y position as percentage of page height')
    width = models.FloatField(help_text='Width as percentage of page width')
    height = models.FloatField(help_text='Height as percentage of page height')
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['page', 'y', 'x']

    def __str__(self):
        return f"{self.get_field_type_display()} on page {self.page} for {self.signer_role}"


class Document(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='signature_documents',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='signature_documents',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signature_documents',
    )
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='signatures/originals/')
    signed_pdf = models.FileField(upload_to='signatures/signed/', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    pdf_hash = models.CharField(max_length=64, blank=True, help_text='SHA-256 hash of signed PDF')
    is_archived = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True, help_text='List of tag strings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('signatures:detail', kwargs={'pk': self.pk})

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    @property
    def all_signed(self):
        return self.signers.exists() and not self.signers.exclude(status='completed').exists()


class DocumentFile(models.Model):
    """Tracks individual uploaded PDFs within a Document (for multi-file uploads)."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='source_files')
    original_filename = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='signatures/originals/')
    page_start = models.PositiveIntegerField(help_text='First page number in the merged PDF (1-based)')
    page_end = models.PositiveIntegerField(help_text='Last page number in the merged PDF (1-based)')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.original_filename} (pages {self.page_start}-{self.page_end})"


class DocumentSigner(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('opened', 'Opened'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='signers')
    name = models.CharField(max_length=200)
    email = models.EmailField()
    role = models.CharField(max_length=100, blank=True, help_text='e.g. Buyer, Seller')
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    signed_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} ({self.email})"

    def get_signing_url(self):
        return reverse('signatures:sign', kwargs={'token': self.access_token})


class DocumentField(models.Model):
    FIELD_TYPES = [
        ('signature', 'Signature'),
        ('initials', 'Initials'),
        ('name', 'Name'),
        ('text', 'Text'),
        ('date', 'Date'),
        ('checkbox', 'Checkbox'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='fields')
    assigned_to = models.ForeignKey(DocumentSigner, on_delete=models.CASCADE, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    label = models.CharField(max_length=100, blank=True)
    prefill_value = models.TextField(blank=True, help_text='Pre-filled value set by sender on the prepare page')
    read_only = models.BooleanField(default=False, help_text='If true, signer sees the value but cannot edit it')
    page = models.PositiveIntegerField()
    x = models.FloatField()
    y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['page', 'y', 'x']

    def __str__(self):
        return f"{self.get_field_type_display()} on page {self.page}"


class SignerFieldValue(models.Model):
    field = models.OneToOneField(DocumentField, on_delete=models.CASCADE, related_name='value')
    signer = models.ForeignKey(DocumentSigner, on_delete=models.CASCADE, related_name='field_values')
    value = models.TextField(help_text='Text value or base64 signature image')
    signed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Value for {self.field}"


class AuditEvent(models.Model):
    EVENT_TYPES = [
        ('created', 'Document Created'),
        ('sent', 'Document Sent'),
        ('opened', 'Document Opened'),
        ('field_signed', 'Field Signed'),
        ('completed', 'Signing Completed'),
        ('declined', 'Signing Declined'),
        ('downloaded', 'Document Downloaded'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='audit_events')
    signer = models.ForeignKey(DocumentSigner, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.document.title}"
