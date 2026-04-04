import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt

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
