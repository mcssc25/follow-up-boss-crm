from django.db.models import Count

from apps.accounts.models import User


def round_robin_assign(team):
    """Assign to the agent with the fewest contacts."""
    agents = User.objects.filter(team=team, is_active=True)
    if not agents.exists():
        return None
    return agents.annotate(
        contact_count=Count('contacts')
    ).order_by('contact_count').first()
