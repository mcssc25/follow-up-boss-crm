"""Meta (Facebook/Instagram) Graph API client."""

import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = 'https://graph.facebook.com/v21.0'


def verify_webhook_signature(request_body, signature_header):
    """Verify X-Hub-Signature-256 from Meta webhook payload.

    Returns True if signature is valid.
    """
    if not signature_header:
        return False

    app_secret = settings.META_APP_SECRET
    expected = 'sha256=' + hmac.new(
        app_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def send_message(page_access_token, recipient_id, text):
    """Send a text message via Meta Send API.

    Works for both Facebook Messenger and Instagram DMs.
    Returns dict with 'success' and optional 'error' keys.
    """
    url = f'{GRAPH_API_BASE}/me/messages'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text},
        'messaging_type': 'RESPONSE',
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            params={'access_token': page_access_token},
            timeout=10,
        )
        if resp.status_code == 200:
            return {'success': True, 'message_id': resp.json().get('message_id')}
        else:
            error = resp.json().get('error', {}).get('message', resp.text)
            logger.error("Meta Send API error: %s", error)
            return {'success': False, 'error': error}
    except requests.RequestException as e:
        logger.exception("Meta Send API request failed")
        return {'success': False, 'error': str(e)}


def get_user_profile(page_access_token, user_id):
    """Fetch basic profile info for a user (name).

    Returns dict with 'name' key or empty dict on failure.
    """
    url = f'{GRAPH_API_BASE}/{user_id}'
    try:
        resp = requests.get(
            url,
            params={
                'fields': 'name',
                'access_token': page_access_token,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
    except requests.RequestException:
        logger.exception("Failed to fetch user profile for %s", user_id)
        return {}
