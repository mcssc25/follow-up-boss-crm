from django.conf import settings
from django.db.models import Count

from apps.accounts.models import User


def round_robin_assign(team, track=None):
    """Assign to the active agent in `team` with the fewest contacts.

    If `track` is provided, restrict the candidate pool to usernames listed
    in settings.TRACK_AGENTS[track]. Returns None if no eligible agents exist.
    """
    agents = User.objects.filter(team=team, is_active=True)
    if track:
        track_usernames = getattr(settings, 'TRACK_AGENTS', {}).get(track, [])
        agents = agents.filter(username__in=track_usernames)
    if not agents.exists():
        return None
    return agents.annotate(
        contact_count=Count('contacts')
    ).order_by('contact_count').first()
