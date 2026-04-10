import json
import threading

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.campaigns.models import Campaign, CampaignEnrollment
from apps.contacts.models import Contact, ContactActivity, Tag

from apps.accounts.notifications import notify_new_lead, send_results_email

from .lead_routing import round_robin_assign
from .models import APIKey


def _cors_response(response):
    """Add CORS headers to a response."""
    response['Access-Control-Allow-Origin'] = '*'
    return response


@csrf_exempt
def capture_lead(request):
    """Public API endpoint for lead capture from landing pages."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = JsonResponse({}, status=200)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-Api-Key'
        return response

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # Auth via X-Api-Key header
    api_key = request.headers.get('X-Api-Key')
    try:
        key_obj = APIKey.objects.select_related('team').get(
            key=api_key, is_active=True
        )
    except APIKey.DoesNotExist:
        return _cors_response(JsonResponse({'error': 'Invalid API key'}, status=401))

    team = key_obj.team
    data = json.loads(request.body)

    # Build source_detail from UTM parameters
    source_detail = data.get('source_detail', '')
    utm_source = data.get('utm_source', '')
    utm_medium = data.get('utm_medium', '')
    utm_campaign = data.get('utm_campaign', '')
    utm_content = data.get('utm_content', '')
    utm_parts = []
    if utm_source:
        utm_parts.append(f"utm_source={utm_source}")
    if utm_medium:
        utm_parts.append(f"utm_medium={utm_medium}")
    if utm_campaign:
        utm_parts.append(f"utm_campaign={utm_campaign}")
    if utm_content:
        utm_parts.append(f"utm_content={utm_content}")
    if utm_parts:
        utm_string = ' | '.join(utm_parts)
        source_detail = f"{source_detail} | {utm_string}" if source_detail else utm_string

    # --- Feature 3: Duplicate Lead Detection ---
    email = data.get('email', '').strip()
    existing_contact = None
    if email:
        existing_contact = Contact.objects.filter(email__iexact=email, team=team).first()

    if existing_contact:
        # Update existing contact's info
        contact = existing_contact
        if data.get('first_name'):
            contact.first_name = data['first_name']
        if data.get('last_name'):
            contact.last_name = data['last_name']
        if data.get('phone'):
            contact.phone = data['phone']
        if source_detail:
            contact.source_detail = source_detail
        contact.save()

        # Log activity for the update
        ContactActivity.objects.create(
            contact=contact,
            activity_type='lead_captured',
            description=f"Returning lead updated from {data.get('source', 'landing_page')}",
        )
        status_label = 'updated'
    else:
        # Create new contact
        contact = Contact.objects.create(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=email,
            phone=data.get('phone', ''),
            source=data.get('source', 'landing_page'),
            source_detail=source_detail,
            team=team,
            assigned_to=round_robin_assign(team),
        )

        # Log activity
        ContactActivity.objects.create(
            contact=contact,
            activity_type='lead_captured',
            description=f"New lead captured from {contact.source}",
        )

        # Notify assigned agent (background so SMTP doesn't block response)
        threading.Thread(
            target=notify_new_lead, args=(contact,), daemon=True
        ).start()
        status_label = 'created'

    # --- Feature 1: Tag handling ---
    tag_names = data.get('tags', [])
    # Also add utm_source as a tag if present
    if utm_source and utm_source not in tag_names:
        tag_names.append(utm_source)

    for tag_name in tag_names:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        tag_obj, _ = Tag.objects.get_or_create(
            name__iexact=tag_name,
            team=team,
            defaults={'name': tag_name},
        )
        contact.tag_objects.add(tag_obj)
        # Also keep the JSON tags field in sync
        if tag_name not in contact.tags:
            contact.tags.append(tag_name)
    if tag_names:
        contact.save(update_fields=['tags'])

    # Send results email to the lead in background (don't block API response)
    results_url = data.get('results_url')
    if results_url:
        threading.Thread(
            target=send_results_email, args=(contact, results_url), daemon=True
        ).start()

    # Auto-enroll in campaign if specified
    campaign_id = data.get('campaign_id')
    if campaign_id:
        try:
            campaign = Campaign.objects.get(
                id=campaign_id, team=team, is_active=True
            )
            # Check not already actively enrolled
            already_enrolled = CampaignEnrollment.objects.filter(
                contact=contact,
                campaign=campaign,
                is_active=True,
                completed_at__isnull=True,
            ).exists()
            if not already_enrolled:
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

    response = JsonResponse(
        {
            'status': status_label,
            'contact_id': contact.id,
            'assigned_to': str(contact.assigned_to) if contact.assigned_to else None,
        },
        status=201 if status_label == 'created' else 200,
    )
    response['Access-Control-Allow-Origin'] = '*'
    return response
