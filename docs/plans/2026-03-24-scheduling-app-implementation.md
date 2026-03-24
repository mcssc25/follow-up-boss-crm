# Scheduling App (Calendly Clone) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Calendly-like scheduling app that lets prospects book phone calls from public booking pages, integrated with Google Calendar and the CRM.

**Architecture:** New Django app `apps/scheduling/` following the same patterns as `apps/signatures/`. Public booking pages at `/schedule/<slug>/`, CRM admin at `/scheduling/`. Google Calendar integration via the existing OAuth credentials on the User model, extended with Calendar scope.

**Tech Stack:** Django 5.1, PostgreSQL, Celery/Redis, Google Calendar API, HTMX, Tailwind CSS (CDN for public pages), django-widget-tweaks.

---

### Task 1: Create the Django App Skeleton

**Files:**
- Create: `apps/scheduling/__init__.py`
- Create: `apps/scheduling/apps.py`
- Create: `apps/scheduling/models.py`
- Create: `apps/scheduling/views.py`
- Create: `apps/scheduling/urls.py`
- Create: `apps/scheduling/forms.py`
- Create: `apps/scheduling/admin.py`
- Create: `apps/scheduling/calendar.py`
- Create: `apps/scheduling/email.py`
- Create: `apps/scheduling/tasks.py`
- Modify: `config/settings.py` (add to INSTALLED_APPS)
- Modify: `config/urls.py` (add URL includes)

**Step 1: Create the app directory and files**

```python
# apps/scheduling/__init__.py
# (empty)
```

```python
# apps/scheduling/apps.py
from django.apps import AppConfig

class SchedulingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scheduling'
    verbose_name = 'Scheduling'
```

```python
# apps/scheduling/models.py
# (placeholder — filled in Task 2)
from django.db import models
```

```python
# apps/scheduling/views.py
# (placeholder — filled in later tasks)
```

```python
# apps/scheduling/urls.py
from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = []
```

```python
# apps/scheduling/forms.py
from django import forms
```

```python
# apps/scheduling/admin.py
from django.contrib import admin
```

```python
# apps/scheduling/calendar.py
# Google Calendar integration (filled in Task 4)
```

```python
# apps/scheduling/email.py
# Email notifications (filled in Task 7)
```

```python
# apps/scheduling/tasks.py
# Celery tasks (filled in Task 8)
```

**Step 2: Register in settings**

In `config/settings.py`, add `'apps.scheduling'` to `INSTALLED_APPS` after `'apps.signatures'`.

**Step 3: Add URL includes**

In `config/urls.py`, add two entries:

```python
path('schedule/', include('apps.scheduling.urls')),      # public booking pages
path('scheduling/', include('apps.scheduling.urls')),     # CRM admin (uses same urlconf, different prefixes handled by named routes)
```

Actually — use a single include since we'll namespace both public and admin routes under the same app:

```python
path('', include('apps.scheduling.urls')),
```

The `apps/scheduling/urls.py` will define both `/schedule/<slug>/` (public) and `/scheduling/` (admin) prefixes explicitly.

**Step 4: Commit**

```bash
git add apps/scheduling/ config/settings.py config/urls.py
git commit -m "feat(scheduling): add Django app skeleton"
```

---

### Task 2: Create Data Models

**Files:**
- Create: `apps/scheduling/models.py`
- Modify: `apps/contacts/models.py` (add `call_scheduled` to ACTIVITY_TYPES)

**Step 1: Write the models**

