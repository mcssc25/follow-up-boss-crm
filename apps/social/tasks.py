import logging

from celery import shared_task

from .engine import find_matching_trigger
from .meta_api import get_user_profile, send_message, send_private_reply
from .models import MessageLog, SocialAccount

logger = logging.getLogger(__name__)


@shared_task
def process_incoming_message(page_id, platform, sender_id, message_text):
    """Backwards-compatible entry point for older DM webhook calls."""
    return process_incoming_event(
        page_id=page_id,
        platform=platform,
        sender_id=sender_id,
        message_text=message_text,
        event_type='message',
    )


@shared_task
def process_incoming_event(
    page_id,
    platform,
    sender_id,
    message_text,
    event_type='message',
    sender_name='',
    comment_id='',
    post_id='',
    external_event_id='',
    raw_event=None,
):
    """Process an incoming social DM or comment event."""
    from apps.campaigns.models import CampaignEnrollment
    from apps.contacts.models import ContactActivity

    account = _get_social_account(page_id)
    if not account:
        return

    team = account.team
    raw_event = raw_event or {}

    if not sender_name and sender_id:
        profile = get_user_profile(account.access_token, sender_id)
        sender_name = profile.get('name', '')

    trigger = find_matching_trigger(team, message_text, platform, event_type=event_type)

    contact = None
    reply_sent = False
    reply_error = ''

    if trigger:
        if trigger.create_contact:
            contact = _get_or_create_contact(
                team=team,
                sender_id=sender_id,
                sender_name=sender_name,
                platform=platform,
                trigger=trigger,
                event_type=event_type,
            )

        reply_text = trigger.reply_text
        if trigger.reply_link:
            reply_text = f"{reply_text}\n\n{trigger.reply_link}"

        result = _send_trigger_reply(
            account=account,
            trigger=trigger,
            sender_id=sender_id,
            comment_id=comment_id,
            text=reply_text,
        )
        reply_sent = result.get('success', False)
        reply_error = result.get('error', '')

        if trigger.campaign and contact:
            CampaignEnrollment.objects.get_or_create(
                campaign=trigger.campaign,
                contact=contact,
                defaults={'is_active': True},
            )

        if contact:
            ContactActivity.objects.create(
                contact=contact,
                activity_type='note_added',
                description=(
                    f"Social {event_type} ({platform}): \"{message_text[:100]}\""
                    f" - auto-replied via keyword \"{trigger.keyword}\""
                ),
                metadata={
                    'platform': platform,
                    'event_type': event_type,
                    'comment_id': comment_id,
                    'post_id': post_id,
                },
            )

        if trigger.notify_agent:
            _notify_trigger_fired(
                team=team,
                trigger=trigger,
                sender_name=sender_name,
                message_text=message_text,
                platform=platform,
                event_type=event_type,
            )

    MessageLog.objects.create(
        social_account=account,
        sender_id=sender_id,
        sender_name=sender_name,
        message_text=message_text,
        platform=platform,
        event_type=event_type,
        external_event_id=external_event_id,
        comment_id=comment_id,
        post_id=post_id,
        trigger_matched=trigger,
        contact_created=contact,
        reply_sent=reply_sent,
        reply_error=reply_error,
        raw_payload=raw_event,
    )


def _get_social_account(page_id):
    try:
        return SocialAccount.objects.select_related('team').get(
            page_id=page_id,
            is_active=True,
        )
    except SocialAccount.DoesNotExist:
        try:
            return SocialAccount.objects.select_related('team').get(
                instagram_account_id=page_id,
                is_active=True,
            )
        except SocialAccount.DoesNotExist:
            logger.warning("No active SocialAccount for page_id=%s", page_id)
            return None


def _send_trigger_reply(account, trigger, sender_id, comment_id, text):
    if trigger.response_type == 'private_reply':
        if not comment_id:
            return {'success': False, 'error': 'No comment_id available for private reply'}
        return send_private_reply(
            page_access_token=account.access_token,
            comment_id=comment_id,
            text=text,
        )

    if not sender_id:
        return {'success': False, 'error': 'No sender_id available for DM reply'}

    return send_message(
        page_access_token=account.access_token,
        recipient_id=sender_id,
        text=text,
    )


def _get_or_create_contact(team, sender_id, sender_name, platform, trigger, event_type):
    from apps.contacts.models import Contact

    platform_field = f'{platform}_id'

    existing = Contact.objects.filter(
        team=team,
        **{f'custom_fields__{platform_field}': sender_id},
    ).first()

    if existing:
        changed = False
        for tag in trigger.tags:
            if tag not in existing.tags:
                existing.tags.append(tag)
                changed = True
        if changed:
            existing.save(update_fields=['tags'])
        return existing

    parts = sender_name.split(' ', 1) if sender_name else ['Unknown', '']
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''

    return Contact.objects.create(
        first_name=first_name,
        last_name=last_name,
        team=team,
        source='other',
        source_detail=f'{platform}_{event_type}',
        tags=trigger.tags,
        custom_fields={platform_field: sender_id} if sender_id else {},
    )


def _notify_trigger_fired(team, trigger, sender_name, message_text, platform, event_type):
    from django.core.mail import send_mail

    admins = team.members.filter(role='admin')
    emails = [u.email for u in admins if u.email]
    if not emails:
        return

    send_mail(
        subject=(
            f"Social Trigger: \"{trigger.keyword}\" fired on {platform}"
            f" ({event_type})"
        ),
        message=(
            f"{sender_name or 'Unknown sender'} triggered a social automation.\n\n"
            f"Platform: {platform}\n"
            f"Event type: {event_type}\n\n"
            f"Message/comment:\n\"{message_text}\"\n\n"
            f"Auto-reply was sent using trigger \"{trigger.keyword}\"."
        ),
        from_email=None,
        recipient_list=emails,
        fail_silently=True,
    )
