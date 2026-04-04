import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import KeywordTriggerForm
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
        if not _verify_signature(request.body, signature):
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


def _verify_signature(request_body, signature_header):
    """Verify X-Hub-Signature-256 from Meta."""
    if not signature_header:
        return False
    expected = 'sha256=' + hmac.new(
        settings.META_APP_SECRET.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


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
