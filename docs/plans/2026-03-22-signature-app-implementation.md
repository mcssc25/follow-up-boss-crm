# E-Signature App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build DocuSign-like e-signature functionality as a Django app inside the existing CRM.

**Architecture:** New `apps/signatures` Django app using PDF.js for document rendering, vanilla JS drag-and-drop for field placement, HTML5 Canvas for signature capture, and PyPDF2 + ReportLab for server-side PDF stamping. All data team-scoped, signing via UUID token links.

**Tech Stack:** Django 5.1, PDF.js, PyPDF2, ReportLab, HTML5 Canvas, Tailwind CSS, HTMX

---

### Task 1: Add Dependencies & Create App Skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `apps/signatures/__init__.py`
- Create: `apps/signatures/apps.py`
- Create: `apps/signatures/admin.py`
- Create: `apps/signatures/urls.py`
- Create: `apps/signatures/views.py`
- Create: `apps/signatures/models.py`
- Create: `apps/signatures/forms.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`

**Step 1: Add PyPDF2 and ReportLab to requirements.txt**

Add these lines to `requirements.txt`:
```
PyPDF2>=3.0,<4.0
reportlab>=4.0,<5.0
```

**Step 2: Create the app directory and skeleton files**

```python
# apps/signatures/__init__.py
# (empty)
```

```python
# apps/signatures/apps.py
from django.apps import AppConfig

class SignaturesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.signatures'
    verbose_name = 'Signatures'
```

```python
# apps/signatures/admin.py
from django.contrib import admin
# Models registered in Task 3
```

```python
# apps/signatures/urls.py
from django.urls import path

app_name = 'signatures'

urlpatterns = []
```

```python
# apps/signatures/views.py
# Views added in later tasks
```

```python
# apps/signatures/models.py
# Models added in Task 2
```

```python
# apps/signatures/forms.py
# Forms added in later tasks
```

**Step 3: Register the app in settings.py**

Add `'apps.signatures'` to `PROJECT_APPS` list in `config/settings.py`.

**Step 4: Include URLs in config/urls.py**

Add this line to the urlpatterns in `config/urls.py`:
```python
path('signatures/', include('apps.signatures.urls')),
```

**Step 5: Install new dependencies**

Run: `pip install PyPDF2 reportlab`

**Step 6: Commit**

```bash
git add apps/signatures/ requirements.txt config/settings.py config/urls.py
git commit -m "feat(signatures): add app skeleton and dependencies"
```

---

### Task 2: Create Data Models

**Files:**
- Modify: `apps/signatures/models.py`

**Step 1: Write all models**

```python
# apps/signatures/models.py
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
        ('text', 'Text'),
        ('date', 'Date'),
        ('checkbox', 'Checkbox'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='fields')
    assigned_to = models.ForeignKey(DocumentSigner, on_delete=models.CASCADE, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    label = models.CharField(max_length=100, blank=True)
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
```

**Step 2: Create and run migrations**

```bash
python manage.py makemigrations signatures
python manage.py migrate
```

**Step 3: Register models in admin**

```python
# apps/signatures/admin.py
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
```

**Step 4: Commit**

```bash
git add apps/signatures/
git commit -m "feat(signatures): add data models for documents, signers, fields, audit"
```

---

### Task 3: Document List & Upload Views

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/forms.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/document_list.html`
- Create: `templates/signatures/document_create.html`
- Modify: `templates/base.html` (add sidebar link)

**Step 1: Create forms**

```python
# apps/signatures/forms.py
from django import forms
from apps.signatures.models import Document

INPUT_CLASS = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'


class DocumentCreateForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'pdf_file', 'expires_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Document title'}),
            'pdf_file': forms.FileInput(attrs={'class': INPUT_CLASS, 'accept': '.pdf'}),
            'expires_at': forms.DateTimeInput(attrs={'class': INPUT_CLASS, 'type': 'datetime-local'}),
        }

    def clean_pdf_file(self):
        f = self.cleaned_data.get('pdf_file')
        if f and not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Only PDF files are allowed.')
        if f and f.size > 50 * 1024 * 1024:  # 50MB limit
            raise forms.ValidationError('File size must be under 50MB.')
        return f
