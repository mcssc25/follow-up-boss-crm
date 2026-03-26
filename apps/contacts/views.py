from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.models import User
from apps.contacts.forms import ContactForm, ContactNoteForm, LogActivityForm, SmartListForm
from apps.contacts.models import Contact, ContactActivity, ContactNote, SmartList
from apps.pwa.push import send_push_notification


class ContactListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'contacts/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 25

    def get_queryset(self):
        qs = Contact.objects.filter(team=self.request.user.team).select_related('assigned_to')

        # Search
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            )

        # Filter by source
        source = self.request.GET.get('source', '').strip()
        if source:
            qs = qs.filter(source=source)

        # Filter by assigned agent
        agent = self.request.GET.get('agent', '').strip()
        if agent:
            qs = qs.filter(assigned_to_id=agent)

        # Filter by tag
        tag = self.request.GET.get('tag', '').strip()
        if tag:
            qs = qs.filter(tags__contains=tag)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_source'] = self.request.GET.get('source', '')
        ctx['selected_agent'] = self.request.GET.get('agent', '')
        ctx['selected_tag'] = self.request.GET.get('tag', '')
        ctx['source_choices'] = Contact.SOURCE_CHOICES
        ctx['agents'] = User.objects.filter(team=self.request.user.team)
        return ctx


class ContactDetailView(LoginRequiredMixin, DetailView):
    model = Contact
    template_name = 'contacts/contact_detail.html'
    context_object_name = 'contact'

    def get_queryset(self):
        return Contact.objects.filter(team=self.request.user.team).select_related('assigned_to')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contact = self.object
        ctx['activities'] = contact.activities.all()[:50]
        ctx['notes'] = contact.notes.select_related('author').all()[:20]
        ctx['note_form'] = ContactNoteForm()
        ctx['activity_form'] = LogActivityForm()

        # Documents: find signature documents where a signer's email matches this contact
        if contact.email:
            from apps.signatures.models import Document
            ctx['documents'] = Document.objects.filter(
                team=self.request.user.team,
                signers__email__iexact=contact.email,
            ).distinct().select_related('created_by').order_by('-created_at')
        else:
            ctx['documents'] = []

        return ctx


class ContactCreateView(LoginRequiredMixin, CreateView):
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        response = super().form_valid(form)
        contact = self.object
        send_push_notification(
            user=self.request.user,
            title='New Contact Added',
            body=f'{contact.first_name} {contact.last_name} has been added',
            url=f'/contacts/{contact.pk}/',
        )
        messages.success(self.request, 'Contact created successfully.')
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Add Contact'
        return ctx


class ContactUpdateView(LoginRequiredMixin, UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_form.html'

    def get_queryset(self):
        return Contact.objects.filter(team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Contact updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Edit Contact'
        return ctx


@login_required
def add_note(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    contact = get_object_or_404(Contact, pk=pk, team=request.user.team)
    form = ContactNoteForm(request.POST)
    if form.is_valid():
        ContactNote.objects.create(
            contact=contact,
            author=request.user,
            content=form.cleaned_data['content'],
        )
        ContactActivity.objects.create(
            contact=contact,
            activity_type='note_added',
            description=form.cleaned_data['content'][:200],
        )
        messages.success(request, 'Note added.')
    else:
        messages.error(request, 'Could not add note. Please provide content.')

    return redirect('contacts:detail', pk=contact.pk)


@login_required
def log_activity(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    contact = get_object_or_404(Contact, pk=pk, team=request.user.team)
    form = LogActivityForm(request.POST)
    if form.is_valid():
        ContactActivity.objects.create(
            contact=contact,
            activity_type=form.cleaned_data['activity_type'],
            description=form.cleaned_data.get('description', ''),
        )
        messages.success(request, 'Activity logged.')
    else:
        messages.error(request, 'Could not log activity.')

    return redirect('contacts:detail', pk=contact.pk)


@login_required
def bulk_action(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    action = request.POST.get('action', '')
    contact_ids = request.POST.getlist('contact_ids')

    if not contact_ids:
        messages.warning(request, 'No contacts selected.')
        return redirect('contacts:list')

    contacts = Contact.objects.filter(pk__in=contact_ids, team=request.user.team)

    if action == 'delete':
        count = contacts.count()
        contacts.delete()
        messages.success(request, f'{count} contact(s) deleted.')

    elif action == 'assign':
        agent_id = request.POST.get('assign_to')
        if agent_id:
            agent = get_object_or_404(User, pk=agent_id, team=request.user.team)
            contacts.update(assigned_to=agent)
            messages.success(request, f'Contacts assigned to {agent}.')
        else:
            messages.error(request, 'No agent selected for assignment.')

    elif action == 'tag':
        tag = request.POST.get('tag', '').strip()
        if tag:
            for contact in contacts:
                if tag not in contact.tags:
                    contact.tags.append(tag)
                    contact.save(update_fields=['tags'])
            messages.success(request, f'Tag "{tag}" added to selected contacts.')
        else:
            messages.error(request, 'No tag provided.')

    else:
        messages.error(request, 'Unknown action.')

    return redirect('contacts:list')


# ---------------------------------------------------------------------------
# Smart List Views
# ---------------------------------------------------------------------------


class SmartListListView(LoginRequiredMixin, ListView):
    model = SmartList
    template_name = 'contacts/smart_list_list.html'
    context_object_name = 'smart_lists'

    def get_queryset(self):
        return SmartList.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for sl in ctx['smart_lists']:
            sl.contact_count = sl.get_contacts().count()
        return ctx


class SmartListCreateView(LoginRequiredMixin, CreateView):
    model = SmartList
    form_class = SmartListForm
    template_name = 'contacts/smart_list_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        form.instance.filters = form.build_filters()
        messages.success(self.request, 'Smart list created.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Create Smart List'
        return ctx


class SmartListDetailView(LoginRequiredMixin, DetailView):
    model = SmartList
    template_name = 'contacts/smart_list_results.html'
    context_object_name = 'smart_list'

    def get_queryset(self):
        return SmartList.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['contacts'] = self.object.get_contacts().select_related('assigned_to')
        return ctx


class SmartListUpdateView(LoginRequiredMixin, UpdateView):
    model = SmartList
    form_class = SmartListForm
    template_name = 'contacts/smart_list_form.html'

    def get_queryset(self):
        return SmartList.objects.filter(team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.filters = form.build_filters()
        messages.success(self.request, 'Smart list updated.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Edit Smart List'
        return ctx


class SmartListDeleteView(LoginRequiredMixin, DeleteView):
    model = SmartList
    success_url = reverse_lazy('contacts:smart_list_list')

    def get_queryset(self):
        return SmartList.objects.filter(team=self.request.user.team)

    def post(self, request, *args, **kwargs):
        messages.success(request, 'Smart list deleted.')
        return super().post(request, *args, **kwargs)
