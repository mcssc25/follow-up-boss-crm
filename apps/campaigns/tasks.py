import re
from urllib.parse import quote

from celery import shared_task
from django.utils import timezone

from django.conf import settings

from .email_renderer import get_video_html, render_campaign_email
from .models import CampaignEnrollment, EmailLog
from apps.accounts.gmail import GmailService
from apps.contacts.models import ContactActivity


@shared_task
def process_due_emails():
    """Find all enrollments with due emails and dispatch individual sends."""
    due_enrollments = CampaignEnrollment.objects.filter(
        is_active=True,
        next_send_at__lte=timezone.now(),
        contact__email__gt='',
        campaign__is_active=True,
    ).select_related(
        'contact', 'contact__assigned_to', 'campaign', 'current_step',
    )
    for enrollment in due_enrollments:
        send_campaign_email.delay(enrollment.id)


def _inject_tracking(html_body, tracking_id, base_url):
    """Inject a tracking pixel and wrap links for click tracking."""
    # Tracking pixel (1x1 transparent gif)
    pixel_url = f"{base_url}/campaigns/track/{tracking_id}/open/"
    pixel_tag = f'<img src="{pixel_url}" width="1" height="1" style="display:none" alt="" />'
    # Append pixel before closing </body> or at end
    if '</body>' in html_body:
        html_body = html_body.replace('</body>', f'{pixel_tag}</body>')
    else:
        html_body += pixel_tag

    # Wrap all href links for click tracking
    def replace_link(match):
        original_url = match.group(1)
        # Don't wrap tracking pixel URL or mailto links
        if 'track/' in original_url or original_url.startswith('mailto:'):
            return match.group(0)
        redirect_url = f"{base_url}/campaigns/track/{tracking_id}/click/?url={quote(original_url, safe='')}"
        return f'href="{redirect_url}"'

    html_body = re.sub(r'href="([^"]+)"', replace_link, html_body)

    return html_body


@shared_task
def send_campaign_email(enrollment_id):
    """Send a single campaign email and advance the enrollment."""
    try:
        enrollment = CampaignEnrollment.objects.select_related(
            'contact', 'contact__assigned_to', 'current_step', 'campaign',
        ).get(id=enrollment_id, is_active=True)
    except CampaignEnrollment.DoesNotExist:
        return

    contact = enrollment.contact
    agent = contact.assigned_to
    step = enrollment.current_step

    if not agent or not agent.gmail_connected:
        return

    # Render email with merge fields
    rendered_body = render_campaign_email(step.body, contact, agent)
    rendered_subject = render_campaign_email(step.subject, contact, agent)

    # Append video thumbnail/play button if step has a video
    if step.video_file:
        base_url = getattr(settings, 'BASE_URL', 'https://crm.yourdomain.com').rstrip('/')
        rendered_body += get_video_html(step, contact, base_url)

    # Create EmailLog entry for tracking
    email_log = EmailLog.objects.create(
        enrollment=enrollment,
        step=step,
    )

    # Inject tracking pixel and wrap links
    base_url = getattr(settings, 'BASE_URL', 'https://crm.yourdomain.com').rstrip('/')
    rendered_body = _inject_tracking(rendered_body, email_log.tracking_id, base_url)

    # Send via Gmail
    gmail = GmailService(
        access_token=agent.gmail_access_token,
        refresh_token=agent.gmail_refresh_token,
    )
    result = gmail.send_email(
        to=contact.email,
        subject=rendered_subject,
        body_html=rendered_body,
        from_email=agent.email,
    )

    if result['success']:
        # Log activity
        ContactActivity.objects.create(
            contact=contact,
            activity_type='email_sent',
            description=f"Campaign email: {rendered_subject}",
            metadata={
                'campaign_id': enrollment.campaign.id,
                'step_order': step.order,
                'tracking_id': str(email_log.tracking_id),
            },
        )
        # Update last contacted
        contact.last_contacted_at = timezone.now()
        contact.save(update_fields=['last_contacted_at'])
        # Advance to next step
        enrollment.advance_to_next_step()
