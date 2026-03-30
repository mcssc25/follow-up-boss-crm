import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .email import send_booking_reminder
from .models import Booking

logger = logging.getLogger(__name__)


@shared_task
def send_booking_reminders():
    """Send 24-hour and 1-hour reminder emails for upcoming bookings."""
    now = timezone.now()
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')

    # 24-hour reminders: bookings between 23-25 hours from now
    window_24h_start = now + timedelta(hours=23)
    window_24h_end = now + timedelta(hours=25)
    bookings_24h = Booking.objects.filter(
        status='scheduled',
        reminder_24h_sent=False,
        start_time__gte=window_24h_start,
        start_time__lte=window_24h_end,
    ).select_related('event_type', 'event_type__owner')

    count_24h = 0
    for booking in bookings_24h:
        try:
            send_booking_reminder(booking, base_url, hours_before=24)
            booking.reminder_24h_sent = True
            booking.save(update_fields=['reminder_24h_sent'])
            count_24h += 1
        except Exception:
            logger.exception("Failed to send 24h reminder for booking %s", booking.pk)

    # 1-hour reminders: bookings between 30-90 minutes from now
    window_1h_start = now + timedelta(minutes=30)
    window_1h_end = now + timedelta(minutes=90)
    bookings_1h = Booking.objects.filter(
        status='scheduled',
        reminder_1h_sent=False,
        start_time__gte=window_1h_start,
        start_time__lte=window_1h_end,
    ).select_related('event_type', 'event_type__owner')

    count_1h = 0
    for booking in bookings_1h:
        try:
            send_booking_reminder(booking, base_url, hours_before=1)
            booking.reminder_1h_sent = True
            booking.save(update_fields=['reminder_1h_sent'])
            count_1h += 1
        except Exception:
            logger.exception("Failed to send 1h reminder for booking %s", booking.pk)

    logger.info("Sent %d 24h reminders and %d 1h reminders", count_24h, count_1h)
    return {'24h': count_24h, '1h': count_1h}
