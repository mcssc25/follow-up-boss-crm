from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView

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