```python
# apps/scheduling/models.py
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class EventType(models.Model):
    """A bookable event type with its own public URL and settings."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_types',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='event_types',
    )
    tags = models.ManyToManyField(
        'contacts.Tag',
        blank=True,
        related_name='event_types',
    )
    color = models.CharField(max_length=7, default='#6366f1')
    is_active = models.BooleanField(default=True)
    min_advance_hours = models.PositiveIntegerField(
        default=24,
        help_text='Minimum hours in advance a booking can be made',
    )
    buffer_minutes = models.PositiveIntegerField(
        default=10,
        help_text='Buffer time between appointments',
    )
    timezone = models.CharField(
        max_length=50,
        default='America/Chicago',
        help_text='Timezone for availability display',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('scheduling:public_booking', kwargs={'slug': self.slug})

    def get_booking_url(self):
        """Full public URL for sharing."""
        return f"/schedule/{self.slug}/"


class Availability(models.Model):
    """Weekly recurring availability for an event type."""
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name='availabilities',
    )
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name_plural = 'availabilities'
        unique_together = ['event_type', 'day_of_week']

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class Booking(models.Model):
    """A scheduled appointment."""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
    ]

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    cancel_token = models.UUIDField(default=uuid.uuid4, unique=True)
    google_event_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.start_time}"

    def get_cancel_url(self):
        return reverse('scheduling:cancel_booking', kwargs={'token': self.cancel_token})

    def get_reschedule_url(self):
        return reverse('scheduling:reschedule_booking', kwargs={'token': self.cancel_token})
```

**Step 2: Add activity type to contacts**

In `apps/contacts/models.py`, add `('call_scheduled', 'Call Scheduled')` to `ContactActivity.ACTIVITY_TYPES` list, after `('call_logged', 'Call Logged')`.

**Step 3: Create and run migrations**

```bash
python manage.py makemigrations scheduling
python manage.py makemigrations contacts
python manage.py migrate
```

**Step 4: Commit**

```bash
git add apps/scheduling/models.py apps/contacts/models.py apps/scheduling/migrations/ apps/contacts/migrations/
git commit -m "feat(scheduling): add EventType, Availability, and Booking models"
```

---

### Task 3: Admin Registration

**Files:**
- Modify: `apps/scheduling/admin.py`

**Step 1: Register models with Django admin**

```python
# apps/scheduling/admin.py
from django.contrib import admin
from .models import EventType, Availability, Booking


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 0


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'duration_minutes', 'owner', 'is_active']
    list_filter = ['is_active', 'owner']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [AvailabilityInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'event_type', 'status', 'start_time', 'phone_number']
    list_filter = ['status', 'event_type']
    readonly_fields = ['cancel_token', 'google_event_id']
```

**Step 2: Commit**

```bash
git add apps/scheduling/admin.py
git commit -m "feat(scheduling): register models in Django admin"
```

---

### Task 4: Google Calendar Integration

**Files:**
- Create: `apps/scheduling/calendar.py`
- Modify: `apps/accounts/views_gmail.py` (add Calendar scope)

**Step 1: Extend OAuth scope**

In `apps/accounts/views_gmail.py`, change the SCOPES list:

```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
]
```

> **Note:** Existing users will need to re-authorize (disconnect/reconnect Gmail) to grant the Calendar scope. The Gmail tokens still work for sending — Calendar calls will fail gracefully until re-authorized.

**Step 2: Write the Calendar service**

```python
# apps/scheduling/calendar.py
from datetime import datetime, timedelta

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
            # If Calendar API fails (scope not granted), return empty
            # so booking page still works with just local availability
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
```

**Step 3: Commit**

```bash
git add apps/scheduling/calendar.py apps/accounts/views_gmail.py
git commit -m "feat(scheduling): add Google Calendar integration service"
```

---

### Task 5: Availability Slot Generation Logic

**Files:**
- Create: `apps/scheduling/slots.py`

This is the core logic that combines availability windows, existing bookings, Google Calendar busy times, buffer, and min advance to produce available time slots.

**Step 1: Write slot generation**

```python
# apps/scheduling/slots.py
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
```

**Step 2: Commit**

```bash
git add apps/scheduling/slots.py
git commit -m "feat(scheduling): add available slot generation logic"
```

---

### Task 6: Public Booking Views

**Files:**
- Modify: `apps/scheduling/views.py`
- Modify: `apps/scheduling/urls.py`
- Modify: `apps/scheduling/forms.py`
- Create: `templates/scheduling/public/booking.html`
- Create: `templates/scheduling/public/confirmation.html`
- Create: `templates/scheduling/public/cancel.html`
- Create: `templates/scheduling/public/cancelled.html`

**Step 1: Write the booking form**

```python
# apps/scheduling/forms.py
from django import forms


class BookingForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
```

