import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_results_email(contact, results_url):
    """Send the lead an HTML email with a link to their condo search results via Gmail API."""
    from .gmail import GmailService

    agent = contact.assigned_to
    if not contact.email or not agent or not agent.gmail_connected:
        logger.warning("Cannot send results email for %s — no agent or Gmail not connected", contact)
        return

    first_name = contact.first_name or "there"
    subject = f"{first_name}, Your Beach Condo Matches Are Ready!"

    body_html = f"""
    <div style="margin:0;padding:0;background-color:#fffbf5;font-family:'Nunito Sans',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#fffbf5;padding:40px 0;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg,#52c09a 0%,#7dd3fc 100%);padding:36px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-family:'Georgia',serif;font-size:28px;font-weight:400;letter-spacing:0.5px;text-shadow:0 1px 3px rgba(0,0,0,0.15);">
                  Big<span style="font-weight:700;">Beach</span><span style="color:#ffd699;">AL</span>
                </h1>
                <p style="margin:8px 0 0;color:#ffffff;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.9;">
                  Gulf Shores &amp; Orange Beach
                </p>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:40px;">
                <h2 style="margin:0 0 8px;color:#1c6b51;font-family:'Georgia',serif;font-size:24px;font-weight:400;">
                  Hi {first_name}!
                </h2>
                <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
                  Thanks for taking our condo quiz &mdash; we&rsquo;ve matched you with properties
                  that fit exactly what you&rsquo;re looking for on the Alabama Gulf Coast.
                </p>

                <!-- CTA Button -->
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr><td align="center" style="padding:8px 0 32px;">
                    <a href="{results_url}"
                       style="display:inline-block;background:linear-gradient(135deg,#30a57e 0%,#38bdf8 100%);color:#ffffff;text-decoration:none;
                              padding:16px 40px;border-radius:50px;font-size:16px;font-weight:700;
                              letter-spacing:0.3px;box-shadow:0 4px 14px rgba(48,165,126,0.3);">
                      View My Matches &rarr;
                    </a>
                  </td></tr>
                </table>

                <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
                  Your personalized results include an interactive map, current MLS listings,
                  video tours, and all the details you need to compare your top picks.
                  Bookmark the link above so you can come back anytime.
                </p>

                <!-- Divider -->
                <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 24px;">
                  <tr><td align="center">
                    <div style="width:60px;height:2px;background:linear-gradient(90deg,#52c09a,#7dd3fc);border-radius:2px;"></div>
                  </td></tr>
                </table>

                <p style="margin:0 0 8px;color:#374151;font-size:15px;line-height:1.6;">
                  <strong>Ready to take the next step?</strong>
                </p>
                <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.6;">
                  Whether you want to schedule a tour, explore financing options, or just have
                  questions about Gulf Shores &amp; Orange Beach &mdash; we&rsquo;re here for you.
                  Just hit reply and we&rsquo;ll be in touch!
                </p>

                <p style="margin:0;color:#374151;font-size:15px;">
                  Talk soon,<br/>
                  <strong>Kelly &amp; Dave Davis</strong><br/>
                  <span style="color:#6b7280;font-size:13px;">Big Beach AL &middot; Gulf Shores &amp; Orange Beach Real Estate</span>
                </p>
              </td>
            </tr>

            <!-- Social Section -->
            <tr>
              <td style="background:linear-gradient(180deg,#f0f9ff 0%,#e0f5ed 100%);padding:32px 40px;text-align:center;border-top:1px solid #e0f2fe;">
                <p style="margin:0 0 6px;color:#1c6b51;font-family:'Georgia',serif;font-size:18px;font-weight:600;">
                  Visit Our Socials
                </p>
                <p style="margin:0 0 20px;color:#6b7280;font-size:14px;line-height:1.5;">
                  See more Gulf Shores &amp; Orange Beach day-to-day activity!
                </p>
                <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
                  <tr>
                    <td style="padding:0 6px;">
                      <a href="https://www.facebook.com/kelly.goodworth.davis"
                         style="display:inline-block;background:#ffffff;color:#228564;text-decoration:none;
                                padding:10px 22px;border-radius:50px;font-size:14px;font-weight:700;
                                border:2px solid #30a57e;letter-spacing:0.3px;">
                        Facebook
                      </a>
                    </td>
                    <td style="padding:0 6px;">
                      <a href="https://www.instagram.com/diy.davis/"
                         style="display:inline-block;background:#ffffff;color:#228564;text-decoration:none;
                                padding:10px 22px;border-radius:50px;font-size:14px;font-weight:700;
                                border:2px solid #30a57e;letter-spacing:0.3px;">
                        Instagram
                      </a>
                    </td>
                    <td style="padding:0 6px;">
                      <a href="https://www.youtube.com/@GulfShoresAlabamaRealEstate"
                         style="display:inline-block;background:#ffffff;color:#228564;text-decoration:none;
                                padding:10px 22px;border-radius:50px;font-size:14px;font-weight:700;
                                border:2px solid #30a57e;letter-spacing:0.3px;">
                        YouTube
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="background:#f2faf7;padding:16px 40px;text-align:center;border-top:1px solid #e0f5ed;">
                <p style="margin:0;color:#85d6b8;font-size:12px;">
                  kelly@bigbeachal.com &middot; bigbeachal.com
                </p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </div>
    """

    gmail = GmailService(
        access_token=agent.gmail_access_token,
        refresh_token=agent.gmail_refresh_token,
    )
    result = gmail.send_email(
        to=contact.email,
        subject=subject,
        body_html=body_html,
        from_email=agent.email,
    )

    if result['success']:
        logger.info("Results email sent to %s via Gmail for contact %s", contact.email, contact)
    else:
        logger.error("Results email failed for %s: %s", contact, result.get('error'))


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


def notify_task_created(task, agent):
    """Send email to an assignee when a new task is created for them."""
    if not agent or not agent.email:
        return

    contact_info = f"\nContact: {task.contact}" if task.contact else ""
    description = f"\n\n{task.description}" if task.description else ""
    subject = f"New Task Assigned: {task.title}"
    message = (
        f"A new task has been assigned to you.\n\n"
        f"Task: {task.title}\n"
        f"Due: {task.due_date.strftime('%b %d, %Y at %I:%M %p')}\n"
        f"Priority: {task.get_priority_display()}"
        f"{contact_info}"
        f"{description}"
        f"\n\nView your tasks: https://crm.bigbeachal.com/tasks/"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[agent.email],
            fail_silently=True,
        )
        logger.info("New task email sent to %s for task %s", agent.email, task)
    except Exception:
        logger.exception("Failed to send new task email for task %s", task)


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
