# Task Notifications & Calendar Sync — Design

## Overview
Add push notifications and Google Calendar integration to the Tasks app so assigned agents are notified immediately when tasks are created, reminded daily until the deadline, and reminded 1 hour before the due date.

## Requirements
- Push notification on task creation to the assignee
- Google Calendar event created on assignee's calendar with task details
- Daily push reminder at 9:00 AM CT for all pending tasks with future deadlines
- 1-hour-before-deadline push reminder (already exists)
- On task completion: stop reminders + remove calendar event
- No user confirmation needed for calendar events

## Model Change
Add `google_event_id` (CharField, max_length=255, blank=True, null=True) to the `Task` model to track the Google Calendar event for cleanup on completion.

## On Task Creation
Triggered from `TaskCreateView.form_valid` via a Celery task `create_task_notifications.delay(task.id)`:

1. **Push notification** to assignee: "New Task: {title} — Due {due_date}"
2. **Google Calendar event** on assignee's calendar:
   - Title: task title
   - Description: task description + priority
   - Start/end: task due_date (as a timed event)
   - Uses existing `GoogleCalendarService.create_event()`
3. Store returned `google_event_id` on the Task model

## Daily Reminders (New Celery Beat task)
- Task: `send_daily_task_reminders`
- Schedule: crontab, 9:00 AM CT daily
- Query: all tasks where `status='pending'` and `due_date > now`
- Action: push notification to each assignee — "Reminder: {title} due {due_date}"

## 1-Hour Reminder (Existing)
- `send_due_reminders` already runs hourly and finds tasks due in the next hour
- Already sends push notifications — no changes needed

## On Task Completion
In the `task_complete` view:
1. If task has a `google_event_id`, call `GoogleCalendarService.delete_event()` to remove the calendar event
2. Reminders stop automatically — all reminder queries filter by `status='pending'`

## Error Handling
- If assignee doesn't have Gmail connected (`gmail_connected=False`), skip calendar event creation; push notification still goes out
- Log Google Calendar API failures but don't block task creation
- If calendar event deletion fails on completion, log the error and continue

## Existing Infrastructure Used
- `apps/pwa/push.py` — `send_push_notification(user, title, body, url)`
- `apps/scheduling/calendar.py` — `GoogleCalendarService` (create_event, delete_event)
- Celery Beat with `django_celery_beat.schedulers:DatabaseScheduler`
- Redis as Celery broker (already configured)
