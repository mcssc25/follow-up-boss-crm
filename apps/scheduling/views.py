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
from .models import EventType, Availability, Booking
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
        dirty = False
        if not contact.phone and booking.phone_number:
            contact.phone = booking.phone_number
            dirty = True
        # Only assign to the schedule owner if the contact is currently unassigned —
        # never override an existing agent assignment.
        if contact.assigned_to_id is None:
            contact.assigned_to = event_type.owner
            dirty = True
        if dirty:
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
            assigned_to=event_type.owner,
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
            result = cal.create_event(booking)
            if result.get('id'):
                booking.google_event_id = result['id']
            if result.get('meet_url'):
                booking.google_meet_url = result['meet_url']
            if result:
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


DAY_CHOICES = Availability.DAYS_OF_WEEK

# -- CRM Admin Views --

class EventTypeListView(LoginRequiredMixin, ListView):
    model = EventType
    template_name = 'scheduling/event_type_list.html'
    context_object_name = 'event_types'

    def get_queryset(self):
        return EventType.objects.filter(team=self.request.user.team)


@login_required
def event_type_create(request):
    """Create a new event type with availability."""
    from .forms import EventTypeForm
    if request.method == 'POST':
        form = EventTypeForm(request.POST, team=request.user.team, user=request.user)
        if form.is_valid():
            event_type = form.save(commit=False)
            # Non-admins always own their own schedules regardless of POST data.
            event_type.owner = request.user if not request.user.is_admin else form.cleaned_data['owner']
            event_type.team = request.user.team
            event_type.save()
            event_type.tags.set(form.cleaned_data.get('tag_ids', []))
            _save_availability(request, event_type)
            messages.success(request, f'Event type "{event_type.name}" created.')
            return redirect('scheduling:event_type_list')
    else:
        form = EventTypeForm(team=request.user.team, user=request.user, initial={'owner': request.user})
    return render(request, 'scheduling/event_type_form.html', {
        'form': form,
        'is_edit': False,
        'day_choices': DAY_CHOICES,
    })


@login_required
def event_type_edit(request, pk):
    """Edit an existing event type."""
    from .forms import EventTypeForm
    event_type = get_object_or_404(EventType, pk=pk, team=request.user.team)
    if not request.user.is_admin and event_type.owner_id != request.user.id:
        messages.error(request, "You can only edit your own schedules.")
        return redirect('scheduling:event_type_list')
    if request.method == 'POST':
        form = EventTypeForm(request.POST, instance=event_type, team=request.user.team, user=request.user)
        if form.is_valid():
            event_type = form.save(commit=False)
            event_type.owner = request.user if not request.user.is_admin else form.cleaned_data['owner']
            event_type.save()
            event_type.tags.set(form.cleaned_data.get('tag_ids', []))
            _save_availability(request, event_type)
            messages.success(request, f'Event type "{event_type.name}" updated.')
            return redirect('scheduling:event_type_list')
    else:
        form = EventTypeForm(instance=event_type, team=request.user.team, user=request.user)
        form.fields['tag_ids'].initial = event_type.tags.all()
        form.fields['owner'].initial = event_type.owner
    return render(request, 'scheduling/event_type_form.html', {
        'form': form,
        'event_type': event_type,
        'is_edit': True,
        'availabilities': event_type.availabilities.all(),
        'day_choices': DAY_CHOICES,
    })


@login_required
@require_POST
def event_type_delete(request, pk):
    """Delete an event type."""
    event_type = get_object_or_404(EventType, pk=pk, team=request.user.team)
    if not request.user.is_admin and event_type.owner_id != request.user.id:
        messages.error(request, "You can only delete your own schedules.")
        return redirect('scheduling:event_type_list')
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


# -- Admin Booking Management Views --

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

        show = self.request.GET.get('show', 'upcoming')
        if show == 'upcoming':
            qs = qs.filter(start_time__gte=timezone.now(), status='scheduled')
        elif show == 'past':
            qs = qs.filter(start_time__lt=timezone.now())

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['event_types'] = EventType.objects.filter(team=self.request.user.team)
        ctx['current_show'] = self.request.GET.get('show', 'upcoming')
        return ctx


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
def booking_admin_cancel(request, pk):
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
