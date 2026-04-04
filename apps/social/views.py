import json
import logging
import secrets
import urllib.parse

import requests as http_requests
from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import KeywordTriggerForm
from .meta_api import verify_webhook_signature
from .models import KeywordTrigger, MessageLog, SocialAccount
from .tasks import process_incoming_message

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    """Meta webhook endpoint — handles verification (GET) and messages (POST)."""

    # GET: Meta verification handshake
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.META_WEBHOOK_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponseForbidden('Invalid verify token')

    # POST: Incoming message
    if request.method == 'POST':
        signature = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if not verify_webhook_signature(request.body, signature):
            return HttpResponseForbidden('Invalid signature')

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        obj_type = data.get('object')  # 'instagram' or 'page'
        platform = 'instagram' if obj_type == 'instagram' else 'facebook'

        for entry in data.get('entry', []):
            page_id = entry.get('id', '')
            for messaging_event in entry.get('messaging', []):
                message = messaging_event.get('message', {})
                text = message.get('text', '')
                if not text:
                    continue  # Skip non-text events (reactions, read receipts, etc.)

                sender_id = messaging_event.get('sender', {}).get('id', '')

                # Dispatch to Celery
                process_incoming_message.delay(
                    page_id=page_id,
                    platform=platform,
                    sender_id=sender_id,
                    message_text=text,
                )

        # Always return 200 quickly — Meta retries on non-200
        return HttpResponse('EVENT_RECEIVED', status=200)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ─── Keyword Trigger CRUD ────────────────────────────────────────────


class TriggerListView(LoginRequiredMixin, ListView):
    model = KeywordTrigger
    template_name = 'social/trigger_list.html'
    context_object_name = 'triggers'

    def get_queryset(self):
        return KeywordTrigger.objects.filter(
            team=self.request.user.team,
        ).select_related('campaign')