**Step 2: Write the public views**

```python
# apps/scheduling/views.py
from datetime import datetime, timedelta, date as dt_date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

import pytz

from apps.contacts.models import Contact, ContactActivity, Tag
from .calendar import GoogleCalendarService
from .email import send_booking_confirmation, send_booking_cancellation, send_owner_notification, send_owner_cancellation
from .forms import BookingForm
from .models import EventType, Availability, Booking
from .slots import generate_available_slots


# ── Public Booking Views ──────────────────────────────────────────

def public_booking(request, slug):
    """Public booking page for an event type."""
    event_type = get_object_or_404(EventType, slug=slug, is_active=True)
    form = BookingForm()
    return render(request, 'scheduling/public/booking.html', {
        'event_type': event_type,
        'form': form,
    })


def get_available_slots(request, slug):
    """AJAX endpoint: return available slots for a given date."""
    event_type = get_object_or_404(EventType, slug=slug, is_active=True)
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'slots': []})

    try:
        date = dt_date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'slots': []})

    # Get Google Calendar busy times if connected
    busy_times = []
    owner = event_type.owner
    if owner.gmail_connected:
        try:
            cal = GoogleCalendarService(owner)
            tz = pytz.timezone(event_type.timezone)
            day_start = tz.localize(datetime.combine(date, datetime.min.time()))
            day_end = tz.localize(datetime.combine(date, datetime.max.time()))
            busy_times = cal.get_busy_times(
                day_start.astimezone(pytz.UTC).replace(tzinfo=None),
                day_end.astimezone(pytz.UTC).replace(tzinfo=None),
                timezone=event_type.timezone,
            )
        except Exception:
            pass  # Graceful fallback

    slots = generate_available_slots(event_type, date, busy_times)

    return JsonResponse({
        'slots': [
            {
                'time': slot.strftime('%I:%M %p'),
                'value': slot.isoformat(),
            }
            for slot in slots
        ]
    })


def confirm_booking(request, slug):
    """Handle booking form submission."""
    event_type = get_object_or_404(EventType, slug=slug, is_active=True)

    if request.method != 'POST':
        return redirect('scheduling:public_booking', slug=slug)

    form = BookingForm(request.POST)
    slot_value = request.POST.get('selected_slot')

    if not form.is_valid() or not slot_value:
        return render(request, 'scheduling/public/booking.html', {
            'event_type': event_type,
            'form': form,
            'error': 'Please select a time slot and fill in all required fields.',
        })

    try:
        start_time = datetime.fromisoformat(slot_value)
    except ValueError:
        return redirect('scheduling:public_booking', slug=slug)

    end_time = start_time + timedelta(minutes=event_type.duration_minutes)

    # Create the booking
    booking = Booking.objects.create(
        event_type=event_type,
        first_name=form.cleaned_data['first_name'],
        last_name=form.cleaned_data['last_name'],
        email=form.cleaned_data['email'],
        phone_number=form.cleaned_data['phone_number'],
        notes=form.cleaned_data.get('notes', ''),
        start_time=start_time,
        end_time=end_time,
    )

    # Create or link CRM contact
    contact, created = Contact.objects.get_or_create(
        email__iexact=booking.email,
        team=event_type.team,
        defaults={
            'first_name': booking.first_name,
            'last_name': booking.last_name,
            'email': booking.email,
            'phone': booking.phone_number,
            'source': 'landing_page',
            'source_detail': f'Scheduling: {event_type.name}',
            'team': event_type.team,
        },
    )
    if not created:
        # Update phone if empty
        if not contact.phone and booking.phone_number:
            contact.phone = booking.phone_number
            contact.save()

    booking.contact = contact
    booking.save()

    # Apply tags from event type
    for tag in event_type.tags.all():
        contact.tag_objects.add(tag)

    # Log activity
    tz = pytz.timezone(event_type.timezone)
    local_time = booking.start_time.astimezone(tz)
    ContactActivity.objects.create(
        contact=contact,
        activity_type='call_scheduled',
        description=(
            f"Scheduled {event_type.duration_minutes}-min {event_type.name} "
            f"for {local_time.strftime('%B %d at %I:%M %p')}"
        ),
    )

    # Create Google Calendar event
    owner = event_type.owner
    if owner.gmail_connected:
        try:
            cal = GoogleCalendarService(owner)
            google_event_id = cal.create_event(booking)
            if google_event_id:
                booking.google_event_id = google_event_id
                booking.save()
        except Exception:
            pass

    # Send confirmation emails
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    send_booking_confirmation(booking, base_url)
    send_owner_notification(booking, base_url)

    return render(request, 'scheduling/public/confirmation.html', {
        'booking': booking,
        'event_type': event_type,
    })


def cancel_booking(request, token):
    """Cancel a booking via token link."""
    booking = get_object_or_404(Booking, cancel_token=token, status='scheduled')

    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()

        # Delete Google Calendar event
        if booking.google_event_id and booking.event_type.owner.gmail_connected:
            try:
                cal = GoogleCalendarService(booking.event_type.owner)
                cal.delete_event(booking.google_event_id)
            except Exception:
                pass

        # Send cancellation emails
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        send_booking_cancellation(booking, base_url)
        send_owner_cancellation(booking, base_url)

        return render(request, 'scheduling/public/cancelled.html', {
            'booking': booking,
        })

    return render(request, 'scheduling/public/cancel.html', {
        'booking': booking,
    })


def reschedule_booking(request, token):
    """Reschedule a booking — shows booking page with info pre-filled."""
    booking = get_object_or_404(Booking, cancel_token=token, status='scheduled')
    event_type = booking.event_type

    form = BookingForm(initial={
        'first_name': booking.first_name,
        'last_name': booking.last_name,
        'email': booking.email,
        'phone_number': booking.phone_number,
    })

    return render(request, 'scheduling/public/booking.html', {
        'event_type': event_type,
        'form': form,
        'reschedule_token': token,
    })


def confirm_reschedule(request, slug, token):
    """Handle reschedule form submission — cancel old, create new."""
    old_booking = get_object_or_404(Booking, cancel_token=token, status='scheduled')

    # Cancel the old booking first
    old_booking.status = 'cancelled'
    old_booking.save()

    if old_booking.google_event_id and old_booking.event_type.owner.gmail_connected:
        try:
            cal = GoogleCalendarService(old_booking.event_type.owner)
            cal.delete_event(old_booking.google_event_id)
        except Exception:
            pass

    # The confirm_booking view handles the rest — redirect POST data there
    # Actually, we handle it inline to avoid redirect issues with POST
    return confirm_booking(request, slug)
```

