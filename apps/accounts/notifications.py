import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_new_lead(contact):
    """Send email notification to assigned agent about new lead."""
    agent = contact.assigned_to
    if not agent or not agent.email:
        return

    subject = f"New Lead: {contact.first_name} {contact.last_name}"
    message = (
        f"A new lead has been assigned to you.\n\n"
        f"Name: {contact}\n"
        f"Email: {contact.email}\n"
        f"Phone: {contact.phone}\n"
        f"Source: {contact.get_source_display()}"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=[agent.email],
            fail_silently=True,
        )
        logger.info("New lead notification sent to %s for contact %s", agent.email, contact)
    except Exception:
        logger.exception("Failed to send new lead notification for contact %s", contact)


def notify_task_reminder(task):
    """Send email reminder for an upcoming task."""
    agent = task.assigned_to
    if not agent or not agent.email:
        return

    contact_info = f"\nContact: {task.contact}" if task.contact else ""
    subject = f"Task Reminder: {task.title}"
    message = (
        f"You have an upcoming task due soon.\n\n"
        f"Task: {task.title}\n"
        f"Due: {task.due_date.strftime('%b %d, %Y at %I:%M %p')}\n"
        f"Priority: {task.get_priority_display()}"
        f"{contact_info}"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[agent.email],
            fail_silently=True,
        )
        logger.info("Task reminder sent to %s for task %s", agent.email, task)
    except Exception:
        logger.exception("Failed to send task reminder for task %s", task)


def notify_overdue_digest(agent, overdue_tasks):
    """Send a daily digest of overdue tasks to an agent."""
    if not agent or not agent.email or not overdue_tasks:
        return

    task_lines = []
    for task in overdue_tasks:
        contact_info = f" (Contact: {task.contact})" if task.contact else ""
        task_lines.append(
            f"  - {task.title} (Due: {task.due_date.strftime('%b %d, %Y')}){contact_info}"
        )

    subject = f"Overdue Tasks: {len(overdue_tasks)} task(s) need attention"
    message = (
        f"You have {len(overdue_tasks)} overdue task(s):\n\n"
        + "\n".join(task_lines)
        + "\n\nPlease log in to complete or reschedule these tasks."
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[agent.email],
            fail_silently=True,
        )
        logger.info("Overdue digest sent to %s with %d tasks", agent.email, len(overdue_tasks))
    except Exception:
        logger.exception("Failed to send overdue digest to %s", agent.email)