class TriggerCreateView(LoginRequiredMixin, CreateView):
    model = KeywordTrigger
    form_class = KeywordTriggerForm
    template_name = 'social/trigger_form.html'
    success_url = reverse_lazy('social:trigger_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        django_messages.success(self.request, 'Keyword trigger created.')
        return super().form_valid(form)


class TriggerUpdateView(LoginRequiredMixin, UpdateView):
    model = KeywordTrigger
    form_class = KeywordTriggerForm
    template_name = 'social/trigger_form.html'
    success_url = reverse_lazy('social:trigger_list')

    def get_queryset(self):
        return KeywordTrigger.objects.filter(team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        django_messages.success(self.request, 'Keyword trigger updated.')
        return super().form_valid(form)


class TriggerDeleteView(LoginRequiredMixin, DeleteView):
    model = KeywordTrigger
    success_url = reverse_lazy('social:trigger_list')

    def get_queryset(self):
        return KeywordTrigger.objects.filter(team=self.request.user.team)

    def delete(self, request, *args, **kwargs):
        django_messages.success(request, 'Keyword trigger deleted.')
        return super().delete(request, *args, **kwargs)


# ─── Message Log ─────────────────────────────────────────────────────


class MessageLogView(LoginRequiredMixin, ListView):
    model = MessageLog
    template_name = 'social/message_log.html'
    context_object_name = 'messages'
    paginate_by = 50

    def get_queryset(self):
        qs = MessageLog.objects.filter(
            social_account__team=self.request.user.team,
        ).select_related('trigger_matched', 'contact_created')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(sender_name__icontains=q)
                | Q(message_text__icontains=q)
            )

        platform = self.request.GET.get('platform', '').strip()
        if platform:
            qs = qs.filter(platform=platform)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_platform'] = self.request.GET.get('platform', '')
        return ctx


# ─── Social Accounts Management ─────────────────────────────────────


@login_required
def social_accounts(request):
    """List connected social accounts and provide connect buttons."""
    accounts = SocialAccount.objects.filter(team=request.user.team)
    meta_app_id = settings.META_APP_ID

    # Generate CSRF state token for OAuth
    state = secrets.token_urlsafe(32)
    request.session['meta_oauth_state'] = state

    redirect_uri = request.build_absolute_uri('/social/oauth/callback/')
    oauth_url = (
        f"https://www.facebook.com/v21.0/dialog/oauth"
        f"?client_id={meta_app_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope=pages_messaging,instagram_messaging,pages_manage_metadata,pages_show_list"
        f"&response_type=code"
        f"&state={state}"
    )

    return render(request, 'social/accounts.html', {
        'accounts': accounts,
        'oauth_url': oauth_url,
    })


@login_required
def oauth_callback(request):
    """Handle Meta OAuth callback — exchange code for page access tokens."""
    code = request.GET.get('code')
    if not code:
        django_messages.error(request, 'OAuth failed — no code received.')
        return redirect('social:accounts')

    # Verify CSRF state token
    state = request.GET.get('state', '')
    expected_state = request.session.pop('meta_oauth_state', None)
    if not state or state != expected_state:
        django_messages.error(request, 'OAuth failed — invalid state parameter.')
        return redirect('social:accounts')

    redirect_uri = request.build_absolute_uri('/social/oauth/callback/')
    team = request.user.team

    try:
        # Exchange code for user access token
        token_resp = http_requests.get(
            'https://graph.facebook.com/v21.0/oauth/access_token',
            params={
                'client_id': settings.META_APP_ID,
                'client_secret': settings.META_APP_SECRET,
                'redirect_uri': redirect_uri,
                'code': code,
            },
            timeout=10,
        )
        if token_resp.status_code != 200:
            logger.error("Meta token exchange failed: %s", token_resp.text)
            django_messages.error(request, 'Failed to connect to Meta.')
            return redirect('social:accounts')

        user_token = token_resp.json().get('access_token')

        # Get pages the user manages
        pages_resp = http_requests.get(
            'https://graph.facebook.com/v21.0/me/accounts',
            params={'access_token': user_token},
            timeout=10,
        )
        if pages_resp.status_code != 200:
            django_messages.error(request, 'Failed to retrieve pages.')
            return redirect('social:accounts')

    except http_requests.RequestException:
        logger.exception("Meta OAuth network error")
        django_messages.error(request, 'Could not reach Meta — please try again.')
        return redirect('social:accounts')

    pages = pages_resp.json().get('data', [])
    created_count = 0

    for page in pages:
        page_token = page['access_token']
        page_id = page['id']
        page_name = page['name']

        # Save Facebook page
        SocialAccount.objects.update_or_create(
            team=team,
            page_id=page_id,
            defaults={
                'platform': 'facebook',
                'page_name': page_name,
                'access_token': page_token,
                'is_active': True,
            },
        )
        created_count += 1

        # Check for connected Instagram Business account
        try:
            ig_resp = http_requests.get(
                f'https://graph.facebook.com/v21.0/{page_id}',
                params={
                    'fields': 'instagram_business_account',
                    'access_token': page_token,
                },
                timeout=10,
            )
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json().get('instagram_business_account', {})
                ig_id = ig_data.get('id')
                if ig_id:
                    SocialAccount.objects.update_or_create(
                        team=team,
                        page_id=ig_id,
                        defaults={
                            'platform': 'instagram',
                            'page_name': f"{page_name} (Instagram)",
                            'access_token': page_token,
                            'instagram_account_id': ig_id,
                            'is_active': True,
                        },
                    )
                    created_count += 1
        except http_requests.RequestException:
            logger.exception("Failed to fetch Instagram account for page %s", page_id)

    django_messages.success(request, f'Connected {created_count} account(s) from Meta.')
    return redirect('social:accounts')


@login_required
def disconnect_account(request, pk):
    """Disconnect (deactivate) a social account."""
    if request.method == 'POST':
        account = get_object_or_404(
            SocialAccount, pk=pk, team=request.user.team,
        )
        account.is_active = False
        account.save(update_fields=['is_active'])
        django_messages.success(request, f'Disconnected {account.page_name}.')
    return redirect('social:accounts')