```

**Step 2: Create views for list and create**

```python
# apps/signatures/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, DeleteView
from django.urls import reverse_lazy

from apps.signatures.models import Document, AuditEvent
from apps.signatures.forms import DocumentCreateForm


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'signatures/document_list.html'
    context_object_name = 'documents'
    paginate_by = 25

    def get_queryset(self):
        qs = Document.objects.filter(
            team=self.request.user.team
        ).select_related('created_by').prefetch_related('signers')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentCreateForm
    template_name = 'signatures/document_create.html'

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        AuditEvent.objects.create(
            document=self.object,
            event_type='created',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        messages.success(self.request, 'Document uploaded. Now add signers and place fields.')
        return response

    def get_success_url(self):
        return reverse_lazy('signatures:prepare', kwargs={'pk': self.object.pk})
```

**Step 3: Add URL patterns**

```python
# apps/signatures/urls.py
from django.urls import path
from apps.signatures import views

app_name = 'signatures'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='list'),
    path('create/', views.DocumentCreateView.as_view(), name='create'),
]
```

**Step 4: Create templates**

Create `templates/signatures/document_list.html` — standard list template matching CRM pattern with search, status filter tabs, table of documents showing title, status badge, signers, created date, and action links.

Create `templates/signatures/document_create.html` — simple form template matching CRM pattern with file upload.

**Step 5: Add "Signatures" link to sidebar in `templates/base.html`**

Add a new sidebar nav item between Tasks and Reports:
```html
<a href="{% url 'signatures:list' %}" class="...">
    <!-- Pen/document icon -->
    Signatures
</a>
```

**Step 6: Commit**

```bash
git add apps/signatures/ templates/
git commit -m "feat(signatures): add document list and upload views"
```

---

### Task 4: Document Preparation Page (Add Signers + Field Placement UI)

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/document_prepare.html`
- Create: `static/signatures/js/field-placer.js`
- Create: `static/signatures/css/field-placer.css`

This is the core UI task — the drag-and-drop field placement on top of PDF.js.

**Step 1: Add prepare view**

Add to `views.py`:
```python
class DocumentPrepareView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'signatures/document_prepare.html'
    context_object_name = 'document'

    def get_queryset(self):
        return Document.objects.filter(team=self.request.user.team, status='draft')
```

Add API views for managing signers and fields via HTMX/fetch:
```python
@login_required
@require_POST
def add_signer(request, pk):
    """Add a signer to a document."""
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', '').strip()
    if name and email:
        DocumentSigner.objects.create(document=doc, name=name, email=email, role=role)
    return redirect('signatures:prepare', pk=pk)

@login_required
@require_POST
def save_fields(request, pk):
    """Save field placements from the JS field placer (JSON body)."""
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    data = json.loads(request.body)
    doc.fields.all().delete()  # Replace all fields
    for f in data.get('fields', []):
        DocumentField.objects.create(
            document=doc,
            assigned_to_id=f['signer_id'],
            field_type=f['type'],
            label=f.get('label', ''),
            page=f['page'],
            x=f['x'], y=f['y'],
            width=f['width'], height=f['height'],
            required=f.get('required', True),
        )
    return JsonResponse({'status': 'ok'})
```

**Step 2: Add URL patterns**

```python
path('<int:pk>/prepare/', views.DocumentPrepareView.as_view(), name='prepare'),
path('<int:pk>/signers/add/', views.add_signer, name='add_signer'),
path('<int:pk>/signers/<int:signer_pk>/delete/', views.delete_signer, name='delete_signer'),
path('<int:pk>/fields/save/', views.save_fields, name='save_fields'),
```

**Step 3: Create the preparation template**

`templates/signatures/document_prepare.html` — Layout:
- Left sidebar: signer list (add/remove), field toolbar (drag signature, initials, text, date, checkbox)
- Center: PDF.js viewer rendering the uploaded PDF
- Fields are draggable from toolbar onto PDF pages
- Each field is resizable and shows the assigned signer's color
- "Save & Send" button at bottom

**Step 4: Create field-placer.js**

