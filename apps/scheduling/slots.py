from datetime import datetime, timedelta, time as dt_time

from django.utils import timezone
import pytz


def generate_available_slots(event_type, date, busy_times=None):
    """Generate available time slots for a given date.

    Args:
        event_type: EventType instance
        date: datetime.date to generate slots for
        busy_times: list of (start, end) datetime tuples from Google Calendar (UTC)

    Returns:
        List of datetime objects (start times) in the event type's timezone
    """
    tz = pytz.timezone(event_type.timezone)
    now = timezone.now().astimezone(tz)
    min_advance = timedelta(hours=event_type.min_advance_hours)

    # Get availability for this day of week (Monday=0)
    day_of_week = date.weekday()
    availability = event_type.availabilities.filter(day_of_week=day_of_week).first()
    if not availability:
        return []

    # Build candidate slots from availability window
    duration = timedelta(minutes=event_type.duration_minutes)
    buffer = timedelta(minutes=event_type.buffer_minutes)
    slot_start = tz.localize(datetime.combine(date, availability.start_time))
    window_end = tz.localize(datetime.combine(date, availability.end_time))

    candidates = []
    while slot_start + duration <= window_end:
        candidates.append(slot_start)
        slot_start += duration + buffer

    # Get existing bookings for this date
    day_start_utc = tz.localize(datetime.combine(date, dt_time.min)).astimezone(pytz.UTC)
    day_end_utc = tz.localize(datetime.combine(date, dt_time.max)).astimezone(pytz.UTC)
    existing_bookings = event_type.bookings.filter(
        start_time__gte=day_start_utc,
        start_time__lte=day_end_utc,
        status='scheduled',
    )

    # Build blocked ranges (bookings + buffer on each side)
    blocked = []
    for b in existing_bookings:
        b_start = b.start_time.astimezone(tz) - buffer
        b_end = b.end_time.astimezone(tz) + buffer
        blocked.append((b_start, b_end))

    # Add Google Calendar busy times
    if busy_times:
        for start, end in busy_times:
            blocked.append((start.astimezone(tz) - buffer, end.astimezone(tz) + buffer))

    # Filter candidates
    available = []
    for slot in candidates:
        slot_end = slot + duration

        # Must be far enough in the future
        if slot < now + min_advance:
            continue

        # Must not overlap with any blocked range
        is_blocked = False
        for b_start, b_end in blocked:
            if slot < b_end and slot_end > b_start:
                is_blocked = True
                break

        if not is_blocked:
            available.append(slot)

    return available
