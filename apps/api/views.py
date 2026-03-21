import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.campaigns.models import Campaign, CampaignEnrollment
from apps.contacts.models import Contact, ContactActivity

from apps.accounts.notifications import notify_new_lead

from .lead_routing import round_robin_assign
from .models import APIKey


@csrf_exempt
@require_POST
def capture_lead(request):
    """Public API endpoint for lead capture from landing pages."""
    # Auth via X-Api-Key header
    api_key = request.headers.get('X-Api-Key')
    try:
        key_obj = APIKey.objects.select_related('team').get(
            key=api_key, is_active=True
        )
    except APIKey.DoesNotExist:
        return JsonResponse({'error': 'Invalid API key'}, status=401)

    team = key_obj.team
    data = json.loads(request.body)

    # Create contact
    contact = Contact.objects.create(
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        source=data.get('source', 'landing_page'),
        source_detail=data.get('utm_source', ''),
        team=team,
        assigned_to=round_robin_assign(team),
    )

    # Log activity
    ContactActivity.objects.create(
        contact=contact,
        activity_type='campaign_enrolled',
        description=f"New lead captured from {contact.source}",
    )

    # Notify assigned agent
    notify_new_lead(contact)

    # Auto-enroll in campaign if specified
    campaign_id = data.get('campaign_id')
    if campaign_id:
        try:
            campaign = Campaign.objects.get(
                id=campaign_id, team=team, is_active=True
            )
            first_step = campaign.steps.first()
            if first_step:
                CampaignEnrollment.objects.create(
                    contact=contact,
                    campaign=campaign,
                    current_step=first_step,
                    next_send_at=timezone.now(),
                )
        except Campaign.DoesNotExist:
            pass

    return JsonResponse(
        {
            'status': 'created',
            'contact_id': contact.id,
            'assigned_to': str(contact.assigned_to) if contact.assigned_to else None,
        },
        status=201,
    )