`static/signatures/js/field-placer.js` — Core JavaScript:
- Initialize PDF.js to render all pages of the PDF into canvas elements
- Create an overlay div on top of each page canvas for field placement
- Toolbar buttons create draggable field elements
- Fields snap to page boundaries, are resizable via corner handles
- Each field stores: type, page, x%, y%, width%, height%, signer_id
- Color-code fields by signer (predefined palette)
- Save button POSTs all field data as JSON to the save_fields endpoint
- Load existing fields on page load (for editing)

**Step 5: Create field-placer.css**

`static/signatures/css/field-placer.css` — Styles for field overlays, drag handles, signer colors, toolbar.

**Step 6: Commit**

```bash
git add apps/signatures/ templates/signatures/ static/signatures/
git commit -m "feat(signatures): add document preparation UI with drag-and-drop fields"
```

---

### Task 5: Send Document & Email Notifications

**Files:**
- Create: `apps/signatures/tasks.py`
- Create: `apps/signatures/email.py`
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/emails/signing_request.html`
- Create: `templates/signatures/emails/signing_complete.html`

**Step 1: Create email helper**

```python
# apps/signatures/email.py
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_signing_request(signer, request=None):
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    signing_url = f"{base_url}{signer.get_signing_url()}"
    context = {
        'signer': signer,
        'document': signer.document,
        'signing_url': signing_url,
    }
    html = render_to_string('signatures/emails/signing_request.html', context)
    send_mail(
        subject=f"Please sign: {signer.document.title}",
        message=f"You have a document to sign. Visit: {signing_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[signer.email],
        html_message=html,
    )


def send_completion_notification(document):
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    context = {
        'document': document,
        'download_url': f"{base_url}/signatures/{document.pk}/download/",
    }
    html = render_to_string('signatures/emails/signing_complete.html', context)
    if document.created_by:
        send_mail(
            subject=f"Completed: {document.title}",
            message=f"All signers have completed {document.title}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[document.created_by.email],
            html_message=html,
        )
