import hashlib
import hmac
import json

from django.test import TestCase, override_settings

from apps.accounts.models import Team
from apps.social.models import SocialAccount


@override_settings(
    META_APP_SECRET='test-secret',
    META_WEBHOOK_VERIFY_TOKEN='test-verify-token',
)
class WebhookVerificationTest(TestCase):
    """Test the GET webhook endpoint (Meta verification handshake)."""

    def test_verify_valid_token(self):
        response = self.client.get('/social/webhook/', {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'test-verify-token',
            'hub.challenge': '1234567890',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'1234567890')

    def test_verify_invalid_token(self):
        response = self.client.get('/social/webhook/', {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong-token',
            'hub.challenge': '1234567890',
        })
        self.assertEqual(response.status_code, 403)


@override_settings(META_APP_SECRET='test-secret')
class WebhookMessageTest(TestCase):
    """Test the POST webhook endpoint (incoming messages)."""

    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='page_123',
            page_name='Test Page',
            access_token='token',
            instagram_account_id='ig_123',
        )

    def _sign(self, body_bytes):
        sig = hmac.new(
            b'test-secret', body_bytes, hashlib.sha256
        ).hexdigest()
        return f'sha256={sig}'

    def test_valid_instagram_message(self):
        payload = {
            'object': 'instagram',
            'entry': [{
                'id': 'ig_123',
                'messaging': [{
                    'sender': {'id': 'user_456'},
                    'recipient': {'id': 'ig_123'},
                    'message': {'text': 'I want Condos'},
                }],
            }],
        }
        body = json.dumps(payload).encode()
        response = self.client.post(
            '/social/webhook/',
            body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(response.status_code, 200)

    def test_valid_facebook_message(self):
        payload = {
            'object': 'page',
            'entry': [{
                'id': 'page_123',
                'messaging': [{
                    'sender': {'id': 'user_789'},
                    'recipient': {'id': 'page_123'},
                    'message': {'text': 'Hello there'},
                }],
            }],
        }
        body = json.dumps(payload).encode()
        response = self.client.post(
            '/social/webhook/',
            body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_signature_rejected(self):
        payload = json.dumps({'object': 'instagram', 'entry': []}).encode()
        response = self.client.post(
            '/social/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid',
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_signature_rejected(self):
        payload = json.dumps({'object': 'instagram', 'entry': []}).encode()
        response = self.client.post(
            '/social/webhook/',
            payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