**Step 3: Write the URL patterns**

```python
# apps/scheduling/urls.py
from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = [
    # Public booking pages
    path('schedule/<slug:slug>/', views.public_booking, name='public_booking'),
    path('schedule/<slug:slug>/slots/', views.get_available_slots, name='get_slots'),
    path('schedule/<slug:slug>/book/', views.confirm_booking, name='confirm_booking'),
    path('schedule/<slug:slug>/book/<uuid:token>/', views.confirm_reschedule, name='confirm_reschedule'),

    # Cancel / reschedule (token-based, no login)
    path('booking/cancel/<uuid:token>/', views.cancel_booking, name='cancel_booking'),
    path('booking/reschedule/<uuid:token>/', views.reschedule_booking, name='reschedule_booking'),

    # CRM admin views (added in Task 9)
]
```

**Step 4: Write the public booking template**

Create `templates/scheduling/public/booking.html` — standalone page (no base.html), Tailwind CDN, mobile-responsive. Shows:
- Event type name, description, duration
- Calendar date picker (vanilla JS, no external lib)
- Time slots loaded via HTMX/fetch from `/schedule/<slug>/slots/?date=YYYY-MM-DD`
- Booking form (hidden until slot selected)
- Hidden `selected_slot` field
- If `reschedule_token` is set, form action posts to `/schedule/<slug>/book/<token>/`

**Step 5: Write the confirmation template**

Create `templates/scheduling/public/confirmation.html` — standalone page showing:
- "You're booked!" message
- Appointment details (date, time, duration, event type)
- "Add to Google Calendar" link (Google Calendar URL scheme)
- "Need to make changes?" with cancel/reschedule links

