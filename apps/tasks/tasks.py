import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.accounts.notifications import notify_overdue_digest, notify_task_reminder

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
