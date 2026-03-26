import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_push_notification(user, title, body, url='/'):
    """Send a push notification to all of a user's subscribed devices."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — skipping push notification")
        return 0

    from .models import PushSubscription

    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', '')
    vapid_claims = {
        'sub': f"mailto:{getattr(settings, 'VAPID_ADMIN_EMAIL', '')}",
    }

    if not vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY not configured — skipping push")
        return 0

    subscriptions = PushSubscription.objects.filter(user=user)
    sent = 0

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url,
    })

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub.subscription_json,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expired or invalid — clean up
                sub.delete()
                logger.info("Removed expired push subscription %s", sub.pk)
            else:
                logger.error("Push failed for subscription %s: %s", sub.pk, e)

    return sent
