import base64

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_GET

from .models import TrackedRecipient, OpenEvent, TrackedLink, ClickEvent

# 1x1 transparent PNG (43 bytes)
TRANSPARENT_PIXEL = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@require_GET
def tracking_pixel(request, tracking_id):
    """Serve 1x1 transparent PNG and log an open event."""
    try:
        recipient = TrackedRecipient.objects.get(tracking_id=tracking_id)
    except TrackedRecipient.DoesNotExist:
        pass
    else:
        OpenEvent.objects.create(
            recipient=recipient,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    response = HttpResponse(TRANSPARENT_PIXEL, content_type='image/png')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_GET
def click_redirect(request, tracking_id, link_hash):
    """Log a click event and redirect to the original URL."""
    try:
        recipient = TrackedRecipient.objects.select_related('email').get(tracking_id=tracking_id)
        link = TrackedLink.objects.get(email=recipient.email, link_hash=link_hash)
    except (TrackedRecipient.DoesNotExist, TrackedLink.DoesNotExist):
        return HttpResponse('Link not found', status=404)

    ClickEvent.objects.create(
        recipient=recipient,
        link=link,
        ip_address=_get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    return HttpResponseRedirect(link.original_url)
