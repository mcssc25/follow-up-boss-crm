from datetime import datetime, timedelta, date as dt_date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

import pytz

from apps.contacts.models import Contact, ContactActivity
from .calendar import GoogleCalendarService
from .email import send_booking_confirmation, send_booking_cancellation, send_owner_notification, send_owner_cancellation
from .forms import BookingForm
from .models import EventType, Booking
from .slots import generate_available_slots


# -- Public Booking Views --

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
            pass

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
    try:
        contact = Contact.objects.get(
            email__iexact=booking.email,
            team=event_type.team,
        )
        if not contact.phone and booking.phone_number:
            contact.phone = booking.phone_number
            contact.save()
    except Contact.DoesNotExist:
        contact = Contact.objects.create(
            first_name=booking.first_name,
            last_name=booking.last_name,
            email=booking.email,
            phone=booking.phone_number,
            source='landing_page',
            source_detail=f'Scheduling: {event_type.name}',
            team=event_type.team,
        )

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

        if booking.google_event_id and booking.event_type.owner.gmail_connected:
            try:
                cal = GoogleCalendarService(booking.event_type.owner)
                cal.delete_event(booking.google_event_id)
            except Exception:
                pass

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
    """Handle reschedule — cancel old booking, create new one."""
    old_booking = get_object_or_404(Booking, cancel_token=token, status='scheduled')

    old_booking.status = 'cancelled'
    old_booking.save()

    if old_booking.google_event_id and old_booking.event_type.owner.gmail_connected:
        try:
            cal = GoogleCalendarService(old_booking.event_type.owner)
            cal.delete_event(old_booking.google_event_id)
        except Exception:
            pass

    return confirm_booking(request, slug)
