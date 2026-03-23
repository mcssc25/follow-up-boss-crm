import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, DetailView

from apps.signatures.models import Document, DocumentSigner, DocumentField, AuditEvent
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
