import hashlib
import io
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, DetailView

from PyPDF2 import PdfReader, PdfWriter

from apps.contacts.models import Contact
from apps.signatures.models import (
    Document, DocumentSigner, DocumentField, DocumentFile, AuditEvent, SignerFieldValue,
    DocumentTemplate, TemplateField,
)
from apps.signatures.forms import DocumentCreateForm
from apps.signatures.email import send_signing_request
from apps.signatures.pdf import extract_text_fingerprint, match_template


class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'signatures/document_list.html'
    context_object_name = 'documents'
    paginate_by = 25

    def get_queryset(self):
        qs = Document.objects.filter(
            team=self.request.user.team
        ).select_related('created_by').prefetch_related('signers')

        # Tab filter
        tab = self.request.GET.get('tab', 'all')
        if tab == 'action_needed':
            qs = qs.filter(status__in=['sent', 'viewed'], is_archived=False)
        elif tab == 'draft':
            qs = qs.filter(status='draft', is_archived=False)
        elif tab == 'sent':
            qs = qs.filter(status__in=['sent', 'viewed'], is_archived=False)
        elif tab == 'completed':
            qs = qs.filter(status='completed', is_archived=False)
        elif tab == 'archived':
            qs = qs.filter(is_archived=True)
        else:
            # "all" tab — exclude archived
            qs = qs.filter(is_archived=False)

        # Search
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(signers__name__icontains=q) |
                Q(signers__email__icontains=q)
            ).distinct()

        # Tag filter
        tag = self.request.GET.get('tag', '').strip()
        if tag:
            qs = qs.filter(tags__contains=[tag])

        # Date range
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # Sorting
        sort = self.request.GET.get('sort', '-created_at')
        allowed_sorts = {
            'title', '-title', 'status', '-status',
            'created_at', '-created_at', 'created_by__first_name', '-created_by__first_name',
        }
        if sort in allowed_sorts:
            qs = qs.order_by(sort)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_tab'] = self.request.GET.get('tab', 'all')
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_sort'] = self.request.GET.get('sort', '-created_at')
        ctx['date_from'] = self.request.GET.get('date_from', '')
        ctx['date_to'] = self.request.GET.get('date_to', '')
        ctx['tag_filter'] = self.request.GET.get('tag', '')

        # Tab counts
        base_qs = Document.objects.filter(team=self.request.user.team)
        ctx['count_all'] = base_qs.filter(is_archived=False).count()
        ctx['count_action'] = base_qs.filter(status__in=['sent', 'viewed'], is_archived=False).count()
        ctx['count_draft'] = base_qs.filter(status='draft', is_archived=False).count()
        ctx['count_sent'] = base_qs.filter(status__in=['sent', 'viewed'], is_archived=False).count()
        ctx['count_completed'] = base_qs.filter(status='completed', is_archived=False).count()
        ctx['count_archived'] = base_qs.filter(is_archived=True).count()

        # All unique tags for the filter dropdown
        all_tags = set()
        for doc in base_qs.exclude(tags=[]).values_list('tags', flat=True):
            if doc:
                all_tags.update(doc)
        ctx['all_tags'] = sorted(all_tags)

        return ctx


