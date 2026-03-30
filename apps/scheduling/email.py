from django.conf import settings
from django.template.loader import render_to_string

from apps.accounts.gmail import GmailService

import pytz


def _get_gmail_service(user):
    return GmailService(
        access_token=user.gmail_access_token,
        refresh_token=user.gmail_refresh_token,
    )


def send_booking_confirmation(booking, base_url):
    """Send confirmation email to the prospect."""
    owner = booking.event_type.owner
    if not owner.gmail_connected:
        return

    tz = pytz.timezone(booking.event_type.timezone)
    local_start = booking.start_time.astimezone(tz)

    gcal_url = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text=Call+with+{owner.get_full_name() or owner.email}"
        f"&dates={booking.start_time.strftime('%Y%m%dT%H%M%SZ')}"
        f"/{booking.end_time.strftime('%Y%m%dT%H%M%SZ')}"
        f"&details=Phone+appointment"
    )

    context = {
        'booking': booking,
        'event_type': booking.event_type,
        'owner': owner,
        'local_start': local_start,
        'gcal_url': gcal_url,
        'meet_url': booking.google_meet_url or '',
        'cancel_url': f"{base_url}{booking.get_cancel_url()}",
        'reschedule_url': f"{base_url}{booking.get_reschedule_url()}",
    }
    html = render_to_string('scheduling/emails/booking_confirmation.html', context)
    gmail = _get_gmail_service(owner)
    gmail.send_email(
        to=booking.email,
        subject=f"Confirmed: {booking.event_type.name} on {local_start.strftime('%B %d at %I:%M %p')}",
        body_html=html,
        from_email=owner.email,
    )


def send_owner_notification(booking, base_url):
    """Notify the event owner about a new booking."""
    owner = booking.event_type.owner
    if not owner.gmail_connected:
        return

    tz = pytz.timezone(booking.event_type.timezone)
    local_start = booking.start_time.astimezone(tz)

    context = {
        'booking': booking,
        'event_type': booking.event_type,
        'local_start': local_start,
        'meet_url': booking.google_meet_url or '',
        'contact_url': f"{base_url}{booking.contact.get_absolute_url()}" if booking.contact else '',
    }
    html = render_to_string('scheduling/emails/owner_notification.html', context)
    gmail = _get_gmail_service(owner)
    gmail.send_email(
        to=owner.email,
        subject=f"New booking: {booking.first_name} {booking.last_name} - {local_start.strftime('%B %d at %I:%M %p')}",
        body_html=html,
        from_email=owner.email,
    )


def send_booking_cancellation(booking, base_url):
    """Notify prospect their booking was cancelled."""
    owner = booking.event_type.owner
    if not owner.gmail_connected:
        return

    context = {
        'booking': booking,
        'event_type': booking.event_type,
        'booking_url': f"{base_url}{booking.event_type.get_booking_url()}",
    }
    html = render_to_string('scheduling/emails/booking_cancellation.html', context)
    gmail = _get_gmail_service(owner)
    gmail.send_email(
        to=booking.email,
        subject=f"Cancelled: {booking.event_type.name}",
        body_html=html,
        from_email=owner.email,
    )


def send_booking_reminder(booking, base_url, hours_before):
    """Send reminder email to the prospect before their appointment."""
    owner = booking.event_type.owner
    if not owner.gmail_connected:
        return

    tz = pytz.timezone(booking.event_type.timezone)
    local_start = booking.start_time.astimezone(tz)

    context = {
        'booking': booking,
        'event_type': booking.event_type,
        'owner': owner,
        'local_start': local_start,
        'meet_url': booking.google_meet_url or '',
        'hours_before': hours_before,
        'cancel_url': f"{base_url}{booking.get_cancel_url()}",
        'reschedule_url': f"{base_url}{booking.get_reschedule_url()}",
    }
    html = render_to_string('scheduling/emails/booking_reminder.html', context)

    if hours_before >= 24:
        time_label = "tomorrow"
    else:
        time_label = "in 1 hour"

    gmail = _get_gmail_service(owner)
    gmail.send_email(
        to=booking.email,
        subject=f"Reminder: {booking.event_type.name} {time_label} - {local_start.strftime('%B %d at %I:%M %p')}",
        body_html=html,
        from_email=owner.email,
    )


def send_owner_cancellation(booking, base_url):
    """Notify event owner about a cancellation."""
    owner = booking.event_type.owner
    if not owner.gmail_connected:
        return

    tz = pytz.timezone(booking.event_type.timezone)
    local_start = booking.start_time.astimezone(tz)

    context = {
        'booking': booking,
        'local_start': local_start,
    }
    html = render_to_string('scheduling/emails/owner_cancellation.html', context)
    gmail = _get_gmail_service(owner)
    gmail.send_email(
        to=owner.email,
        subject=f"Cancelled: {booking.first_name} {booking.last_name} - {local_start.strftime('%B %d at %I:%M %p')}",
        body_html=html,
        from_email=owner.email,
    )
