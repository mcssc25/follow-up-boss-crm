import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.accounts.notifications import (
    notify_overdue_digest,
    notify_task_created,
    notify_task_reminder,
)
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
        .select_related('contact')
        .prefetch_related('assigned_to')
    )

    count = 0
    for task in upcoming:
        notify_task_reminder(task)
        for agent in task.assigned_to.all():
            send_push_notification(
                user=agent,
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
    now = timezone.now()
    overdue = (
        Task.objects.filter(status='pending', due_date__lt=now)
        .select_related('contact')
        .prefetch_related('assigned_to')
        .order_by('due_date')
    )

    # Group by agent (a task can appear for multiple agents)
    agent_tasks = {}
    for task in overdue:
        for agent in task.assigned_to.all():
            agent_tasks.setdefault(agent, []).append(task)

    count = 0
    for agent, tasks in agent_tasks.items():
        notify_overdue_digest(agent, tasks)
        count += 1

    logger.info("Sent overdue digest to %d agents", count)
    return count


@shared_task
def send_daily_task_reminders():
    """Daily 9 AM push reminder for all pending tasks with future deadlines."""
    now = timezone.now()
    pending_tasks = (
        Task.objects.filter(status='pending', due_date__gt=now)
        .prefetch_related('assigned_to')
    )

    count = 0
    for task in pending_tasks:
        due_str = task.due_date.strftime('%b %d at %I:%M %p')
        for agent in task.assigned_to.all():
            send_push_notification(
                user=agent,
                title='Task Reminder',
                body=f'{task.title} — due {due_str}',
                url='/tasks/',
            )
            count += 1

    logger.info("Sent %d daily task reminders", count)
    return count


@shared_task
def create_task_notifications(task_id):
    """Send push notification and create calendar event for each assignee."""
    try:
        task = Task.objects.prefetch_related('assignments__user').get(pk=task_id)
    except Task.DoesNotExist:
        logger.warning("Task %s not found for notification", task_id)
        return

    due_str = task.due_date.strftime('%b %d at %I:%M %p')

    for assignment in task.assignments.select_related('user').all():
        agent = assignment.user

        # Email notification
        notify_task_created(task, agent)

        # Push notification
        send_push_notification(
            user=agent,
            title=f'New Task: {task.title}',
            body=f'Due {due_str} — Priority: {task.get_priority_display()}',
            url='/tasks/',
        )

        # Google Calendar event
        if not agent.gmail_connected:
            logger.info(
                "Skipping calendar for task %s, user %s — Gmail not connected",
                task_id, agent.pk,
            )
            continue

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
                assignment.google_event_id = event_id
                assignment.save(update_fields=['google_event_id'])
                logger.info(
                    "Created calendar event %s for task %s, user %s",
                    event_id, task_id, agent.pk,
                )
        except Exception:
            logger.exception(
                "Failed to create calendar event for task %s, user %s",
                task_id, agent.pk,
            )
