"""Keyword matching engine for incoming social messages."""

from apps.social.models import KeywordTrigger


def find_matching_trigger(team, message_text, platform):
    """Find the first active KeywordTrigger that matches the message.

    Returns the matched KeywordTrigger or None.
    """
    triggers = KeywordTrigger.objects.filter(
        team=team,
        is_active=True,
    ).filter(
        platform__in=[platform, 'both'],
    )

    text_lower = message_text.lower()

    for trigger in triggers:
        keyword_lower = trigger.keyword.lower()

        if trigger.match_type == 'exact' and text_lower == keyword_lower:
            return trigger
        elif trigger.match_type == 'contains' and keyword_lower in text_lower:
            return trigger
        elif trigger.match_type == 'starts_with' and text_lower.startswith(keyword_lower):
            return trigger

    return None
