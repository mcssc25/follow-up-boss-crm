import json
import functools

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TrackedEmail, TrackedRecipient, TrackedLink


def require_api_key(view_func):
    """Decorator that checks for valid API key in Authorization header."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return JsonResponse({'error': 'Missing API key'}, status=401)
        key = auth[7:]
        if key != settings.EMAIL_TRACKER_API_KEY:
            return JsonResponse({'error': 'Invalid API key'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@require_POST
@require_api_key
def register_email(request):
    """Register a new tracked email with recipients and links.

    POST body (JSON):
    {
        "subject": "Hello",
        "gmail_message_id": "msg-abc123",
        "recipients": [
            {"address": "bob@example.com", "tracking_id": "uuid-1"}
        ],
        "links": [
            {"link_hash": "a1b2c3", "original_url": "https://example.com/page"}
        ]
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = TrackedEmail.objects.create(
        subject=data.get('subject', ''),
        gmail_message_id=data.get('gmail_message_id', ''),
    )

    for r in data.get('recipients', []):
        TrackedRecipient.objects.create(
            email=email,
            recipient_address=r['address'],
            tracking_id=r['tracking_id'],
        )

    for link in data.get('links', []):
        TrackedLink.objects.create(
            email=email,
            link_hash=link['link_hash'],
            original_url=link['original_url'],
        )

    return JsonResponse({'id': str(email.id), 'status': 'registered'})


@csrf_exempt
@require_POST
@require_api_key
def get_status(request):
    """Get tracking status for a list of tracked email IDs.

    POST body (JSON):
    {
        "email_ids": ["uuid-1", "uuid-2"]
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email_ids = data.get('email_ids', [])
    if not email_ids:
        return JsonResponse({})

    emails = TrackedEmail.objects.filter(
        id__in=email_ids
    ).prefetch_related(
        'recipients__opens',
        'recipients__clicks__link',
    )

    result = {}
    for email in emails:
        recipients_data = []
        for recipient in email.recipients.all():
            opens = recipient.opens.all()
            clicks = recipient.clicks.all()

            recipients_data.append({
                'address': recipient.recipient_address,
                'opens': opens.count(),
                'first_opened': opens.last().opened_at.isoformat() if opens.exists() else None,
                'last_opened': opens.first().opened_at.isoformat() if opens.exists() else None,
                'clicks': [
                    {
                        'url': click.link.original_url,
                        'clicked_at': click.clicked_at.isoformat(),
                    }
                    for click in clicks
                ],
            })

        result[str(email.id)] = {'recipients': recipients_data}

    return JsonResponse(result)
