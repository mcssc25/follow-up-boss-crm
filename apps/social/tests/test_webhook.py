import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.accounts.models import Team
from apps.social.models import SocialAccount


@override_settings(
    META_APP_SECRET='test-secret',
    META_WEBHOOK_VERIFY_TOKEN='test-verify-token',
)
class WebhookVerificationTest(TestCase):
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

    @patch('apps.social.views.process_incoming_event.delay')
    def test_valid_instagram_message_dispatches_message_event(self, mock_delay):
        payload = {
            'object': 'instagram',
            'entry': [{
                'id': 'ig_123',
                'messaging': [{
                    'sender': {'id': 'user_456'},
                    'recipient': {'id': 'ig_123'},
                    'message': {'text': 'I want Condos', 'mid': 'mid.123'},
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
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.kwargs['event_type'], 'message')
        self.account.refresh_from_db()
        self.assertTrue(self.account.webhook_verified)

    @patch('apps.social.views.process_incoming_event.delay')
    def test_comment_change_dispatches_comment_event(self, mock_delay):
        payload = {
            'object': 'instagram',
            'entry': [{
                'id': 'ig_123',
                'changes': [{
                    'field': 'feed',
                    'value': {
                        'item': 'comment',
                        'comment_id': 'comment_42',
                        'post_id': 'post_1',
                        'message': 'send guide',
                        'from': {'id': 'user_999', 'name': 'Comment User'},
                    },
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
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.kwargs['event_type'], 'comment')
        self.assertEqual(mock_delay.call_args.kwargs['comment_id'], 'comment_42')

    def test_invalid_signature_rejected(self):
        payload = json.dumps({'object': 'instagram', 'entry': []}).encode()
        response = self.client.post(
            '/social/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid',
        )
        self.assertEqual(response.status_code, 403)
