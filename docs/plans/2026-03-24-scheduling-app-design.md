# Scheduling App Design (Calendly Clone)

**Date:** 2026-03-24
**Status:** Approved

## Overview

A new `scheduling` Django app for the CRM that provides Calendly-like phone appointment booking. Public-facing booking pages allow leads/prospects from landing pages and social media to schedule calls with Kelly (or future agents). Each booking page has its own URL, duration, tags, and availability settings.

Hosted on the existing CRM server at `crm.bigbeachal.com/schedule/<slug>/`.

## Data Models

### EventType

Each booking page configuration.

| Field | Type | Description |
|-------|------|-------------|
| name | CharField | e.g., "Beach Buyer Consultation" |
| slug | SlugField | URL slug, e.g., "beach-buyers" |
| duration_minutes | IntegerField | 15, 30, etc. |
| description | TextField | Shown on booking page |
| tags | ManyToManyField(Tag) | Auto-applied to CRM contact on booking |
| owner | ForeignKey(User) | The agent who owns this event type |
| color | CharField | Visual distinction in CRM admin |
| is_active | BooleanField | Toggle on/off without deleting |
| min_advance_hours | IntegerField | Minimum scheduling notice (e.g., 24 = no same-day) |
| buffer_minutes | IntegerField | Padding between appointments |

### Availability

Weekly recurring schedule. One row per day per event type.

| Field | Type | Description |
|-------|------|-------------|
| event_type | ForeignKey(EventType) | Parent event type |
| day_of_week | IntegerField | 0-6 (Mon-Sun) |
| start_time | TimeField | e.g., 10:00 |
| end_time | TimeField | e.g., 15:00 |

### Booking

A scheduled appointment.

| Field | Type | Description |
|-------|------|-------------|
| event_type | ForeignKey(EventType) | Which event type was booked |
| contact | ForeignKey(Contact) | Created or linked on booking |
| start_time | DateTimeField | Appointment start (UTC) |
| end_time | DateTimeField | Appointment end (UTC) |
| phone_number | CharField | Prospect's phone |
| email | EmailField | Prospect's email |
| first_name | CharField | |
| last_name | CharField | |
| status | CharField | scheduled / cancelled / completed / no_show |
| cancel_token | UUIDField | For cancel/reschedule links |
| google_event_id | CharField | For syncing with Google Calendar |
| notes | TextField | Optional message from prospect |
| created_at | DateTimeField | auto_now_add |

## Google Calendar Integration

Extends the existing Google OAuth setup (currently used for Gmail) to include Calendar scopes.

- **Reading busy times:** Calls Google Calendar `freebusy` API when prospect views booking page. Combined with Availability schedule, shows only open slots.
- **Creating events:** On booking confirmation, creates a Google Calendar event on the owner's calendar with prospect name, phone number, and event type in description.
- **Cancel/reschedule:** Deletes or updates Google Calendar event via stored `google_event_id`.
- **Timezone:** Owner sets timezone in event type (defaults to account timezone). Slots displayed in prospect's browser timezone, stored in UTC.
- **No webhooks needed:** We manage all events directly, so sync is inherent.

## Public Booking Flow

### Prospect Experience

1. Clicks link from landing page/social → `crm.bigbeachal.com/schedule/beach-buyers/`
2. Sees booking page: event type name, description, duration, calendar date picker
3. Picks a date → available time slots load (filtered by: availability schedule, Google Calendar busy times, existing bookings, min advance notice, buffer time)
4. Picks a time slot → form: first name, last name, email, phone number, optional notes
5. Submits → confirmation page with appointment details
6. **Prospect receives:** confirmation email with date/time, "Add to Google Calendar" button (.ics link), cancel/reschedule links
7. **Owner receives:** confirmation email with prospect name, phone, time. Event auto-added to Google Calendar.

### Cancel/Reschedule

- **Cancel:** Prospect clicks cancel link → confirmation page → booking cancelled → Google Calendar event deleted → both parties emailed
- **Reschedule:** Prospect clicks reschedule link → booking page with info pre-filled → old booking cancelled when new one confirmed

### CRM Integration (on booking creation)

1. Search for existing Contact by email
2. If not found, create new Contact with first/last name, email, phone
3. Apply all tags from the EventType
4. Log a ContactActivity (e.g., "Scheduled 30-min Beach Buyer Consultation for March 28 at 2:00 PM")

## CRM Admin Interface

### Event Types Page

- List view: name, duration, tags, active/inactive, copyable booking URL
- Create/edit form: name, slug (auto-generated, editable), duration, description, tags (multi-select), availability schedule (day/time grid), min advance hours, buffer minutes
- Toggle active/inactive
- Delete with confirmation

### Bookings Page

- List view: upcoming and past bookings, filterable by event type and status
- Columns: date/time, prospect name, phone, email, event type, status
- Actions: mark completed, mark no-show, cancel
- Click through to linked CRM contact

### Dashboard Widget

- "Upcoming Calls" card on CRM home page
- Shows next 5 bookings: name, time, phone number

## UI Design

### Public Booking Page

- Clean, standalone layout (no CRM admin chrome) — similar to signature signing pages
- Mobile-responsive (prospects come from social links on phones)
- White background, professional styling consistent with BigBeachAL brand
- Calendar date picker on left, time slots on right (stacked on mobile)

### CRM Admin Pages

- Same Bootstrap style as rest of CRM (signatures, contacts, pipeline)

### Technology

- Vanilla JS + HTMX for interactivity (date picker, slot loading)
- No external JS frameworks
- Django templates

## Architecture

- New Django app: `apps/scheduling/`
- Standard structure: models.py, views.py, urls.py, forms.py, admin.py, tasks.py
- Templates: `templates/scheduling/` (admin) and `templates/scheduling/public/` (booking pages)
- Google Calendar service: `apps/scheduling/calendar.py`
- Email notifications: `apps/scheduling/email.py` (confirmation, cancellation)
- Celery tasks: reminder emails (optional future enhancement)
- URL prefix: `/schedule/` for public, `/scheduling/` for CRM admin
