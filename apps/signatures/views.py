import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, DetailView

from apps.contacts.models import Contact
from apps.signatures.models import (
    Document, DocumentSigner, DocumentField, AuditEvent, SignerFieldValue,
    DocumentTemplate, TemplateField,
)
from apps.signatures.forms import DocumentCreateForm
from apps.signatures.email import send_signing_request


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


class DocumentPrepareView(LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'signatures/document_prepare.html'
    context_object_name = 'document'

    def get_queryset(self):
        return Document.objects.filter(team=self.request.user.team, status='draft')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['signers'] = self.object.signers.all()
        ctx['fields'] = self.object.fields.select_related('assigned_to').all()
        ctx['signer_colors'] = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
        return ctx


@login_required
@require_POST
def add_signer(request, pk):
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', '').strip()
    if name and email:
        DocumentSigner.objects.create(document=doc, name=name, email=email, role=role)
        messages.success(request, f'Signer {name} added.')
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
    doc = get_object_or_404(Document, pk=pk, team=request.user.team, status='draft')
    data = json.loads(request.body)
    doc.fields.all().delete()
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

    return render(request, 'signatures/sign.html', {
        'signer': signer,
        'document': doc,
        'fields': fields,
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
    from apps.signatures.email import send_signer_confirmation, send_completion_notification
    send_signer_confirmation(signer)

    # Check if all signers are done
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
    if doc.status not in ('draft', 'declined', 'expired'):
        messages.error(request, 'Cannot delete a document that is in progress.')
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
