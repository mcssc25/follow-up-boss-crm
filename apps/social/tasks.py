import logging

from celery import shared_task

from .engine import find_matching_trigger
from .meta_api import get_user_profile, send_message
from .models import MessageLog, SocialAccount

logger = logging.getLogger(__name__)


@shared_task
def process_incoming_message(page_id, platform, sender_id, message_text):
    """Process an incoming social DM — match keywords and execute actions."""
    from apps.campaigns.models import CampaignEnrollment
    from apps.contacts.models import Contact, ContactActivity

    # Find the social account
    try:
        account = SocialAccount.objects.select_related('team').get(
            page_id=page_id, is_active=True,
        )
    except SocialAccount.DoesNotExist:
        # Also check instagram_account_id for IG
        try:
            account = SocialAccount.objects.select_related('team').get(
                instagram_account_id=page_id, is_active=True,
            )
        except SocialAccount.DoesNotExist:
            logger.warning("No active SocialAccount for page_id=%s", page_id)
            return

    team = account.team

    # Fetch sender profile
    profile = get_user_profile(account.access_token, sender_id)
    sender_name = profile.get('name', '')

    # Match keyword
    trigger = find_matching_trigger(team, message_text, platform)

    contact = None
    reply_sent = False

    if trigger:
        # Create or find contact
        if trigger.create_contact:
            contact = _get_or_create_contact(
                team, sender_id, sender_name, platform, trigger,
            )

        # Send reply
        reply_text = trigger.reply_text
        if trigger.reply_link:
            reply_text = f"{reply_text}\n\n{trigger.reply_link}"

        result = send_message(
            page_access_token=account.access_token,
            recipient_id=sender_id,
            text=reply_text,
        )
        reply_sent = result.get('success', False)

        # Enroll in campaign
        if trigger.campaign and contact:
            CampaignEnrollment.objects.get_or_create(
                campaign=trigger.campaign,
                contact=contact,
                defaults={'is_active': True},
            )

        # Log activity
        if contact:
            ContactActivity.objects.create(
                contact=contact,
                activity_type='note_added',
                description=(
                    f"Social DM ({platform}): \"{message_text[:100]}\""
                    f" — auto-replied via keyword \"{trigger.keyword}\""
                ),
            )

        # Notify agent
        if trigger.notify_agent:
            _notify_trigger_fired(team, trigger, sender_name, message_text, platform)

    # Always log the message
    MessageLog.objects.create(
        social_account=account,
        sender_id=sender_id,
        sender_name=sender_name,
        message_text=message_text,
        platform=platform,
        trigger_matched=trigger,
        contact_created=contact,
        reply_sent=reply_sent,
    )


def _get_or_create_contact(team, sender_id, sender_name, platform, trigger):
    """Find existing contact by platform ID or create a new one."""
    from apps.contacts.models import Contact

    platform_field = f'{platform}_id'

    # Try to find existing contact with this platform ID
    existing = Contact.objects.filter(
        team=team,
        **{f'custom_fields__{platform_field}': sender_id},
    ).first()

    if existing:
        # Update tags if new ones
        changed = False
        for tag in trigger.tags:
            if tag not in existing.tags:
                existing.tags.append(tag)
                changed = True
        if changed:
            existing.save(update_fields=['tags'])
        return existing

    # Parse name
    parts = sender_name.split(' ', 1) if sender_name else ['Unknown', '']
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''

    contact = Contact.objects.create(
        first_name=first_name,
        last_name=last_name,
        team=team,
        source='other',
        source_detail=f'{platform}_dm',
        tags=trigger.tags,
        custom_fields={platform_field: sender_id},
    )
    return contact


def _notify_trigger_fired(team, trigger, sender_name, message_text, platform):
    """Send email notification to team admins when a trigger fires."""
    from django.core.mail import send_mail

    admins = team.members.filter(role='admin')
    emails = [u.email for u in admins if u.email]
    if not emails:
        return

    send_mail(
        subject=f"Social DM Trigger: \"{trigger.keyword}\" fired on {platform}",
        message=(
            f"{sender_name} sent a DM on {platform}:\n\n"
            f"\"{message_text}\"\n\n"
            f"Auto-reply was sent using trigger \"{trigger.keyword}\"."
        ),
        from_email=None,
        recipient_list=emails,
        fail_silently=True,
    )