class DocumentCreateView(LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentCreateForm
    template_name = 'signatures/document_create.html'

    def post(self, request, *args, **kwargs):
        pdf_files = request.FILES.getlist('pdf_files')
        if not pdf_files:
            form = self.get_form()
            form.is_valid()
            form.add_error(None, 'Please upload at least one PDF file.')
            return self.form_invalid(form)
        for f in pdf_files:
            if not f.name.lower().endswith('.pdf'):
                form = self.get_form()
                form.is_valid()
                form.add_error(None, f'"{f.name}" is not a PDF file.')
                return self.form_invalid(form)
            if f.size > 50 * 1024 * 1024:
                form = self.get_form()
                form.is_valid()
                form.add_error(None, f'"{f.name}" exceeds the 50MB limit.')
                return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        form.instance.created_by = self.request.user

        pdf_files = self.request.FILES.getlist('pdf_files')

        if len(pdf_files) == 1:
            # Read page count before Django consumes the temp file on save
            reader = PdfReader(pdf_files[0])
            num_pages = len(reader.pages)
            original_name = pdf_files[0].name
            pdf_files[0].seek(0)
            form.instance.pdf_file = pdf_files[0]
            response = super().form_valid(form)
            # Track as a DocumentFile — point to the same saved file
            doc_file = DocumentFile(
                document=self.object,
                original_filename=original_name,
                page_start=1,
                page_end=num_pages,
                order=0,
            )
            doc_file.pdf_file.name = self.object.pdf_file.name
            doc_file.save()
        else:
            # Multiple files — merge into one combined PDF
            writer = PdfWriter()
            file_info = []  # [(filename, original_file, page_start, page_end)]
            current_page = 1

            for i, uploaded_file in enumerate(pdf_files):
                reader = PdfReader(uploaded_file)
                num_pages = len(reader.pages)
                for page in reader.pages:
                    writer.add_page(page)
                file_info.append({
                    'filename': uploaded_file.name,
                    'file': uploaded_file,
                    'page_start': current_page,
                    'page_end': current_page + num_pages - 1,
                    'order': i,
                })
                current_page += num_pages

            # Save merged PDF
            merged_buffer = io.BytesIO()
            writer.write(merged_buffer)
            merged_buffer.seek(0)
            merged_content = ContentFile(merged_buffer.read(), name=f"{form.cleaned_data['title']}.pdf")

            form.instance.pdf_file = merged_content
            response = super().form_valid(form)

            # Create DocumentFile records for each original
            for info in file_info:
                info['file'].seek(0)
                DocumentFile.objects.create(
                    document=self.object,
                    original_filename=info['filename'],
                    pdf_file=info['file'],
                    page_start=info['page_start'],
                    page_end=info['page_end'],
                    order=info['order'],
                )

        AuditEvent.objects.create(
            document=self.object,
            event_type='created',
            detail=f'Uploaded {len(pdf_files)} file(s).',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )

        # Auto-match against templates
        try:
            matched_template, confidence = match_template(
                self.object.pdf_file, self.request.user.team
            )
            if matched_template:
                self.object.template = matched_template
                self.object.save(update_fields=['template'])
                # Auto-create placeholder signers for each role
                role_signers = {}
                for role in matched_template.signer_roles or []:
                    signer = DocumentSigner.objects.create(
                        document=self.object,
                        name=f'{role} (edit name)',
                        email=f'placeholder@example.com',
                        role=role,
                    )
                    role_signers[role] = signer
                # Copy template fields to document
                for tf in matched_template.fields.all():
                    signer = role_signers.get(tf.signer_role)
                    if signer:
                        DocumentField.objects.create(
                            document=self.object,
                            assigned_to=signer,
                            field_type=tf.field_type,
                            label=tf.label,
                            page=tf.page,
                            x=tf.x, y=tf.y,
                            width=tf.width, height=tf.height,
                            required=tf.required,
                        )
                pct = int(confidence * 100)
                messages.success(
                    self.request,
                    f'Matched template "{matched_template.title}" ({pct}% confidence). '
                    f'Fields auto-placed. Update signer names/emails before sending.'
                )
            else:
                file_word = 'file' if len(pdf_files) == 1 else 'files'
                messages.success(self.request, f'{len(pdf_files)} {file_word} uploaded. Now add signers and place fields.')
        except Exception:
            file_word = 'file' if len(pdf_files) == 1 else 'files'
            messages.success(self.request, f'{len(pdf_files)} {file_word} uploaded. Now add signers and place fields.')

        return response

    def get_success_url(self):
        return reverse_lazy('signatures:prepare', kwargs={'pk': self.object.pk})


class DocumentPrepareView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'signatures/document_prepare.html'
    context_object_name = 'document'

    def get_queryset(self):
        return Document.objects.filter(team=self.request.user.team).exclude(status__in=('completed', 'expired'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['signers'] = self.object.signers.all()
        ctx['fields'] = self.object.fields.select_related('assigned_to').all()
        ctx['signer_colors'] = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
        # Source files for document dividers
        source_files = list(self.object.source_files.all().values(
            'original_filename', 'page_start', 'page_end', 'order'
        ))
        ctx['source_files_json'] = json.dumps(source_files)
        return ctx


@login_required
@require_POST
def add_signer(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    if doc.status in ('completed', 'expired'):
        messages.error(request, 'Cannot modify a completed or expired document.')
        return redirect('signatures:list')
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', '').strip()
    if name and email:
        DocumentSigner.objects.create(document=doc, name=name, email=email, role=role)
        messages.success(request, f'Signer {name} added.')
    return redirect('signatures:prepare', pk=pk)


@login_required
@require_POST
def edit_signer(request, pk, signer_pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    signer = get_object_or_404(DocumentSigner, pk=signer_pk, document=doc)
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', '').strip()
    if name and email:
        signer.name = name
        signer.email = email
        signer.role = role
        signer.save()
        messages.success(request, f'Signer updated to {name} ({email}).')
    return redirect('signatures:prepare', pk=pk)


@login_required
@require_POST
def delete_signer(request, pk, signer_pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    signer = get_object_or_404(DocumentSigner, pk=signer_pk, document=doc)
    signer.delete()
    messages.success(request, 'Signer removed.')
    return redirect('signatures:prepare', pk=pk)


@login_required
@require_POST
def save_fields(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    if doc.status in ('completed', 'expired'):
        return JsonResponse({'error': 'Cannot modify a completed or expired document.'}, status=400)
    data = json.loads(request.body)
    doc.fields.all().delete()
    for f in data.get('fields', []):
        DocumentField.objects.create(
            document=doc,
            assigned_to_id=f['signer_id'],
            field_type=f['type'],
            label=f.get('label', ''),
            prefill_value=f.get('prefill_value', ''),
            read_only=f.get('read_only', False),
            page=f['page'],
            x=f['x'], y=f['y'],
            width=f['width'], height=f['height'],
            required=f.get('required', True),
        )
    return JsonResponse({'status': 'ok', 'count': len(data.get('fields', []))})


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
    placeholder_signers = doc.signers.filter(email='placeholder@example.com')
    if placeholder_signers.exists():
        names = ', '.join(s.name for s in placeholder_signers)
        messages.error(request, f'Update signer details before sending: {names}')
        return redirect('signatures:prepare', pk=pk)
    doc.status = 'sent'
    doc.save()
    email_errors = []
    for signer in doc.signers.all():
        try:
            send_signing_request(signer, sender=request.user)
        except Exception as e:
            email_errors.append(f'{signer.name}: {e}')
    AuditEvent.objects.create(
        document=doc, event_type='sent',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    if doc.contact:
        from apps.contacts.models import ContactActivity
        ContactActivity.objects.create(
            contact=doc.contact, team=doc.team,
            activity_type='document_sent',
            description=f'Document sent for signature: {doc.title}',
        )
    if email_errors:
        messages.warning(request, f'Document marked as sent but email delivery failed for: {"; ".join(email_errors)}. You can resend from the detail page.')
    else:
        messages.success(request, 'Document sent to all signers.')
    return redirect('signatures:detail', pk=pk)


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
        ctx['source_files'] = self.object.source_files.all()
        ctx['signer_colors'] = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
        return ctx


# ---------------------------------------------------------------------------
# Public signing views (no login required)
# ---------------------------------------------------------------------------

def sign_document(request, token):
    """Public signing page — no login required."""
    signer = get_object_or_404(DocumentSigner, access_token=token)
    doc = signer.document

    if doc.is_expired:
        doc.status = 'expired'
        doc.save()
        return render(request, 'signatures/sign_expired.html', {'document': doc})

    if signer.status == 'completed':
        return render(request, 'signatures/sign_completed.html', {'signer': signer, 'document': doc})

    if signer.status == 'declined':
        return render(request, 'signatures/sign_declined.html', {'signer': signer, 'document': doc})

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

    source_files = list(doc.source_files.all().values(
        'original_filename', 'page_start', 'page_end', 'order'
    ))

    return render(request, 'signatures/sign.html', {
        'signer': signer,
        'document': doc,
        'fields': fields,
        'source_files_json': json.dumps(source_files),
    })


@csrf_exempt
@require_POST
def submit_signing(request, token):
    """Process submitted field values from signing page."""
    signer = get_object_or_404(DocumentSigner, access_token=token)
    doc = signer.document

    if signer.status == 'completed' or doc.is_expired:
        return JsonResponse({'error': 'Cannot sign this document.'}, status=400)

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

    # Send confirmation to signer
    from apps.signatures.email import (
        send_signer_confirmation, send_completion_notification, send_completed_copy_to_signers,
    )
    send_signer_confirmation(signer)

    # Check if all signers are done
    if doc.all_signed:
        from apps.signatures.pdf import generate_signed_pdf
        generate_signed_pdf(doc)
        doc.status = 'completed'
        doc.completed_at = timezone.now()
        doc.save()
        send_completion_notification(doc)
        send_completed_copy_to_signers(doc)
        if doc.contact:
            from apps.contacts.models import ContactActivity
            ContactActivity.objects.create(
                contact=doc.contact, team=doc.team,
                activity_type='document_signed',
                description=f'Document fully signed: {doc.title}',
            )

    return JsonResponse({'status': 'ok', 'all_complete': doc.all_signed})


@csrf_exempt
@require_POST
def decline_signing(request, token):
    """Allow signer to decline."""
    signer = get_object_or_404(DocumentSigner, access_token=token)
    doc = signer.document
    reason = ''
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '')
    except (json.JSONDecodeError, ValueError):
        pass
    signer.status = 'declined'
    signer.ip_address = request.META.get('REMOTE_ADDR')
    signer.user_agent = request.META.get('HTTP_USER_AGENT', '')
    signer.save()
    doc.status = 'declined'
    doc.save()
    AuditEvent.objects.create(
        document=doc, signer=signer, event_type='declined',
        detail=reason,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# Download & Verify
# ---------------------------------------------------------------------------

@login_required
def download_signed(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='completed')
    if not doc.signed_pdf:
        messages.error(request, 'Signed PDF not yet available.')
        return redirect('signatures:detail', pk=pk)
    AuditEvent.objects.create(
        document=doc, event_type='downloaded',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    response = FileResponse(doc.signed_pdf.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{doc.title} - Signed.pdf"'
    return response


@login_required
def download_individual_file(request, pk, file_pk):
    """Download a single file from a multi-file document, with signed field values stamped."""
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='completed')
    doc_file = get_object_or_404(DocumentFile, pk=file_pk, document=doc)
    if not doc.signed_pdf:
        messages.error(request, 'Signed PDF not yet available.')
        return redirect('signatures:detail', pk=pk)

    # Extract pages from the signed PDF for this file's range
    reader = PdfReader(doc.signed_pdf)
    writer = PdfWriter()
    for page_num in range(doc_file.page_start - 1, doc_file.page_end):
        if page_num < len(reader.pages):
            writer.add_page(reader.pages[page_num])

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    filename = doc_file.original_filename.replace('.pdf', '') + ' - Signed.pdf'
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TemplateListView(LoginRequiredMixin, ListView):
    model = DocumentTemplate
    template_name = 'signatures/template_list.html'
    context_object_name = 'templates'
    paginate_by = 25

    def get_queryset(self):
        return DocumentTemplate.objects.filter(team=self.request.user.team)


class TemplateCreateView(LoginRequiredMixin, CreateView):
    model = DocumentTemplate
    template_name = 'signatures/template_create.html'
    fields = ['title', 'pdf_file']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['title'].widget.attrs.update({
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'placeholder': 'Template name',
        })
        form.fields['pdf_file'].widget.attrs.update({
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'accept': '.pdf',
        })
        return form

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # Generate text fingerprint for auto-matching
        try:
            fingerprint, page_count = extract_text_fingerprint(self.object.pdf_file)
            self.object.text_fingerprint = fingerprint
            self.object.page_count = page_count
            self.object.save(update_fields=['text_fingerprint', 'page_count'])
        except Exception:
            pass  # Non-critical — template still works without fingerprint
        messages.success(self.request, 'Template created.')
        return response

    def get_success_url(self):
        return reverse_lazy('signatures:template_prepare', kwargs={'pk': self.object.pk})


class TemplatePrepareView(LoginRequiredMixin, DetailView):
    model = DocumentTemplate
    template_name = 'signatures/template_prepare.html'
    context_object_name = 'template'

    def get_queryset(self):
        return DocumentTemplate.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['template_fields'] = self.object.fields.all()
        ctx['signer_roles'] = self.object.signer_roles or []
        return ctx


@login_required
@require_POST
def template_save_roles(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk, team=request.user.team)
    data = json.loads(request.body)
    template.signer_roles = data.get('roles', [])
    template.save()
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def template_save_fields(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk, team=request.user.team)
    data = json.loads(request.body)
    template.fields.all().delete()
    for f in data.get('fields', []):
        TemplateField.objects.create(
            template=template,
            field_type=f['type'],
            label=f.get('label', ''),
            signer_role=f['signer_role'],
            page=f['page'],
            x=f['x'], y=f['y'],
            width=f['width'], height=f['height'],
            required=f.get('required', True),
        )
    return JsonResponse({'status': 'ok', 'count': len(data.get('fields', []))})


@login_required
def use_template(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk, team=request.user.team)
    if request.method == 'POST':
        title = request.POST.get('title', template.title).strip()
        # Create document from template
        doc = Document.objects.create(
            team=request.user.team,
            created_by=request.user,
            template=template,
            title=title,
            pdf_file=template.pdf_file,
        )
        # Create signers from role assignments
        role_signers = {}
        for role in template.signer_roles:
            name = request.POST.get(f'signer_name_{role}', '').strip()
            email = request.POST.get(f'signer_email_{role}', '').strip()
            if name and email:
                signer = DocumentSigner.objects.create(
                    document=doc, name=name, email=email, role=role,
                )
                role_signers[role] = signer

        # Copy template fields with actual signer assignments
        for tf in template.fields.all():
            signer = role_signers.get(tf.signer_role)
            if signer:
                DocumentField.objects.create(
                    document=doc,
                    assigned_to=signer,
                    field_type=tf.field_type,
                    label=tf.label,
                    page=tf.page,
                    x=tf.x, y=tf.y,
                    width=tf.width, height=tf.height,
                    required=tf.required,
                )

        AuditEvent.objects.create(
            document=doc, event_type='created',
            detail=f'Created from template: {template.title}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        messages.success(request, 'Document created from template. Review fields and send.')
        return redirect('signatures:prepare', pk=doc.pk)

    return render(request, 'signatures/template_use.html', {
        'template': template,
    })


@login_required
@require_POST
def delete_template(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk, team=request.user.team)
    template.delete()
    messages.success(request, 'Template deleted.')
    return redirect('signatures:template_list')


# ---------------------------------------------------------------------------
# Delete & Resend
# ---------------------------------------------------------------------------

@login_required
@require_POST
def delete_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    if doc.status == 'completed':
        messages.error(request, 'Cannot delete a completed document.')
        return redirect('signatures:detail', pk=pk)
    doc.delete()
    messages.success(request, 'Document deleted.')
    return redirect('signatures:list')


@login_required
@require_POST
def resend_all_signers(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    pending = doc.signers.exclude(status__in=('completed', 'declined'))
    email_errors = []
    sent_count = 0
    for signer in pending:
        try:
            send_signing_request(signer, sender=request.user)
            sent_count += 1
        except Exception as e:
            email_errors.append(f'{signer.name}: {e}')
    if email_errors:
        messages.warning(request, f'Resent to {sent_count} signer(s), but failed for: {"; ".join(email_errors)}')
    else:
        messages.success(request, f'Signing email resent to {sent_count} signer(s).')
    return redirect('signatures:list')


@login_required
@require_POST
def resend_to_signer(request, pk, signer_pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    signer = get_object_or_404(DocumentSigner, pk=signer_pk, document=doc)
    if signer.status in ('completed', 'declined'):
        messages.error(request, f'{signer.name} has already {signer.get_status_display().lower()}.')
        return redirect('signatures:detail', pk=pk)
    send_signing_request(signer, sender=request.user)
    messages.success(request, f'Signing email resent to {signer.name}.')
    return redirect('signatures:detail', pk=pk)


@login_required
def search_contacts(request):
    """AJAX endpoint to search CRM contacts for signer autocomplete."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)
    contacts = Contact.objects.filter(
        team=request.user.team,
    ).filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(email__icontains=q)
    )[:10]
    results = [
        {
            'name': f'{c.first_name} {c.last_name}'.strip(),
            'email': c.email,
            'phone': c.phone,
        }
        for c in contacts
    ]
    return JsonResponse(results, safe=False)


# ---------------------------------------------------------------------------
# Archive / Bulk Actions / Tags
# ---------------------------------------------------------------------------

@login_required
@require_POST
def archive_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    doc.is_archived = True
    doc.save(update_fields=['is_archived'])
    messages.success(request, f'"{doc.title}" archived.')
    return redirect('signatures:list')


@login_required
@require_POST
def unarchive_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    doc.is_archived = False
    doc.save(update_fields=['is_archived'])
    messages.success(request, f'"{doc.title}" restored.')
    return redirect(request.META.get('HTTP_REFERER', reverse_lazy('signatures:list')))


@login_required
@require_POST
def bulk_action(request):
    action = request.POST.get('action', '')
    doc_ids = request.POST.getlist('doc_ids')
    if not doc_ids:
        messages.warning(request, 'No documents selected.')
        return redirect('signatures:list')

    docs = Document.objects.filter(pk__in=doc_ids, team=request.user.team)

    if action == 'archive':
        count = docs.update(is_archived=True)
        messages.success(request, f'{count} document(s) archived.')
    elif action == 'unarchive':
        count = docs.update(is_archived=False)
        messages.success(request, f'{count} document(s) restored.')
    elif action == 'delete':
        non_deletable = docs.filter(status='completed').count()
        deletable = docs.exclude(status='completed')
        count = deletable.count()
        deletable.delete()
        if count:
            messages.success(request, f'{count} document(s) deleted.')
        if non_deletable:
            messages.warning(request, f'{non_deletable} completed document(s) cannot be deleted.')
    elif action == 'resend':
        count = 0
        for doc in docs.filter(status__in=['sent', 'viewed']):
            for signer in doc.signers.exclude(status='completed'):
                send_signing_request(doc, signer)
                count += 1
        messages.success(request, f'Resent to {count} signer(s).')

    return redirect(request.META.get('HTTP_REFERER', reverse_lazy('signatures:list')))


@login_required
@require_POST
def add_tag(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    tag = request.POST.get('tag', '').strip()
    if tag and tag not in doc.tags:
        doc.tags.append(tag)
        doc.save(update_fields=['tags'])
    return JsonResponse({'tags': doc.tags})


@login_required
@require_POST
def remove_tag(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team)
    tag = request.POST.get('tag', '').strip()
    if tag in doc.tags:
        doc.tags.remove(tag)
        doc.save(update_fields=['tags'])
    return JsonResponse({'tags': doc.tags})