**Step 6: Write the cancel/cancelled templates**

Create `templates/scheduling/public/cancel.html`:
- "Are you sure?" confirmation with booking details
- Cancel button (POST form)

Create `templates/scheduling/public/cancelled.html`:
- "Your appointment has been cancelled" confirmation
- "Want to rebook?" link back to the booking page

**Step 7: Commit**

```bash
git add apps/scheduling/views.py apps/scheduling/urls.py apps/scheduling/forms.py templates/scheduling/
git commit -m "feat(scheduling): add public booking views and templates"
```

---

### Task 7: Email Notifications

**Files:**
- Modify: `apps/scheduling/email.py`
- Create: `templates/scheduling/emails/booking_confirmation.html`
- Create: `templates/scheduling/emails/owner_notification.html`
- Create: `templates/scheduling/emails/booking_cancellation.html`
- Create: `templates/scheduling/emails/owner_cancellation.html`

**Step 1: Write email functions**

Follow the exact pattern from `apps/signatures/email.py`:

```python
# apps/scheduling/email.py
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

    # Google Calendar add-event URL
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
```

**Step 2: Write email templates**

Create 4 email templates in `templates/scheduling/emails/`:

- `booking_confirmation.html` — styled HTML email to prospect: appointment details, "Add to Google Calendar" button, cancel/reschedule links
- `owner_notification.html` — email to Kelly: prospect name, phone number, time, event type, link to CRM contact
- `booking_cancellation.html` — email to prospect: "Your appointment has been cancelled", rebook link
- `owner_cancellation.html` — email to Kelly: "Appointment cancelled" with details

Use simple, clean inline CSS (email-safe). Follow the style of existing templates in `templates/signatures/emails/`.

**Step 3: Commit**

```bash
git add apps/scheduling/email.py templates/scheduling/emails/
git commit -m "feat(scheduling): add email notifications for bookings"
```

---

### Task 8: CRM Admin Views — Event Type Management

**Files:**
- Modify: `apps/scheduling/views.py` (add admin views)
- Modify: `apps/scheduling/urls.py` (add admin routes)
- Modify: `apps/scheduling/forms.py` (add EventType form)
- Create: `templates/scheduling/event_type_list.html`
- Create: `templates/scheduling/event_type_form.html`

**Step 1: Add EventType form**

```python
# Add to apps/scheduling/forms.py

class EventTypeForm(forms.ModelForm):
    class Meta:
        model = EventType
        fields = [
            'name', 'slug', 'description', 'duration_minutes',
            'color', 'is_active', 'min_advance_hours', 'buffer_minutes',
            'timezone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    # Tags as multi-select
    tag_ids = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    # Availability — 7 sets of day/start/end
    # Handle in the view with formset or manual processing

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        if team:
            self.fields['tag_ids'].queryset = Tag.objects.filter(team=team)
```

**Step 2: Add CRM admin views**

Add to `apps/scheduling/views.py`:

