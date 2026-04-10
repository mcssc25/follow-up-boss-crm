"""Keyword matching engine for incoming social messages."""

from apps.social.models import KeywordTrigger


def find_matching_trigger(team, message_text, platform, event_type='message'):
    """Find the first active KeywordTrigger that matches the message.

    Returns the matched KeywordTrigger or None.
    """
    triggers = KeywordTrigger.objects.filter(
        team=team,
        is_active=True,
    ).filter(
        platform__in=[platform, 'both'],
        trigger_event__in=[event_type, 'both'],
    )

    normalized_text = ' '.join(message_text.lower().split())
    exact_matches = []
    starts_with_matches = []
    contains_matches = []

    for trigger in triggers:
        keyword_lower = ' '.join(trigger.keyword.lower().split())

        if trigger.match_type == 'exact' and normalized_text == keyword_lower:
            exact_matches.append(trigger)
        elif (
            trigger.match_type == 'starts_with'
            and normalized_text.startswith(keyword_lower)
        ):
            starts_with_matches.append(trigger)
        elif trigger.match_type == 'contains' and keyword_lower in normalized_text:
            contains_matches.append(trigger)

    for candidates in (exact_matches, starts_with_matches, contains_matches):
        if candidates:
            return max(candidates, key=lambda trigger: len(trigger.keyword.strip()))

    return None
