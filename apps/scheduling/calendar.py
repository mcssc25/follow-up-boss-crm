from datetime import datetime

from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleCalendarService:
    """Wrapper around Google Calendar API."""

    def __init__(self, user):
        self.user = user
        self.credentials = Credentials(
            token=user.gmail_access_token,
            refresh_token=user.gmail_refresh_token,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            token_uri='https://oauth2.googleapis.com/token',
        )
        self.service = build('calendar', 'v3', credentials=self.credentials)

    def get_busy_times(self, time_min, time_max, timezone='America/Chicago'):
        """Get busy time ranges from Google Calendar.

        Args:
            time_min: datetime (UTC)
            time_max: datetime (UTC)
            timezone: str timezone name

        Returns:
            List of (start, end) datetime tuples in UTC
        """
        body = {
            'timeMin': time_min.isoformat() + 'Z',
            'timeMax': time_max.isoformat() + 'Z',
            'timeZone': timezone,
            'items': [{'id': 'primary'}],
        }
        try:
            result = self.service.freebusy().query(body=body).execute()
            busy = result.get('calendars', {}).get('primary', {}).get('busy', [])
            return [
                (
                    datetime.fromisoformat(slot['start'].replace('Z', '+00:00')),
                    datetime.fromisoformat(slot['end'].replace('Z', '+00:00')),
                )
                for slot in busy
            ]
        except Exception:
            return []

    def create_event(self, booking):
        """Create a Google Calendar event for a booking.

        Returns the Google event ID or empty string on failure.
        """
        event = {
            'summary': f"Call: {booking.first_name} {booking.last_name}",
            'description': (
                f"Phone: {booking.phone_number}\n"
                f"Email: {booking.email}\n"
                f"Type: {booking.event_type.name}\n"
                f"Notes: {booking.notes or 'None'}"
            ),
            'start': {
                'dateTime': booking.start_time.isoformat(),
                'timeZone': booking.event_type.timezone,
            },
            'end': {
                'dateTime': booking.end_time.isoformat(),
                'timeZone': booking.event_type.timezone,
            },
        }
        try:
            result = self.service.events().insert(
                calendarId='primary', body=event
            ).execute()
            return result.get('id', '')
        except Exception:
            return ''

    def delete_event(self, google_event_id):
        """Delete a Google Calendar event."""
        try:
            self.service.events().delete(
                calendarId='primary', eventId=google_event_id
            ).execute()
            return True
        except Exception:
            return False

    def update_event(self, google_event_id, booking):
        """Update an existing Google Calendar event."""
        event = {
            'summary': f"Call: {booking.first_name} {booking.last_name}",
            'description': (
                f"Phone: {booking.phone_number}\n"
                f"Email: {booking.email}\n"
                f"Type: {booking.event_type.name}\n"
                f"Notes: {booking.notes or 'None'}"
            ),
            'start': {
                'dateTime': booking.start_time.isoformat(),
                'timeZone': booking.event_type.timezone,
            },
            'end': {
                'dateTime': booking.end_time.isoformat(),
                'timeZone': booking.event_type.timezone,
            },
        }
        try:
            self.service.events().update(
                calendarId='primary', eventId=google_event_id, body=event
            ).execute()
            return True
        except Exception:
            return False