```python
# ── CRM Admin Views ──────────────────────────────────────────────

class EventTypeListView(LoginRequiredMixin, ListView):
    model = EventType
    template_name = 'scheduling/event_type_list.html'
    context_object_name = 'event_types'

    def get_queryset(self):
        return EventType.objects.filter(team=self.request.user.team)


@login_required
def event_type_create(request):
    """Create a new event type with availability."""
    if request.method == 'POST':
        form = EventTypeForm(request.POST, team=request.user.team)
        if form.is_valid():
            event_type = form.save(commit=False)
            event_type.owner = request.user
            event_type.team = request.user.team
            event_type.save()

            # Save tags
            event_type.tags.set(form.cleaned_data.get('tag_ids', []))

            # Save availability from POST data
            _save_availability(request, event_type)

            messages.success(request, f'Event type "{event_type.name}" created.')
            return redirect('scheduling:event_type_list')
    else:
        form = EventTypeForm(team=request.user.team)

    return render(request, 'scheduling/event_type_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def event_type_edit(request, pk):
    """Edit an existing event type."""
    event_type = get_object_or_404(EventType, pk=pk, team=request.user.team)

    if request.method == 'POST':
        form = EventTypeForm(request.POST, instance=event_type, team=request.user.team)
        if form.is_valid():
            event_type = form.save()
            event_type.tags.set(form.cleaned_data.get('tag_ids', []))
            _save_availability(request, event_type)
            messages.success(request, f'Event type "{event_type.name}" updated.')
            return redirect('scheduling:event_type_list')
    else:
        form = EventTypeForm(instance=event_type, team=request.user.team)
        form.fields['tag_ids'].initial = event_type.tags.all()

    return render(request, 'scheduling/event_type_form.html', {
        'form': form,
        'event_type': event_type,
        'is_edit': True,
        'availabilities': event_type.availabilities.all(),
    })


@login_required
@require_POST
def event_type_delete(request, pk):
    """Delete an event type."""
    event_type = get_object_or_404(EventType, pk=pk, team=request.user.team)
    name = event_type.name
    event_type.delete()
    messages.success(request, f'Event type "{name}" deleted.')
    return redirect('scheduling:event_type_list')


def _save_availability(request, event_type):
    """Parse availability from POST data and save."""
    event_type.availabilities.all().delete()
    for day in range(7):
        enabled = request.POST.get(f'day_{day}_enabled')
        start = request.POST.get(f'day_{day}_start')
        end = request.POST.get(f'day_{day}_end')
        if enabled and start and end:
            Availability.objects.create(
                event_type=event_type,
                day_of_week=day,
                start_time=start,
                end_time=end,
            )
```

**Step 3: Add admin URL patterns**

Append to `apps/scheduling/urls.py` urlpatterns:

```python
    # CRM admin views
    path('scheduling/', views.EventTypeListView.as_view(), name='event_type_list'),
    path('scheduling/create/', views.event_type_create, name='event_type_create'),
    path('scheduling/<int:pk>/edit/', views.event_type_edit, name='event_type_edit'),
    path('scheduling/<int:pk>/delete/', views.event_type_delete, name='event_type_delete'),
```

**Step 4: Write event type list template**

Create `templates/scheduling/event_type_list.html` — extends `base.html`, Bootstrap style matching other CRM pages. Shows table of event types with: name, duration, tags (colored badges), active toggle, copyable booking URL, edit/delete actions.

**Step 5: Write event type form template**

Create `templates/scheduling/event_type_form.html` — extends `base.html`. Form with:
- Name, slug (auto-generated via JS), description, duration dropdown
- Tags as checkboxes
- Availability grid: 7 rows (Mon-Sun), each with enabled checkbox, start time, end time. Default Mon-Fri 10:00-15:00 enabled.
- Min advance hours, buffer minutes
- Color picker
- Timezone dropdown

**Step 6: Commit**

```bash
git add apps/scheduling/views.py apps/scheduling/urls.py apps/scheduling/forms.py templates/scheduling/
git commit -m "feat(scheduling): add CRM admin views for event type management"
```

---

### Task 9: Bookings Management View

**Files:**
- Modify: `apps/scheduling/views.py`
- Modify: `apps/scheduling/urls.py`
- Create: `templates/scheduling/booking_list.html`

**Step 1: Add bookings list view**

```python
class BookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'scheduling/booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 25

    def get_queryset(self):
        qs = Booking.objects.filter(
            event_type__team=self.request.user.team
        ).select_related('event_type', 'contact')

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        event_type = self.request.GET.get('event_type')
        if event_type:
            qs = qs.filter(event_type_id=event_type)

        # Default: show upcoming first
        show = self.request.GET.get('show', 'upcoming')
        if show == 'upcoming':
            qs = qs.filter(start_time__gte=timezone.now(), status='scheduled')
        elif show == 'past':
            qs = qs.filter(start_time__lt=timezone.now())

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['event_types'] = EventType.objects.filter(team=self.request.user.team)
        return ctx
```

**Step 2: Add booking action views**