```

**Step 2: Create send view**

Add to `views.py`:
```python
@login_required
@require_POST
def send_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    if not doc.signers.exists():
        messages.error(request, 'Add at least one signer before sending.')
        return redirect('signatures:prepare', pk=pk)
    if not doc.fields.exists():
        messages.error(request, 'Place at least one field before sending.')
        return redirect('signatures:prepare', pk=pk)
    doc.status = 'sent'
    doc.save()
    for signer in doc.signers.all():
        send_signing_request(signer)
    AuditEvent.objects.create(
        document=doc, event_type='sent',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    # Log activity on linked contact
    if doc.contact:
        from apps.contacts.models import ContactActivity
        ContactActivity.objects.create(
            contact=doc.contact, team=doc.team,
            activity_type='document_sent',
            description=f'Document sent for signature: {doc.title}',
        )
    messages.success(request, 'Document sent to all signers.')
    return redirect('signatures:detail', pk=pk)
```

**Step 3: Create email templates**

Simple, clean HTML emails with a prominent "Review & Sign" button linking to the signing URL.

**Step 4: Add URL**

```python
path('<int:pk>/send/', views.send_document, name='send'),
```

**Step 5: Commit**

```bash
git add apps/signatures/ templates/signatures/
git commit -m "feat(signatures): add send document with email notifications"
```

---

### Task 6: Document Detail View

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/document_detail.html`

**Step 1: Add detail view**

```python
class DocumentDetailView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'signatures/document_detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return Document.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['signers'] = self.object.signers.all()
        ctx['audit_events'] = self.object.audit_events.all()
        return ctx
```

**Step 2: Create template**

Shows document title, status, signers with their statuses, and full audit trail timeline.

**Step 3: Add URL**

```python
path('<int:pk>/', views.DocumentDetailView.as_view(), name='detail'),
```

**Step 4: Commit**

```bash
git add apps/signatures/ templates/signatures/
git commit -m "feat(signatures): add document detail view with audit trail"
```

---

### Task 7: Client Signing Experience

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/sign.html`
- Create: `static/signatures/js/signing.js`

This is the public-facing signing page — no login required.

**Step 1: Add signing views**

```python
def sign_document(request, token):
    """Public signing page — no login required."""
    signer = get_object_or_404(DocumentSigner, access_token=token)
    doc = signer.document

    if doc.is_expired:
        doc.status = 'expired'
        doc.save()
        return render(request, 'signatures/sign_expired.html')

    if signer.status == 'completed':
        return render(request, 'signatures/sign_already_completed.html', {'signer': signer})

    if signer.status == 'pending':
        signer.status = 'opened'
        signer.save()
        AuditEvent.objects.create(
            document=doc, signer=signer, event_type='opened',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        if doc.status == 'sent':
            doc.status = 'viewed'
            doc.save()

    fields = DocumentField.objects.filter(
        document=doc, assigned_to=signer
    ).order_by('page', 'y')

    return render(request, 'signatures/sign.html', {
        'signer': signer,
        'document': doc,
        'fields': fields,
    })


@require_POST
@csrf_exempt
def submit_signing(request, token):
    """Process submitted field values from signing page."""
    signer = get_object_or_404(DocumentSigner, access_token=token)
    doc = signer.document

    if signer.status == 'completed' or doc.is_expired:
        return JsonResponse({'error': 'Cannot sign'}, status=400)

    data = json.loads(request.body)

    for field_data in data.get('fields', []):
        field = get_object_or_404(DocumentField, pk=field_data['field_id'], assigned_to=signer)
        SignerFieldValue.objects.update_or_create(
            field=field, signer=signer,
            defaults={'value': field_data['value']},
        )
        AuditEvent.objects.create(
            document=doc, signer=signer, event_type='field_signed',
            detail=f"Signed {field.get_field_type_display()} on page {field.page}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    signer.status = 'completed'
    signer.signed_at = timezone.now()
    signer.ip_address = request.META.get('REMOTE_ADDR')
    signer.user_agent = request.META.get('HTTP_USER_AGENT', '')
    signer.save()

    AuditEvent.objects.create(
        document=doc, signer=signer, event_type='completed',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    if doc.all_signed:
        from apps.signatures.pdf import generate_signed_pdf
        generate_signed_pdf(doc)
        doc.status = 'completed'
        doc.completed_at = timezone.now()
        doc.save()
        send_completion_notification(doc)
        if doc.contact:
            from apps.contacts.models import ContactActivity
            ContactActivity.objects.create(
                contact=doc.contact, team=doc.team,
                activity_type='document_signed',
                description=f'Document signed: {doc.title}',
            )

    return JsonResponse({'status': 'ok', 'completed': doc.all_signed})
```

**Step 2: Create signing template**

`templates/signatures/sign.html` — Standalone page (does NOT extend base.html, no CRM chrome):
- Clean, professional layout with document title and sender info
- PDF.js renders the document
- Assigned fields highlighted with guided step-by-step flow
- Signature fields: HTML5 Canvas draw pad + type-to-sign toggle (script font)
- "Finish Signing" button submits all values via fetch POST
- Confirmation message after completion

**Step 3: Create signing.js**

`static/signatures/js/signing.js`:
- Renders PDF via PDF.js
- Overlays assigned fields on correct pages
- Signature capture: Canvas with mouse/touch drawing, clear button, type-to-sign option
- Guided mode: highlights current field, scrolls to it
- Validates all required fields filled before submission
- Submits field values as JSON, shows confirmation on success

**Step 4: Add URLs**

```python
path('sign/<uuid:token>/', views.sign_document, name='sign'),
path('sign/<uuid:token>/submit/', views.submit_signing, name='submit_signing'),
```

**Step 5: Commit**

```bash
git add apps/signatures/ templates/signatures/ static/signatures/
git commit -m "feat(signatures): add client signing experience"
```

---

### Task 8: PDF Generation (Stamp Signatures onto PDF)

**Files:**
- Create: `apps/signatures/pdf.py`

**Step 1: Create PDF stamping module**

```python
# apps/signatures/pdf.py
import hashlib
import io
import base64
from datetime import datetime

from django.core.files.base import ContentFile
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from apps.signatures.models import SignerFieldValue, AuditEvent


def generate_signed_pdf(document):
    """Stamp all signer field values onto the original PDF and save."""
    reader = PdfReader(document.pdf_file)
    writer = PdfWriter()

    # Collect all field values grouped by page
    field_values = SignerFieldValue.objects.filter(
        field__document=document
    ).select_related('field', 'field__assigned_to', 'signer')

    pages_fields = {}
    for fv in field_values:
        page_num = fv.field.page
        if page_num not in pages_fields:
            pages_fields[page_num] = []
        pages_fields[page_num].append(fv)

    for page_num, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        if page_num in pages_fields:
            # Create overlay with reportlab
            overlay_buffer = io.BytesIO()
            c = pdf_canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

            for fv in pages_fields[page_num]:
                field = fv.field
                x = field.x / 100 * page_width
                # PDF y-coordinates are from bottom
                y = page_height - (field.y / 100 * page_height) - (field.height / 100 * page_height)
                w = field.width / 100 * page_width
                h = field.height / 100 * page_height

                if field.field_type in ('signature', 'initials') and fv.value.startswith('data:image'):
                    # Base64 image
                    img_data = base64.b64decode(fv.value.split(',')[1])
                    img = ImageReader(io.BytesIO(img_data))
                    c.drawImage(img, x, y, w, h, preserveAspectRatio=True, mask='auto')
                elif field.field_type == 'checkbox':
                    if fv.value == 'true':
                        c.setFont('Helvetica-Bold', min(h * 0.8, 14))
                        c.drawString(x + 2, y + 2, '✓')
                else:
                    # Text, date, typed signature
                    c.setFont('Helvetica', min(h * 0.7, 12))
                    c.drawString(x + 2, y + h * 0.25, fv.value)

            c.save()
            overlay_buffer.seek(0)
            overlay_reader = PdfReader(overlay_buffer)
            page.merge_page(overlay_reader.pages[0])

        writer.add_page(page)

    # Append audit trail certificate page
    audit_page = generate_audit_certificate(document)
    audit_reader = PdfReader(io.BytesIO(audit_page))
    writer.add_page(audit_reader.pages[0])

    # Write final PDF
    output = io.BytesIO()
    writer.write(output)
    pdf_bytes = output.getvalue()

    # Compute hash
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    document.pdf_hash = pdf_hash

    # Save signed PDF
    filename = f"signed_{document.pk}_{document.title[:50]}.pdf"
    document.signed_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    document.save()

    return pdf_bytes


def generate_audit_certificate(document):
    """Generate a PDF page with the audit trail."""
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - inch
    c.setFont('Helvetica-Bold', 16)
    c.drawString(inch, y, 'Audit Trail Certificate')
    y -= 30

    c.setFont('Helvetica', 10)
    c.drawString(inch, y, f'Document: {document.title}')
    y -= 15
    c.drawString(inch, y, f'Document ID: {document.pk}')
    y -= 15
    c.drawString(inch, y, f'Created: {document.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
    y -= 25

    # Signers
    c.setFont('Helvetica-Bold', 12)
    c.drawString(inch, y, 'Signers')
    y -= 18
    c.setFont('Helvetica', 10)
    for signer in document.signers.all():
        c.drawString(inch, y, f'{signer.name} ({signer.email})')
        y -= 14
        if signer.signed_at:
            c.drawString(inch + 20, y, f'Signed: {signer.signed_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
            y -= 14
            c.drawString(inch + 20, y, f'IP: {signer.ip_address or "N/A"}')
            y -= 18

    # Events
    y -= 10
    c.setFont('Helvetica-Bold', 12)
    c.drawString(inch, y, 'Event Log')
    y -= 18
    c.setFont('Helvetica', 9)
    for event in document.audit_events.all():
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont('Helvetica', 9)
        line = f'{event.created_at.strftime("%Y-%m-%d %H:%M:%S")} | {event.get_event_type_display()}'
        if event.signer:
            line += f' | {event.signer.name}'
        if event.ip_address:
            line += f' | IP: {event.ip_address}'
        c.drawString(inch, y, line)
        y -= 13

    c.save()
    return buffer.getvalue()
```

**Step 2: Commit**

```bash
git add apps/signatures/pdf.py
git commit -m "feat(signatures): add PDF stamping and audit certificate generation"
```

---

### Task 9: Download & Verify Endpoints

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/verify.html`

**Step 1: Add download view**

```python
@login_required
def download_signed(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='completed')
    AuditEvent.objects.create(
        document=doc, event_type='downloaded',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    response = FileResponse(doc.signed_pdf.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{doc.title} - Signed.pdf"'
    return response


def verify_document(request):
    """Public endpoint to verify a signed PDF hasn't been tampered with."""
    result = None
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        uploaded = request.FILES['pdf_file'].read()
        file_hash = hashlib.sha256(uploaded).hexdigest()
        doc = Document.objects.filter(pdf_hash=file_hash).first()
        if doc:
            result = {'verified': True, 'document': doc}
        else:
            result = {'verified': False}
    return render(request, 'signatures/verify.html', {'result': result})
```

**Step 2: Add URLs**

```python
path('<int:pk>/download/', views.download_signed, name='download'),
path('verify/', views.verify_document, name='verify'),
```

**Step 3: Commit**

```bash
git add apps/signatures/ templates/signatures/
git commit -m "feat(signatures): add download and verify endpoints"
```

---

### Task 10: Templates Feature

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/forms.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/template_list.html`
- Create: `templates/signatures/template_create.html`
- Create: `templates/signatures/template_prepare.html`
- Create: `templates/signatures/document_from_template.html`

**Step 1: Add template CRUD views**

Standard ListView, CreateView for DocumentTemplate. A prepare view similar to Task 4 but with role-based field assignment instead of specific signers. A "use template" view that creates a new Document from a template, copies fields, and lets user assign real signers to roles.

**Step 2: Add URLs**

```python
path('templates/', views.TemplateListView.as_view(), name='template_list'),
path('templates/create/', views.TemplateCreateView.as_view(), name='template_create'),
path('templates/<int:pk>/prepare/', views.TemplatePrepareView.as_view(), name='template_prepare'),
path('templates/<int:pk>/use/', views.use_template, name='use_template'),
```

**Step 3: Commit**

```bash
git add apps/signatures/ templates/signatures/
git commit -m "feat(signatures): add document templates"
```

---

### Task 11: Delete, Resend, Decline, and Polish

**Files:**
- Modify: `apps/signatures/views.py`
- Modify: `apps/signatures/urls.py`
- Create: `templates/signatures/sign_expired.html`
- Create: `templates/signatures/sign_already_completed.html`
- Create: `templates/signatures/sign_confirmation.html`

**Step 1: Add utility views**

- `delete_document` — Delete draft documents
- `resend_to_signer` — Resend signing email to a specific signer
- `decline_signing` — Allow signer to decline (POST from signing page)
- Signing confirmation page after completion
- Expired/already-completed pages

**Step 2: Add URLs and commit**

```bash
git add apps/signatures/ templates/signatures/
git commit -m "feat(signatures): add delete, resend, decline, and status pages"
```

---

### Task 12: Docker & Deployment Updates

**Files:**
- Modify: `docker-compose.yml` (ensure media volume covers signatures)
- Modify: `docker-entrypoint.sh` (add signatures to migration list)
- Modify: `nginx/nginx.conf` (ensure media serving works for signature PDFs)

**Step 1: Update docker-entrypoint.sh**

Add `signatures` to the list of apps that get migrated.

**Step 2: Verify media volume**

The existing `media_files` volume already covers `/app/media/` which includes `signatures/`. No change needed unless the volume mapping is different.

**Step 3: Rebuild and test**

```bash
docker-compose build
docker-compose up -d
docker-compose exec web python manage.py migrate
```

**Step 4: Commit**

```bash
git add docker-entrypoint.sh
git commit -m "feat(signatures): add signatures to deployment config"
```

---

## Summary

| Task | Description | Estimated Complexity |
|------|-------------|---------------------|
| 1 | App skeleton & dependencies | Simple |
| 2 | Data models | Medium |
| 3 | Document list & upload views | Medium |
| 4 | Preparation page (field placement UI) | **Complex** — core feature |
| 5 | Send document & email | Medium |
| 6 | Document detail view | Simple |
| 7 | Client signing experience | **Complex** — core feature |
| 8 | PDF stamping & audit certificate | Medium |
| 9 | Download & verify | Simple |
| 10 | Templates | Medium |
| 11 | Delete, resend, decline, polish | Simple |
| 12 | Docker & deployment | Simple |
