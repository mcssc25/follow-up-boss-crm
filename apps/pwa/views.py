import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render

from .models import PushSubscription


def offline_view(request):
    """Serve the offline fallback page."""
    return render(request, 'pwa/offline.html')


@login_required
def vapid_public_key(request):
    """Return the VAPID public key for push subscription."""
    return JsonResponse({
        'public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    })


@login_required
@require_POST
def subscribe(request):
    """Save a push subscription for the current user."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    subscription = data.get('subscription')
    if not subscription:
        return JsonResponse({'error': 'Missing subscription'}, status=400)

    # Avoid duplicates — match on endpoint
    endpoint = subscription.get('endpoint', '')
    PushSubscription.objects.filter(
        user=request.user,
        subscription_json__endpoint=endpoint,
    ).delete()

    PushSubscription.objects.create(
        user=request.user,
        subscription_json=subscription,
    )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def unsubscribe(request):
    """Remove a push subscription for the current user."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint', '')
    deleted, _ = PushSubscription.objects.filter(
        user=request.user,
        subscription_json__endpoint=endpoint,
    ).delete()
    return JsonResponse({'ok': True, 'deleted': deleted})