```python
@login_required
@require_POST
def booking_mark_completed(request, pk):
    booking = get_object_or_404(Booking, pk=pk, event_type__team=request.user.team)
    booking.status = 'completed'
    booking.save()
    messages.success(request, 'Booking marked as completed.')
    return redirect('scheduling:booking_list')


@login_required
@require_POST
def booking_mark_noshow(request, pk):
    booking = get_object_or_404(Booking, pk=pk, event_type__team=request.user.team)
    booking.status = 'no_show'
    booking.save()
    messages.success(request, 'Booking marked as no-show.')
    return redirect('scheduling:booking_list')


@login_required
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(Booking, pk=pk, event_type__team=request.user.team, status='scheduled')
    booking.status = 'cancelled'
    booking.save()

    if booking.google_event_id and booking.event_type.owner.gmail_connected:
        try:
            cal = GoogleCalendarService(booking.event_type.owner)
            cal.delete_event(booking.google_event_id)
        except Exception:
            pass

    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    send_booking_cancellation(booking, base_url)

    messages.success(request, 'Booking cancelled.')
    return redirect('scheduling:booking_list')
```

**Step 3: Add URL patterns**

```python
    path('scheduling/bookings/', views.BookingListView.as_view(), name='booking_list'),
    path('scheduling/bookings/<int:pk>/complete/', views.booking_mark_completed, name='booking_complete'),
    path('scheduling/bookings/<int:pk>/no-show/', views.booking_mark_noshow, name='booking_noshow'),
    path('scheduling/bookings/<int:pk>/cancel/', views.booking_cancel, name='booking_admin_cancel'),
```

**Step 4: Write booking list template**

Create `templates/scheduling/booking_list.html` — extends `base.html`. Shows:
- Toggle tabs: Upcoming / Past / All
- Filter by event type, status
- Table: date/time, prospect name (linked to contact), phone, email, event type, status badge, actions (complete/no-show/cancel)

**Step 5: Commit**

```bash
git add apps/scheduling/ templates/scheduling/
git commit -m "feat(scheduling): add bookings management view"
```

---

### Task 10: Dashboard Widget & Navigation

**Files:**
- Modify: existing dashboard template (wherever the CRM home page is)
- Modify: base navigation template (add Scheduling nav item)

**Step 1: Add navigation link**

Add "Scheduling" to the CRM sidebar/nav, linking to `scheduling:event_type_list`. Use a calendar icon. Place it near Signatures in the nav order.

**Step 2: Add dashboard widget**

Add an "Upcoming Calls" card to the dashboard showing next 5 scheduled bookings with: time, prospect name, phone number. Query: `Booking.objects.filter(event_type__team=team, status='scheduled', start_time__gte=now).order_by('start_time')[:5]`

**Step 3: Commit**

```bash
git add templates/
git commit -m "feat(scheduling): add nav link and dashboard widget"
```

---

### Task 11: Add pytz Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add pytz**

Check if `pytz` is already in requirements.txt. If not, add it. (Django uses `zoneinfo` by default in 5.x, but `pytz` is widely used and may already be a transitive dependency. If we prefer, we can use `zoneinfo` from the stdlib instead — but `pytz` is more explicit.)

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytz dependency"
```

---

### Task 12: Deploy to Server

**Files:**
- No new files — deploy existing code

**Step 1: Push to server and rebuild**

SSH into the DigitalOcean VPS, pull latest code, rebuild Docker containers, run migrations:

```bash
ssh root@157.245.89.79
cd /opt/crm
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Step 2: Re-authorize Gmail (for Calendar scope)**

Kelly needs to disconnect and reconnect Gmail from her CRM profile settings to grant the new Calendar scope.

**Step 3: Create first event type**

Log into CRM, go to Scheduling, create "Beach Buyer Consultation" with:
- Duration: 30 min
- Tags: BEACH
- Availability: Mon-Fri 10:00-15:00
- Min advance: 24 hours
- Buffer: 10 minutes

**Step 4: Test the booking flow end-to-end**

Visit `crm.bigbeachal.com/schedule/beach-buyer-consultation/` and test:
- Date picker shows available dates
- Time slots load correctly
- Booking creates contact in CRM with BEACH tag
- Confirmation emails sent to both parties
- Google Calendar event created
- Cancel/reschedule links work

**Step 5: Update landing page**

Add a "Schedule a Call" link on bigbeachal.com pointing to the booking URL.
