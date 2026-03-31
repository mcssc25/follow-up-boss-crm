from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.gmail import GmailService
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
        user = self.request.user
        qs = Contact.objects.filter(team=user.team).select_related('assigned_to')

        # Agents only see contacts assigned to them or where they collaborate
        if user.role == 'agent':
            qs = qs.filter(
                Q(assigned_to=user) | Q(collaborators=user)
            ).distinct()

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
        user = self.request.user
        qs = Contact.objects.filter(team=user.team).select_related('assigned_to')
        if user.role == 'agent':
            qs = qs.filter(Q(assigned_to=user) | Q(collaborators=user)).distinct()
        return qs

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
# Email History (Gmail API)
# ---------------------------------------------------------------------------


def _get_email_team_members(contact, current_user):
    """Get all team members whose Gmail should be searched for this contact:
    the current user, the assigned agent, and all collaborators."""
    users = {current_user.pk: current_user}
    if contact.assigned_to and contact.assigned_to.gmail_connected:
        users[contact.assigned_to.pk] = contact.assigned_to
    for collab in contact.collaborators.filter(gmail_connected=True):
        users[collab.pk] = collab
    return list(users.values())


@login_required
def contact_emails(request, pk):
    """Fetch merged email history with a contact from all relevant team members' Gmail."""
    contact = get_object_or_404(Contact, pk=pk, team=request.user.team)
    if not contact.email:
        return JsonResponse({'emails': [], 'error': 'Contact has no email address.'})

    team_members = _get_email_team_members(contact, request.user)
    connected = [u for u in team_members if u.gmail_connected]
    if not connected:
        return JsonResponse({'emails': [], 'error': 'No team members have Gmail connected.'})

    all_emails = []
    seen_ids = set()
    errors = []

    for user in connected:
        service = GmailService(user.gmail_access_token, user.gmail_refresh_token)
        result = service.get_emails_for_contact(contact.email)
        if not result.get('success'):
            errors.append(f'{user.get_full_name() or user.username}: {result.get("error", "unknown error")}')
            continue
        for em in result.get('emails', []):
            if em['id'] not in seen_ids:
                seen_ids.add(em['id'])
                em['fetched_by'] = user.get_full_name() or user.username
                em['fetched_by_id'] = user.pk
                all_emails.append(em)

    # Sort by date (Gmail returns newest first per user, re-sort the merged list)
    all_emails.sort(key=lambda e: e.get('date', ''), reverse=True)
    all_emails = all_emails[:50]  # Cap at 50

    resp = {'success': True, 'emails': all_emails}
    if errors:
        resp['warnings'] = errors
    return JsonResponse(resp)


@login_required
def contact_email_detail(request, pk, message_id):
    """Fetch the body of a single email. Try the requesting user first, then other team members."""
    contact = get_object_or_404(Contact, pk=pk, team=request.user.team)

    # Try the user specified in the query param first (the one who fetched it)
    fetched_by_id = request.GET.get('uid')
    team_members = _get_email_team_members(contact, request.user)
    connected = [u for u in team_members if u.gmail_connected]

    # Put the fetched_by user first in the list to try
    if fetched_by_id:
        connected.sort(key=lambda u: (0 if str(u.pk) == fetched_by_id else 1))

    for user in connected:
        service = GmailService(user.gmail_access_token, user.gmail_refresh_token)
        result = service.get_email_body(message_id)
        if result.get('success'):
            return JsonResponse(result)

    return JsonResponse({'error': 'Could not retrieve email from any connected account.'}, status=400)


# ---------------------------------------------------------------------------
# Collaborators
# ---------------------------------------------------------------------------


@login_required
def manage_collaborators(request, pk):
    """Add or remove collaborators on a contact."""
    contact = get_object_or_404(Contact, pk=pk, team=request.user.team)

    if request.method == 'GET':
        collabs = contact.collaborators.values_list('id', 'first_name', 'last_name', 'username')
        team_members = User.objects.filter(team=request.user.team).exclude(
            pk=request.user.pk
        ).values_list('id', 'first_name', 'last_name', 'username')
        return JsonResponse({
            'collaborators': [{'id': c[0], 'name': f'{c[1]} {c[2]}'.strip() or c[3]} for c in collabs],
            'team_members': [{'id': m[0], 'name': f'{m[1]} {m[2]}'.strip() or m[3]} for m in team_members],
        })

    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        action = data.get('action')
        user_id = data.get('user_id')
        target_user = get_object_or_404(User, pk=user_id, team=request.user.team)

        if action == 'add':
            contact.collaborators.add(target_user)
            return JsonResponse({'status': 'ok', 'message': f'{target_user} added as collaborator.'})
        elif action == 'remove':
            contact.collaborators.remove(target_user)
            return JsonResponse({'status': 'ok', 'message': f'{target_user} removed as collaborator.'})

        return JsonResponse({'error': 'Invalid action.'}, status=400)

    return HttpResponseNotAllowed(['GET', 'POST'])


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
