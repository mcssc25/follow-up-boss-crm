import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.accounts.notifications import notify_overdue_digest, notify_task_reminder
from apps.pwa.push import send_push_notification
from apps.scheduling.calendar import GoogleCalendarService

from .models import Task

logger = logging.getLogger(__name__)


@shared_task
def send_due_reminders():
    """Send reminders for tasks due in the next hour."""
    now = timezone.now()
    upcoming = (
        Task.objects.filter(
            status='pending',
            due_date__gte=now,
            due_date__lte=now + timedelta(hours=1),
        )
        .select_related('assigned_to', 'contact')
    )

    count = 0
    for task in upcoming:
        notify_task_reminder(task)
        send_push_notification(
            user=task.assigned_to,
            title='Task Due Soon',
            body=f'{task.title} is due in less than an hour',
            url='/tasks/',
        )
        count += 1

    logger.info("Sent %d task due reminders", count)
    return count


@shared_task
def send_overdue_digest():
    """Daily digest of overdue tasks, grouped by agent."""
    from apps.accounts.models import User

    now = timezone.now()
    overdue = (
        Task.objects.filter(status='pending', due_date__lt=now)
        .select_related('assigned_to', 'contact')
        .order_by('assigned_to', 'due_date')
    )

    # Group by agent
    agent_tasks = {}
    for task in overdue:
        if task.assigned_to_id:
            agent_tasks.setdefault(task.assigned_to, []).append(task)

    count = 0
    for agent, tasks in agent_tasks.items():
        notify_overdue_digest(agent, tasks)
        count += 1

    logger.info("Sent overdue digest to %d agents", count)
    return count


@shared_task
def create_task_notifications(task_id):
    """Send push notification and create calendar event when a task is created."""
    try:
        task = Task.objects.select_related('assigned_to').get(pk=task_id)
    except Task.DoesNotExist:
        logger.warning("Task %s not found for notification", task_id)
        return

    agent = task.assigned_to
    due_str = task.due_date.strftime('%b %d at %I:%M %p')

    # Push notification
    send_push_notification(
        user=agent,
        title=f'New Task: {task.title}',
        body=f'Due {due_str} — Priority: {task.get_priority_display()}',
        url='/tasks/',
    )

    # Google Calendar event
    if not agent.gmail_connected:
        logger.info("Skipping calendar for task %s — agent Gmail not connected", task_id)
        return

    try:
        cal = GoogleCalendarService(agent)
        event = {
            'summary': task.title,
            'description': (
                f"Priority: {task.get_priority_display()}\n"
                f"{task.description}"
            ).strip(),
            'start': {
                'dateTime': task.due_date.isoformat(),
                'timeZone': 'America/Chicago',
            },
            'end': {
                'dateTime': (task.due_date + timedelta(minutes=30)).isoformat(),
                'timeZone': 'America/Chicago',
            },
        }
        result = cal.service.events().insert(
            calendarId='primary', body=event, sendUpdates='none',
        ).execute()
        event_id = result.get('id', '')
        if event_id:
            task.google_event_id = event_id
            task.save(update_fields=['google_event_id'])
            logger.info("Created calendar event %s for task %s", event_id, task_id)
    except Exception:
        logger.exception("Failed to create calendar event for task %s", task_id)
