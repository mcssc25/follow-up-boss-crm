import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GmailService:
    def __init__(self, access_token, refresh_token, client_id=None, client_secret=None):
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id or settings.GOOGLE_CLIENT_ID,
            client_secret=client_secret or settings.GOOGLE_CLIENT_SECRET,
            token_uri='https://oauth2.googleapis.com/token',
        )
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def send_email(self, to, subject, body_html, from_email, reply_to=None):
        try:
            message = MIMEMultipart('alternative')
            message['to'] = to
            message['from'] = from_email
            message['subject'] = subject
            if reply_to:
                message['Reply-To'] = reply_to

            html_part = MIMEText(body_html, 'html')
            message.attach(html_part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            result = (
                self.service.users()
                .messages()
                .send(userId='me', body={'raw': raw})
                .execute()
            )
            return {'success': True, 'message_id': result.get('id')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
