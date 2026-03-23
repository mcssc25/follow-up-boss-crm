import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, DetailView

from apps.signatures.models import Document, DocumentSigner, DocumentField, AuditEvent, SignerFieldValue
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
    for signer in doc.signers.all():
        send_signing_request(signer)
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
