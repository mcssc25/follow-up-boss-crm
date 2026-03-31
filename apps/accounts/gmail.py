import base64
from email.mime.application import MIMEApplication
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

    def send_email(self, to, subject, body_html, from_email, reply_to=None, attachments=None):
        """Send an email via Gmail API.

        Args:
            attachments: list of dicts with 'filename' (str) and 'content' (bytes)
        """
        try:
            message = MIMEMultipart('mixed')
            message['to'] = to
            message['from'] = from_email
            message['subject'] = subject
            if reply_to:
                message['Reply-To'] = reply_to

            html_part = MIMEText(body_html, 'html')
            message.attach(html_part)

            for att in (attachments or []):
                part = MIMEApplication(att['content'], Name=att['filename'])
                part['Content-Disposition'] = f'attachment; filename="{att["filename"]}"'
                message.attach(part)

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

    def get_emails_for_contact(self, contact_email, max_results=25):
        """Fetch email threads involving a contact email address."""
        try:
            query = f'from:{contact_email} OR to:{contact_email}'
            results = (
                self.service.users()
                .messages()
                .list(userId='me', q=query, maxResults=max_results)
                .execute()
            )
            messages = results.get('messages', [])
            emails = []
            for msg_ref in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId='me', id=msg_ref['id'], format='metadata',
                         metadataHeaders=['From', 'To', 'Subject', 'Date'])
                    .execute()
                )
                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
                emails.append({
                    'id': msg['id'],
                    'thread_id': msg.get('threadId', ''),
                    'snippet': msg.get('snippet', ''),
                    'from': headers.get('From', ''),
                    'to': headers.get('To', ''),
                    'subject': headers.get('Subject', '(no subject)'),
                    'date': headers.get('Date', ''),
                    'label_ids': msg.get('labelIds', []),
                })
            return {'success': True, 'emails': emails}
        except Exception as e:
            return {'success': False, 'error': str(e), 'emails': []}

    def get_email_body(self, message_id):
        """Fetch the full body of a single email."""
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId='me', id=message_id, format='full')
                .execute()
            )
            payload = msg.get('payload', {})
            body_html = ''
            body_text = ''

            def extract_parts(part):
                nonlocal body_html, body_text
                mime = part.get('mimeType', '')
                if mime == 'text/html' and part.get('body', {}).get('data'):
                    body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                elif mime == 'text/plain' and part.get('body', {}).get('data'):
                    body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                for sub in part.get('parts', []):
                    extract_parts(sub)

            extract_parts(payload)
            return {'success': True, 'html': body_html, 'text': body_text}
        except Exception as e:
            return {'success': False, 'error': str(e)}
