from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import patch, MagicMock

from apps.accounts.gmail import GmailService
from apps.accounts.models import User


class GmailServiceTest(TestCase):
    @patch('apps.accounts.gmail.build')
    def test_send_email(self, mock_build):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.users().messages().send().execute.return_value = {'id': '123'}

        gmail = GmailService(access_token="fake", refresh_token="fake")
        result = gmail.send_email(
            to="test@example.com",
            subject="Hello",
            body_html="<p>Hi</p>",
            from_email="agent@gmail.com",
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['message_id'], '123')

    @patch('apps.accounts.gmail.build')
    def test_send_email_with_reply_to(self, mock_build):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.users().messages().send().execute.return_value = {'id': '456'}

        gmail = GmailService(access_token="fake", refresh_token="fake")
        result = gmail.send_email(
            to="test@example.com",
            subject="Hello",
            body_html="<p>Hi</p>",
            from_email="agent@gmail.com",
            reply_to="other@example.com",
        )
        self.assertTrue(result['success'])

    @patch('apps.accounts.gmail.build')
    def test_send_email_failure(self, mock_build):
        mock_build.side_effect = Exception("API error")
        gmail = GmailService.__new__(GmailService)
        gmail.credentials = None
        gmail.service = None
        # Since build raises in __init__, we need to test the send path separately
        result = None
        try:
            gmail = GmailService(access_token="fake", refresh_token="fake")
        except Exception:
            pass

        # Test that send_email itself catches exceptions
        mock_build.side_effect = None
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.users().messages().send().execute.side_effect = Exception("Send failed")

        gmail = GmailService(access_token="fake", refresh_token="fake")
        result = gmail.send_email(
            to="test@example.com",
            subject="Hello",
            body_html="<p>Hi</p>",
            from_email="agent@gmail.com",
        )
        self.assertFalse(result['success'])
        self.assertIn('Send failed', result['error'])


class GmailDisconnectTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.user.gmail_connected = True
        self.user.gmail_access_token = 'token'
        self.user.gmail_refresh_token = 'refresh'
        self.user.save()

    def test_disconnect_clears_gmail_fields(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/accounts/gmail/disconnect/')
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.gmail_connected)
        self.assertEqual(self.user.gmail_access_token, '')
        self.assertEqual(self.user.gmail_refresh_token, '')
        self.assertIsNone(self.user.gmail_token_expiry)

    def test_disconnect_get_does_not_clear(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/accounts/gmail/disconnect/')
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.gmail_connected)
