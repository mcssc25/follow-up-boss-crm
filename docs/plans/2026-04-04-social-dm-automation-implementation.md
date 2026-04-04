# Social DM Automation — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a keyword-triggered DM automation system for Instagram & Facebook that auto-replies and captures leads into the CRM — replacing ManyChat.

**Architecture:** New `apps/social/` Django app receives Meta webhooks via Celery, matches keywords, sends replies via Meta Send API, and creates/tags/enrolls contacts. Admin UI for managing triggers built with Tailwind + HTMX matching existing CRM patterns.

**Tech Stack:** Django, Celery, Meta Graph API v21.0, Tailwind CSS, HTMX, PostgreSQL

---

### Task 1: Create App Skeleton

**Files:**
- Create: `apps/social/__init__.py`
- Create: `apps/social/apps.py`
- Create: `apps/social/models.py`
- Create: `apps/social/views.py`
- Create: `apps/social/urls.py`
- Create: `apps/social/tasks.py`
- Create: `apps/social/meta_api.py`
- Create: `apps/social/admin.py`
- Create: `apps/social/tests/__init__.py`
- Create: `apps/social/tests/test_models.py`
- Create: `apps/social/tests/test_webhook.py`
- Create: `apps/social/tests/test_keyword_engine.py`
- Create: `apps/social/tests/test_views.py`
- Modify: `config/settings.py` (add to PROJECT_APPS)
- Modify: `config/urls.py` (add social urls)

**Step 1: Create the app directory and files**

`apps/social/apps.py`:
```python
from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.social'
    verbose_name = 'Social DM Automation'
```

`apps/social/__init__.py`: empty file

`apps/social/models.py`:
```python
from django.db import models
```

`apps/social/views.py`:
```python
from django.http import JsonResponse
```

`apps/social/urls.py`:
```python
from django.urls import path

app_name = 'social'

urlpatterns = []
```

`apps/social/tasks.py`:
```python
from celery import shared_task
```

`apps/social/meta_api.py`:
```python
"""Meta (Facebook/Instagram) Graph API client."""
```

`apps/social/admin.py`:
```python
from django.contrib import admin
```

`apps/social/tests/__init__.py`: empty file

**Step 2: Register the app in settings**

In `config/settings.py`, add `'apps.social'` to `PROJECT_APPS` list (after `'apps.email_tracker'`).

**Step 3: Add URL include**

In `config/urls.py`, add:
```python
path('social/', include('apps.social.urls')),
```

**Step 4: Commit**

```bash
git add apps/social/ config/settings.py config/urls.py
git commit -m "feat(social): scaffold social DM automation app"
```

---

### Task 2: Data Models

**Files:**
- Modify: `apps/social/models.py`
- Create: `apps/social/tests/test_models.py`

**Step 1: Write failing tests for models**

`apps/social/tests/test_models.py`:
```python
from django.test import TestCase

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign
from apps.contacts.models import Contact
from apps.social.models import KeywordTrigger, MessageLog, SocialAccount


class SocialAccountModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")

    def test_create_social_account(self):
        account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='12345',
            page_name='Test Page',
            access_token='token123',
        )
        self.assertEqual(str(account), "Test Page (instagram)")
        self.assertTrue(account.is_active)
        self.assertFalse(account.webhook_verified)

    def test_platform_choices(self):
        account = SocialAccount(platform='invalid')
        with self.assertRaises(Exception):
            account.full_clean()


class KeywordTriggerModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")

    def test_create_keyword_trigger(self):
        trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            reply_text='Thanks for your interest! Here is the guide.',
        )
        self.assertEqual(str(trigger), "Condos (both)")
        self.assertTrue(trigger.is_active)
        self.assertTrue(trigger.create_contact)

    def test_trigger_with_campaign(self):
        campaign = Campaign.objects.create(
            name="Condo Drip", team=self.team
        )
        trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Phoenix',
            reply_text='Check out Phoenix condos!',
            campaign=campaign,
        )
        self.assertEqual(trigger.campaign, campaign)

    def test_trigger_defaults(self):
        trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Test',
            reply_text='Reply',
        )
        self.assertEqual(trigger.match_type, 'contains')
        self.assertEqual(trigger.platform, 'both')
        self.assertTrue(trigger.create_contact)
        self.assertFalse(trigger.notify_agent)
        self.assertEqual(trigger.tags, [])


class MessageLogModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='12345',
            page_name='Test Page',
            access_token='token',
        )

    def test_create_message_log(self):
        log = MessageLog.objects.create(
            social_account=self.account,
            sender_id='ig_user_123',
            sender_name='Jane Smith',
            message_text='I want Condos',
            platform='instagram',
        )
        self.assertFalse(log.reply_sent)
        self.assertIsNone(log.trigger_matched)
        self.assertIsNone(log.contact_created)
```

**Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.social.tests.test_models -v 2`
Expected: ImportError (models don't exist yet)

**Step 3: Write the models**

`apps/social/models.py`:
```python
from django.db import models


class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
    ]

    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='social_accounts',
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    page_id = models.CharField(max_length=100)
    page_name = models.CharField(max_length=255)
    access_token = models.TextField(help_text='Encrypted Page Access Token')
    instagram_account_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Instagram Business Account ID (for IG-specific calls)',
    )
    is_active = models.BooleanField(default=True)
    webhook_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['team', 'page_id']

    def __str__(self):
        return f"{self.page_name} ({self.platform})"


class KeywordTrigger(models.Model):
    MATCH_TYPE_CHOICES = [
        ('exact', 'Exact Match'),
        ('contains', 'Contains'),
        ('starts_with', 'Starts With'),
    ]
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('both', 'Both'),
    ]

    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='keyword_triggers',
    )
    keyword = models.CharField(max_length=100)
    match_type = models.CharField(
        max_length=20, choices=MATCH_TYPE_CHOICES, default='contains',
    )
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, default='both',
    )
    is_active = models.BooleanField(default=True)
    reply_text = models.TextField(help_text='Auto-reply message body')
    reply_link = models.URLField(
        blank=True, default='',
        help_text='Optional link to include (PDF, video, landing page)',
    )
    tags = models.JSONField(default=list, blank=True)
    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='keyword_triggers',
    )
    create_contact = models.BooleanField(default=True)
    notify_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['keyword']

    def __str__(self):
        return f"{self.keyword} ({self.platform})"


class MessageLog(models.Model):
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender_id = models.CharField(max_length=100)
    sender_name = models.CharField(max_length=255, blank=True, default='')
    message_text = models.TextField()
    platform = models.CharField(max_length=20)
    trigger_matched = models.ForeignKey(
        KeywordTrigger,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs',
    )
    contact_created = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_messages',
    )
    reply_sent = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender_name}: {self.message_text[:50]}"
```

**Step 4: Create and run migration**

Run: `python manage.py makemigrations social`
Run: `python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `python manage.py test apps.social.tests.test_models -v 2`
Expected: All PASS

**Step 6: Commit**

```bash
git add apps/social/models.py apps/social/migrations/ apps/social/tests/test_models.py
git commit -m "feat(social): add SocialAccount, KeywordTrigger, MessageLog models"
```

---

### Task 3: Keyword Matching Engine

**Files:**
- Create: `apps/social/engine.py`
- Create: `apps/social/tests/test_keyword_engine.py`

**Step 1: Write failing tests**

`apps/social/tests/test_keyword_engine.py`:
```python
from django.test import TestCase

from apps.accounts.models import Team
from apps.social.engine import find_matching_trigger
from apps.social.models import KeywordTrigger


class KeywordMatchingTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.trigger_condos = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            reply_text='Here is the condo guide!',
        )
        self.trigger_phoenix = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Phoenix',
            match_type='exact',
            platform='instagram',
            reply_text='Check out Phoenix tours!',
        )
        self.trigger_hello = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Hi ',
            match_type='starts_with',
            platform='facebook',
            reply_text='Welcome!',
        )

    def test_contains_match(self):
        trigger = find_matching_trigger(
            self.team, 'I want Condos please', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_contains_case_insensitive(self):
        trigger = find_matching_trigger(
            self.team, 'show me condos', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_exact_match(self):
        trigger = find_matching_trigger(
            self.team, 'Phoenix', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_phoenix)

    def test_exact_no_partial(self):
        trigger = find_matching_trigger(
            self.team, 'Phoenix condos', 'instagram'
        )
        # "Phoenix" is exact match only, so this should NOT match phoenix
        # but "condos" contains match should fire
        self.assertEqual(trigger, self.trigger_condos)

    def test_starts_with_match(self):
        trigger = find_matching_trigger(
            self.team, 'Hi there!', 'facebook'
        )
        self.assertEqual(trigger, self.trigger_hello)

    def test_platform_filter_instagram(self):
        # "Hi " trigger is facebook-only, should not match on instagram
        trigger = find_matching_trigger(
            self.team, 'Hi there!', 'instagram'
        )
        self.assertIsNone(trigger)

    def test_platform_both_matches_any(self):
        trigger = find_matching_trigger(
            self.team, 'Show me condos', 'facebook'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_no_match(self):
        trigger = find_matching_trigger(
            self.team, 'What is the weather?', 'instagram'
        )
        self.assertIsNone(trigger)

    def test_inactive_trigger_skipped(self):
        self.trigger_condos.is_active = False
        self.trigger_condos.save()
        trigger = find_matching_trigger(
            self.team, 'I want condos', 'instagram'
        )
        self.assertIsNone(trigger)
```

**Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.social.tests.test_keyword_engine -v 2`
Expected: ImportError

**Step 3: Write the engine**

`apps/social/engine.py`:
```python
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
        # Platform: match specific or 'both'
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
```

**Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.social.tests.test_keyword_engine -v 2`
Expected: All PASS

**Step 5: Commit**

```bash
git add apps/social/engine.py apps/social/tests/test_keyword_engine.py
git commit -m "feat(social): add keyword matching engine with contains/exact/starts_with"
```

---

### Task 4: Meta API Client

**Files:**
- Modify: `apps/social/meta_api.py`

This task has no tests because it wraps external HTTP calls. We'll mock it in the webhook/task tests.

**Step 1: Write the Meta API client**

`apps/social/meta_api.py`:
```python
"""Meta (Facebook/Instagram) Graph API client."""

import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = 'https://graph.facebook.com/v21.0'


def verify_webhook_signature(request_body, signature_header):
    """Verify X-Hub-Signature-256 from Meta webhook payload.

    Returns True if signature is valid.
    """
    if not signature_header:
        return False

    app_secret = settings.META_APP_SECRET
    expected = 'sha256=' + hmac.new(
        app_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def send_message(page_access_token, recipient_id, text):
    """Send a text message via Meta Send API.

    Works for both Facebook Messenger and Instagram DMs.
    Returns dict with 'success' and optional 'error' keys.
    """
    url = f'{GRAPH_API_BASE}/me/messages'
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text},
        'messaging_type': 'RESPONSE',
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            params={'access_token': page_access_token},
            timeout=10,
        )
        if resp.status_code == 200:
            return {'success': True, 'message_id': resp.json().get('message_id')}
        else:
            error = resp.json().get('error', {}).get('message', resp.text)
            logger.error("Meta Send API error: %s", error)
            return {'success': False, 'error': error}
    except requests.RequestException as e:
        logger.exception("Meta Send API request failed")
        return {'success': False, 'error': str(e)}


def get_user_profile(page_access_token, user_id):
    """Fetch basic profile info for a user (name).

    Returns dict with 'name' key or empty dict on failure.
    """
    url = f'{GRAPH_API_BASE}/{user_id}'
    try:
        resp = requests.get(
            url,
            params={
                'fields': 'name',
                'access_token': page_access_token,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
    except requests.RequestException:
        logger.exception("Failed to fetch user profile for %s", user_id)
        return {}
```

**Step 2: Add Meta settings to config**

In `config/settings.py`, add near the bottom (after Celery settings):
```python
# Meta (Facebook/Instagram) API
META_APP_ID = os.getenv('META_APP_ID', '')
META_APP_SECRET = os.getenv('META_APP_SECRET', '')
META_WEBHOOK_VERIFY_TOKEN = os.getenv('META_WEBHOOK_VERIFY_TOKEN', 'crm-social-webhook-verify')
```

**Step 3: Commit**

```bash
git add apps/social/meta_api.py config/settings.py
git commit -m "feat(social): add Meta Graph API client for messaging and signature verification"
```

---

### Task 5: Webhook Endpoint (Verification + Message Receiver)

**Files:**
- Modify: `apps/social/views.py`
- Modify: `apps/social/urls.py`
- Create: `apps/social/tests/test_webhook.py`

**Step 1: Write failing tests**

`apps/social/tests/test_webhook.py`:
```python
import hashlib
import hmac
import json

from django.conf import settings
from django.test import TestCase, override_settings

from apps.accounts.models import Team
from apps.social.models import SocialAccount


@override_settings(
    META_APP_SECRET='test-secret',
    META_WEBHOOK_VERIFY_TOKEN='test-verify-token',
)
class WebhookVerificationTest(TestCase):
    """Test the GET webhook endpoint (Meta verification handshake)."""

    def test_verify_valid_token(self):
        response = self.client.get('/social/webhook/', {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'test-verify-token',
            'hub.challenge': '1234567890',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'1234567890')

    def test_verify_invalid_token(self):
        response = self.client.get('/social/webhook/', {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong-token',
            'hub.challenge': '1234567890',
        })
        self.assertEqual(response.status_code, 403)


@override_settings(META_APP_SECRET='test-secret')
class WebhookMessageTest(TestCase):
    """Test the POST webhook endpoint (incoming messages)."""

    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='page_123',
            page_name='Test Page',
            access_token='token',
            instagram_account_id='ig_123',
        )

    def _sign(self, body_bytes):
        sig = hmac.new(
            b'test-secret', body_bytes, hashlib.sha256
        ).hexdigest()
        return f'sha256={sig}'

    def test_valid_instagram_message(self):
        payload = {
            'object': 'instagram',
            'entry': [{
                'id': 'ig_123',
                'messaging': [{
                    'sender': {'id': 'user_456'},
                    'recipient': {'id': 'ig_123'},
                    'message': {'text': 'I want Condos'},
                }],
            }],
        }
        body = json.dumps(payload).encode()
        response = self.client.post(
            '/social/webhook/',
            body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(response.status_code, 200)

    def test_valid_facebook_message(self):
        payload = {
            'object': 'page',
            'entry': [{
                'id': 'page_123',
                'messaging': [{
                    'sender': {'id': 'user_789'},
                    'recipient': {'id': 'page_123'},
                    'message': {'text': 'Hello there'},
                }],
            }],
        }
        body = json.dumps(payload).encode()
        response = self.client.post(
            '/social/webhook/',
            body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_signature_rejected(self):
        payload = json.dumps({'object': 'instagram', 'entry': []}).encode()
        response = self.client.post(
            '/social/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid',
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_signature_rejected(self):
        payload = json.dumps({'object': 'instagram', 'entry': []}).encode()
        response = self.client.post(
            '/social/webhook/',
            payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
```

**Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.social.tests.test_webhook -v 2`
Expected: 404 (no URL configured)

**Step 3: Write the webhook view**

`apps/social/views.py`:
```python
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import SocialAccount
from .tasks import process_incoming_message

logger = logging.getLogger(__name__)


def _verify_signature(request_body, signature_header):
    """Verify X-Hub-Signature-256 from Meta."""
    if not signature_header:
        return False
    expected = 'sha256=' + hmac.new(
        settings.META_APP_SECRET.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@csrf_exempt
def webhook(request):
    """Meta webhook endpoint — handles verification (GET) and messages (POST)."""

    # GET: Meta verification handshake
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.META_WEBHOOK_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponseForbidden('Invalid verify token')

    # POST: Incoming message
    if request.method == 'POST':
        signature = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if not _verify_signature(request.body, signature):
            return HttpResponseForbidden('Invalid signature')

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        obj_type = data.get('object')  # 'instagram' or 'page'
        platform = 'instagram' if obj_type == 'instagram' else 'facebook'

        for entry in data.get('entry', []):
            page_id = entry.get('id', '')
            for messaging_event in entry.get('messaging', []):
                message = messaging_event.get('message', {})
                text = message.get('text', '')
                if not text:
                    continue  # Skip non-text events (reactions, read receipts, etc.)

                sender_id = messaging_event.get('sender', {}).get('id', '')

                # Dispatch to Celery
                process_incoming_message.delay(
                    page_id=page_id,
                    platform=platform,
                    sender_id=sender_id,
                    message_text=text,
                )

        # Always return 200 quickly — Meta retries on non-200
        return HttpResponse('EVENT_RECEIVED', status=200)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
```

**Step 4: Wire up URL**

`apps/social/urls.py`:
```python
from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),
]
```

**Step 5: Create a stub Celery task (so the import works)**

`apps/social/tasks.py`:
```python
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def process_incoming_message(page_id, platform, sender_id, message_text):
    """Process an incoming social DM — match keywords and execute actions.

    Stubbed — will be implemented in Task 6.
    """
    logger.info(
        "Received message: page=%s platform=%s sender=%s text=%s",
        page_id, platform, sender_id, message_text[:100],
    )
```

**Step 6: Run tests to verify they pass**

Run: `python manage.py test apps.social.tests.test_webhook -v 2`
Expected: All PASS

**Step 7: Commit**

```bash
git add apps/social/views.py apps/social/urls.py apps/social/tasks.py apps/social/tests/test_webhook.py
git commit -m "feat(social): add Meta webhook endpoint with signature verification"
```

---

### Task 6: Celery Task — Process Incoming Messages

**Files:**
- Modify: `apps/social/tasks.py`
- Create: `apps/social/tests/test_tasks.py`

**Step 1: Write failing tests**

`apps/social/tests/test_tasks.py`:
```python
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign
from apps.contacts.models import Contact, ContactActivity
from apps.social.models import KeywordTrigger, MessageLog, SocialAccount
from apps.social.tasks import process_incoming_message


class ProcessIncomingMessageTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.agent = User.objects.create_user(
            username="kelly", password="pass", team=self.team
        )
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='page_123',
            page_name='Kelly Realty',
            access_token='token123',
            instagram_account_id='ig_123',
        )
        self.trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            reply_text='Here is the condo guide!',
            reply_link='https://example.com/guide.pdf',
            tags=['condos', 'interested'],
            create_contact=True,
        )

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_keyword_match_creates_contact_and_replies(
        self, mock_profile, mock_send
    ):
        mock_profile.return_value = {'name': 'Jane Smith'}
        mock_send.return_value = {'success': True}

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_456',
            message_text='I want Condos',
        )

        # Contact created
        contact = Contact.objects.get(
            custom_fields__instagram_id='user_456',
        )
        self.assertEqual(contact.first_name, 'Jane')
        self.assertEqual(contact.last_name, 'Smith')
        self.assertIn('condos', contact.tags)

        # Message logged
        log = MessageLog.objects.get(sender_id='user_456')
        self.assertEqual(log.trigger_matched, self.trigger)
        self.assertTrue(log.reply_sent)
        self.assertEqual(log.contact_created, contact)

        # Reply sent with link appended
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertIn('condo guide', call_args[1]['text'])
        self.assertIn('https://example.com/guide.pdf', call_args[1]['text'])

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_no_match_logs_without_reply(self, mock_profile, mock_send):
        mock_profile.return_value = {'name': 'John Doe'}

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_789',
            message_text='What is the weather?',
        )

        # Message logged but no trigger
        log = MessageLog.objects.get(sender_id='user_789')
        self.assertIsNone(log.trigger_matched)
        self.assertFalse(log.reply_sent)

        # No reply sent
        mock_send.assert_not_called()

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_existing_contact_updated_not_duplicated(
        self, mock_profile, mock_send
    ):
        mock_profile.return_value = {'name': 'Jane Smith'}
        mock_send.return_value = {'success': True}

        # Pre-existing contact from same sender
        Contact.objects.create(
            first_name='Jane',
            last_name='Smith',
            team=self.team,
            custom_fields={'instagram_id': 'user_456'},
        )

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_456',
            message_text='Show me Condos again',
        )

        # Should not create a duplicate
        self.assertEqual(
            Contact.objects.filter(
                custom_fields__instagram_id='user_456'
            ).count(),
            1,
        )

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_campaign_enrollment(self, mock_profile, mock_send):
        mock_profile.return_value = {'name': 'Bob Jones'}
        mock_send.return_value = {'success': True}

        campaign = Campaign.objects.create(
            name="Condo Drip", team=self.team
        )
        self.trigger.campaign = campaign
        self.trigger.save()

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_enroll',
            message_text='I love Condos!',
        )

        contact = Contact.objects.get(
            custom_fields__instagram_id='user_enroll',
        )
        self.assertTrue(
            campaign.enrollments.filter(contact=contact, is_active=True).exists()
        )
```

**Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.social.tests.test_tasks -v 2`
Expected: FAIL (task is still a stub)

**Step 3: Implement the task**

`apps/social/tasks.py`:
```python
import logging

from celery import shared_task
from django.db.models import Q

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
        if trigger.campaign and contact and contact.email:
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
```

**Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.social.tests.test_tasks -v 2`
Expected: All PASS

**Step 5: Commit**

```bash
git add apps/social/tasks.py apps/social/tests/test_tasks.py
git commit -m "feat(social): implement message processing task with keyword matching and CRM actions"
```

---

### Task 7: Admin UI — Keyword Triggers List + CRUD

**Files:**
- Modify: `apps/social/views.py`
- Modify: `apps/social/urls.py`
- Create: `apps/social/forms.py`
- Create: `templates/social/trigger_list.html`
- Create: `templates/social/trigger_form.html`

**Step 1: Create the form**

`apps/social/forms.py`:
```python
from django import forms

from apps.campaigns.models import Campaign

from .models import KeywordTrigger


class KeywordTriggerForm(forms.ModelForm):
    class Meta:
        model = KeywordTrigger
        fields = [
            'keyword', 'match_type', 'platform', 'is_active',
            'reply_text', 'reply_link',
            'tags', 'campaign', 'create_contact', 'notify_agent',
        ]
        widgets = {
            'keyword': forms.TextInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'e.g. Condos',
            }),
            'match_type': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'platform': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'reply_text': forms.Textarea(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'The auto-reply message...',
            }),
            'reply_link': forms.URLInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'https://example.com/guide.pdf',
            }),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        if team:
            self.fields['campaign'].queryset = Campaign.objects.filter(
                team=team, is_active=True,
            )
        self.fields['campaign'].required = False
        self.fields['campaign'].empty_label = '— No campaign —'
```

**Step 2: Add the list and CRUD views**

Add to `apps/social/views.py` (below the webhook view):
```python
from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import KeywordTriggerForm
from .models import KeywordTrigger, MessageLog, SocialAccount


class TriggerListView(LoginRequiredMixin, ListView):
    model = KeywordTrigger
    template_name = 'social/trigger_list.html'
    context_object_name = 'triggers'

    def get_queryset(self):
        return KeywordTrigger.objects.filter(
            team=self.request.user.team,
        ).select_related('campaign')


class TriggerCreateView(LoginRequiredMixin, CreateView):
    model = KeywordTrigger
    form_class = KeywordTriggerForm
    template_name = 'social/trigger_form.html'
    success_url = reverse_lazy('social:trigger_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        django_messages.success(self.request, 'Keyword trigger created.')
        return super().form_valid(form)


class TriggerUpdateView(LoginRequiredMixin, UpdateView):
    model = KeywordTrigger
    form_class = KeywordTriggerForm
    template_name = 'social/trigger_form.html'
    success_url = reverse_lazy('social:trigger_list')

    def get_queryset(self):
        return KeywordTrigger.objects.filter(team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        django_messages.success(self.request, 'Keyword trigger updated.')
        return super().form_valid(form)


class TriggerDeleteView(LoginRequiredMixin, DeleteView):
    model = KeywordTrigger
    success_url = reverse_lazy('social:trigger_list')

    def get_queryset(self):
        return KeywordTrigger.objects.filter(team=self.request.user.team)

    def delete(self, request, *args, **kwargs):
        django_messages.success(request, 'Keyword trigger deleted.')
        return super().delete(request, *args, **kwargs)
```

**Step 3: Update URLs**

`apps/social/urls.py`:
```python
from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    # Meta webhook (public)
    path('webhook/', views.webhook, name='webhook'),

    # Keyword triggers (authenticated)
    path('triggers/', views.TriggerListView.as_view(), name='trigger_list'),
    path('triggers/new/', views.TriggerCreateView.as_view(), name='trigger_create'),
    path('triggers/<int:pk>/edit/', views.TriggerUpdateView.as_view(), name='trigger_update'),
    path('triggers/<int:pk>/delete/', views.TriggerDeleteView.as_view(), name='trigger_delete'),
]
```

**Step 4: Create trigger list template**

`templates/social/trigger_list.html`:
```django
{% extends "base.html" %}

{% block title %}Keyword Triggers — Social DM{% endblock %}

{% block content %}
<div class="max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Keyword Triggers</h1>
            <p class="mt-1 text-sm text-gray-500">Auto-reply to Instagram & Facebook DMs based on keywords</p>
        </div>
        <a href="{% url 'social:trigger_create' %}"
           class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 shadow-sm">
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            New Trigger
        </a>
    </div>

    {% if triggers %}
    <div class="bg-white shadow-sm border border-gray-200 rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keyword</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Match</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Platform</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reply Preview</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
                {% for trigger in triggers %}
                <tr class="{% cycle 'bg-white' 'bg-gray-50' %} hover:bg-indigo-50">
                    <td class="px-4 py-3 font-medium text-gray-900">{{ trigger.keyword }}</td>
                    <td class="px-4 py-3 text-sm text-gray-500">{{ trigger.get_match_type_display }}</td>
                    <td class="px-4 py-3 text-sm">
                        {% if trigger.platform == 'instagram' %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-pink-100 text-pink-800">Instagram</span>
                        {% elif trigger.platform == 'facebook' %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">Facebook</span>
                        {% else %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">Both</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">{{ trigger.reply_text|truncatewords:15 }}</td>
                    <td class="px-4 py-3 text-sm text-gray-500">
                        {% if trigger.campaign %}{{ trigger.campaign.name }}{% else %}—{% endif %}
                    </td>
                    <td class="px-4 py-3">
                        {% if trigger.is_active %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Active</span>
                        {% else %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">Inactive</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3 text-right text-sm space-x-2">
                        <a href="{% url 'social:trigger_update' trigger.pk %}" class="text-indigo-600 hover:text-indigo-900">Edit</a>
                        <form method="post" action="{% url 'social:trigger_delete' trigger.pk %}" class="inline"
                              onsubmit="return confirm('Delete this trigger?')">
                            {% csrf_token %}
                            <button type="submit" class="text-red-600 hover:text-red-900">Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-12 text-center">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No keyword triggers</h3>
        <p class="mt-1 text-sm text-gray-500">Create your first trigger to start auto-replying to DMs.</p>
        <div class="mt-6">
            <a href="{% url 'social:trigger_create' %}"
               class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">
                New Trigger
            </a>
        </div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 5: Create trigger form template**

`templates/social/trigger_form.html`:
```django
{% extends "base.html" %}

{% block title %}{% if form.instance.pk %}Edit{% else %}New{% endif %} Keyword Trigger{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="mb-6">
        <a href="{% url 'social:trigger_list' %}" class="text-sm text-indigo-600 hover:text-indigo-900">
            &larr; Back to Triggers
        </a>
        <h1 class="mt-2 text-2xl font-bold text-gray-900">
            {% if form.instance.pk %}Edit Trigger{% else %}New Keyword Trigger{% endif %}
        </h1>
    </div>

    <form method="post" class="space-y-6">
        {% csrf_token %}

        <!-- Keyword & Matching -->
        <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Keyword Trigger</h2>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Keyword</label>
                    {{ form.keyword }}
                    {% if form.keyword.errors %}<p class="mt-1 text-sm text-red-600">{{ form.keyword.errors.0 }}</p>{% endif %}
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Match Type</label>
                    {{ form.match_type }}
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Platform</label>
                    {{ form.platform }}
                </div>
                <div class="flex items-end">
                    <label class="inline-flex items-center">
                        {{ form.is_active }}
                        <span class="ml-2 text-sm text-gray-700">Active</span>
                    </label>
                </div>
            </div>
        </div>

        <!-- Auto-Reply -->
        <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Auto-Reply</h2>
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Reply Message</label>
                    {{ form.reply_text }}
                    {% if form.reply_text.errors %}<p class="mt-1 text-sm text-red-600">{{ form.reply_text.errors.0 }}</p>{% endif %}
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Link (optional)</label>
                    {{ form.reply_link }}
                    <p class="mt-1 text-xs text-gray-500">PDF, video page, or landing page URL</p>
                </div>
            </div>
        </div>

        <!-- CRM Actions -->
        <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">CRM Actions</h2>
            <div class="space-y-4">
                <label class="inline-flex items-center">
                    {{ form.create_contact }}
                    <span class="ml-2 text-sm text-gray-700">Add sender to CRM as a contact</span>
                </label>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Enroll in Campaign</label>
                    {{ form.campaign }}
                </div>
                <label class="inline-flex items-center">
                    {{ form.notify_agent }}
                    <span class="ml-2 text-sm text-gray-700">Notify me when this trigger fires</span>
                </label>
            </div>
        </div>

        <div class="flex justify-end space-x-3">
            <a href="{% url 'social:trigger_list' %}"
               class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
                Cancel
            </a>
            <button type="submit"
                    class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 shadow-sm">
                {% if form.instance.pk %}Save Changes{% else %}Create Trigger{% endif %}
            </button>
        </div>
    </form>
</div>
{% endblock %}
```

**Step 6: Commit**

```bash
git add apps/social/forms.py apps/social/views.py apps/social/urls.py templates/social/
git commit -m "feat(social): add keyword trigger CRUD views and templates"
```

---

### Task 8: Admin UI — Message Log

**Files:**
- Modify: `apps/social/views.py`
- Modify: `apps/social/urls.py`
- Create: `templates/social/message_log.html`

**Step 1: Add message log view**

Add to `apps/social/views.py`:
```python
class MessageLogView(LoginRequiredMixin, ListView):
    model = MessageLog
    template_name = 'social/message_log.html'
    context_object_name = 'messages'
    paginate_by = 50

    def get_queryset(self):
        qs = MessageLog.objects.filter(
            social_account__team=self.request.user.team,
        ).select_related('trigger_matched', 'contact_created')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(sender_name__icontains=q)
                | Q(message_text__icontains=q)
            )

        platform = self.request.GET.get('platform', '').strip()
        if platform:
            qs = qs.filter(platform=platform)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_platform'] = self.request.GET.get('platform', '')
        return ctx
```

**Step 2: Add URL**

Add to `apps/social/urls.py`:
```python
path('messages/', views.MessageLogView.as_view(), name='message_log'),
```

**Step 3: Create template**

`templates/social/message_log.html`:
```django
{% extends "base.html" %}

{% block title %}Message Log — Social DM{% endblock %}

{% block content %}
<div class="max-w-6xl mx-auto">
    <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">Message Log</h1>
        <p class="mt-1 text-sm text-gray-500">All incoming DMs from Instagram & Facebook</p>
    </div>

    <!-- Search/Filter -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <form method="get" class="flex flex-wrap items-end gap-4">
            <div class="flex-1 min-w-[200px]">
                <label class="block text-xs font-medium text-gray-500 mb-1">Search</label>
                <input type="text" name="q" value="{{ search_query }}"
                       placeholder="Name or message..."
                       class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Platform</label>
                <select name="platform" class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                    <option value="">All</option>
                    <option value="instagram" {% if selected_platform == 'instagram' %}selected{% endif %}>Instagram</option>
                    <option value="facebook" {% if selected_platform == 'facebook' %}selected{% endif %}>Facebook</option>
                </select>
            </div>
            <button type="submit" class="inline-flex items-center px-4 py-2 bg-gray-800 text-white text-sm font-medium rounded-md hover:bg-gray-700">
                Filter
            </button>
        </form>
    </div>

    {% if messages %}
    <div class="bg-white shadow-sm border border-gray-200 rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sender</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Platform</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trigger</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reply</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
                {% for msg in messages %}
                <tr class="{% cycle 'bg-white' 'bg-gray-50' %} hover:bg-indigo-50">
                    <td class="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                        {{ msg.timestamp|date:"M d, g:i A" }}
                    </td>
                    <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ msg.sender_name|default:"Unknown" }}</td>
                    <td class="px-4 py-3 text-sm">
                        {% if msg.platform == 'instagram' %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-pink-100 text-pink-800">IG</span>
                        {% else %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">FB</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700 max-w-xs truncate">{{ msg.message_text|truncatewords:20 }}</td>
                    <td class="px-4 py-3 text-sm">
                        {% if msg.trigger_matched %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            {{ msg.trigger_matched.keyword }}
                        </span>
                        {% else %}
                        <span class="text-gray-400">—</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3 text-sm">
                        {% if msg.contact_created %}
                        <a href="{% url 'contacts:detail' msg.contact_created.pk %}" class="text-indigo-600 hover:text-indigo-900">
                            {{ msg.contact_created }}
                        </a>
                        {% else %}
                        <span class="text-gray-400">—</span>
                        {% endif %}
                    </td>
                    <td class="px-4 py-3 text-sm">
                        {% if msg.reply_sent %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Sent</span>
                        {% else %}
                        <span class="text-gray-400">—</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Pagination -->
    {% if is_paginated %}
    <nav class="mt-6 flex items-center justify-between">
        <p class="text-sm text-gray-700">
            Showing {{ page_obj.start_index }}-{{ page_obj.end_index }} of {{ page_obj.paginator.count }}
        </p>
        <div class="flex space-x-2">
            {% if page_obj.has_previous %}
            <a href="?page={{ page_obj.previous_page_number }}&q={{ search_query }}&platform={{ selected_platform }}"
               class="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">Previous</a>
            {% endif %}
            {% if page_obj.has_next %}
            <a href="?page={{ page_obj.next_page_number }}&q={{ search_query }}&platform={{ selected_platform }}"
               class="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">Next</a>
            {% endif %}
        </div>
    </nav>
    {% endif %}

    {% else %}
    <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-12 text-center">
        <p class="text-sm text-gray-500">No messages received yet.</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 4: Commit**

```bash
git add apps/social/views.py apps/social/urls.py templates/social/message_log.html
git commit -m "feat(social): add message log view with search and filtering"
```

---

### Task 9: Social Accounts Management Page

**Files:**
- Modify: `apps/social/views.py`
- Modify: `apps/social/urls.py`
- Create: `templates/social/accounts.html`

**Step 1: Add views for social accounts page and Meta OAuth callback**

Add to `apps/social/views.py`:
```python
import urllib.parse

from django.contrib.auth.decorators import login_required


@login_required
def social_accounts(request):
    """List connected social accounts and provide connect buttons."""
    accounts = SocialAccount.objects.filter(team=request.user.team)
    meta_app_id = settings.META_APP_ID

    # Build OAuth URL for Meta login
    redirect_uri = request.build_absolute_uri('/social/oauth/callback/')
    oauth_url = (
        f"https://www.facebook.com/v21.0/dialog/oauth"
        f"?client_id={meta_app_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope=pages_messaging,instagram_messaging,pages_manage_metadata,pages_show_list"
        f"&response_type=code"
    )

    return render(request, 'social/accounts.html', {
        'accounts': accounts,
        'oauth_url': oauth_url,
    })


@login_required
def oauth_callback(request):
    """Handle Meta OAuth callback — exchange code for page access tokens."""
    import requests as http_requests

    code = request.GET.get('code')
    if not code:
        django_messages.error(request, 'OAuth failed — no code received.')
        return redirect('social:accounts')

    redirect_uri = request.build_absolute_uri('/social/oauth/callback/')
    team = request.user.team

    # Exchange code for user access token
    token_resp = http_requests.get(
        'https://graph.facebook.com/v21.0/oauth/access_token',
        params={
            'client_id': settings.META_APP_ID,
            'client_secret': settings.META_APP_SECRET,
            'redirect_uri': redirect_uri,
            'code': code,
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        logger.error("Meta token exchange failed: %s", token_resp.text)
        django_messages.error(request, 'Failed to connect to Meta.')
        return redirect('social:accounts')

    user_token = token_resp.json().get('access_token')

    # Get pages the user manages
    pages_resp = http_requests.get(
        'https://graph.facebook.com/v21.0/me/accounts',
        params={'access_token': user_token},
        timeout=10,
    )
    if pages_resp.status_code != 200:
        django_messages.error(request, 'Failed to retrieve pages.')
        return redirect('social:accounts')

    pages = pages_resp.json().get('data', [])
    created_count = 0

    for page in pages:
        page_token = page['access_token']
        page_id = page['id']
        page_name = page['name']

        # Save Facebook page
        SocialAccount.objects.update_or_create(
            team=team,
            page_id=page_id,
            defaults={
                'platform': 'facebook',
                'page_name': page_name,
                'access_token': page_token,
                'is_active': True,
            },
        )
        created_count += 1

        # Check for connected Instagram Business account
        ig_resp = http_requests.get(
            f'https://graph.facebook.com/v21.0/{page_id}',
            params={
                'fields': 'instagram_business_account',
                'access_token': page_token,
            },
            timeout=10,
        )
        if ig_resp.status_code == 200:
            ig_data = ig_resp.json().get('instagram_business_account', {})
            ig_id = ig_data.get('id')
            if ig_id:
                SocialAccount.objects.update_or_create(
                    team=team,
                    page_id=ig_id,
                    defaults={
                        'platform': 'instagram',
                        'page_name': f"{page_name} (Instagram)",
                        'access_token': page_token,
                        'instagram_account_id': ig_id,
                        'is_active': True,
                    },
                )
                created_count += 1

    django_messages.success(request, f'Connected {created_count} account(s) from Meta.')
    return redirect('social:accounts')


@login_required
def disconnect_account(request, pk):
    """Disconnect (deactivate) a social account."""
    if request.method == 'POST':
        account = get_object_or_404(
            SocialAccount, pk=pk, team=request.user.team,
        )
        account.is_active = False
        account.save(update_fields=['is_active'])
        django_messages.success(request, f'Disconnected {account.page_name}.')
    return redirect('social:accounts')
```

**Step 2: Add URLs**

Add to `apps/social/urls.py`:
```python
# Social accounts
path('accounts/', views.social_accounts, name='accounts'),
path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
path('accounts/<int:pk>/disconnect/', views.disconnect_account, name='disconnect_account'),
```

**Step 3: Create template**

`templates/social/accounts.html`:
```django
{% extends "base.html" %}

{% block title %}Social Accounts{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Social Accounts</h1>
            <p class="mt-1 text-sm text-gray-500">Connect your Instagram and Facebook pages for DM automation</p>
        </div>
        <a href="{{ oauth_url }}"
           class="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 shadow-sm">
            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/>
            </svg>
            Connect Meta Account
        </a>
    </div>

    {% if accounts %}
    <div class="space-y-4">
        {% for account in accounts %}
        <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-6 flex items-center justify-between">
            <div class="flex items-center space-x-4">
                {% if account.platform == 'instagram' %}
                <div class="w-10 h-10 bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                    </svg>
                </div>
                {% else %}
                <div class="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                    <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/>
                    </svg>
                </div>
                {% endif %}
                <div>
                    <h3 class="text-sm font-medium text-gray-900">{{ account.page_name }}</h3>
                    <p class="text-xs text-gray-500">{{ account.get_platform_display }} &middot; ID: {{ account.page_id }}</p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                {% if account.is_active %}
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Connected</span>
                {% else %}
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">Disconnected</span>
                {% endif %}
                {% if account.is_active %}
                <form method="post" action="{% url 'social:disconnect_account' account.pk %}"
                      onsubmit="return confirm('Disconnect this account?')">
                    {% csrf_token %}
                    <button type="submit" class="text-sm text-red-600 hover:text-red-900">Disconnect</button>
                </form>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="bg-white shadow-sm border border-gray-200 rounded-lg p-12 text-center">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No accounts connected</h3>
        <p class="mt-1 text-sm text-gray-500">Connect your Meta account to start receiving DMs.</p>
        <div class="mt-6">
            <a href="{{ oauth_url }}"
               class="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700">
                Connect Meta Account
            </a>
        </div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 4: Commit**

```bash
git add apps/social/views.py apps/social/urls.py templates/social/accounts.html
git commit -m "feat(social): add social accounts page with Meta OAuth connect/disconnect"
```

---

### Task 10: Add Navigation Links

**Files:**
- Modify: `templates/base.html` (add Social DM nav items to sidebar)

**Step 1: Find the nav section in base.html and add social links**

Add a new section to the sidebar navigation (after existing nav items like Campaigns, Tasks, etc.):

```django
<!-- Social DM -->
<div class="px-3 mt-6">
    <h3 class="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Social DM</h3>
    <div class="mt-2 space-y-1">
        <a href="{% url 'social:trigger_list' %}"
           class="group flex items-center px-3 py-2 text-sm font-medium rounded-md {% if request.resolver_match.app_name == 'social' and 'trigger' in request.resolver_match.url_name %}bg-gray-200 text-gray-900{% else %}text-gray-600 hover:bg-gray-50{% endif %}">
            Keyword Triggers
        </a>
        <a href="{% url 'social:message_log' %}"
           class="group flex items-center px-3 py-2 text-sm font-medium rounded-md {% if request.resolver_match.app_name == 'social' and request.resolver_match.url_name == 'message_log' %}bg-gray-200 text-gray-900{% else %}text-gray-600 hover:bg-gray-50{% endif %}">
            Message Log
        </a>
        <a href="{% url 'social:accounts' %}"
           class="group flex items-center px-3 py-2 text-sm font-medium rounded-md {% if request.resolver_match.app_name == 'social' and request.resolver_match.url_name == 'accounts' %}bg-gray-200 text-gray-900{% else %}text-gray-600 hover:bg-gray-50{% endif %}">
            Connected Accounts
        </a>
    </div>
</div>
```

**Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat(social): add Social DM section to sidebar navigation"
```

---

### Task 11: Environment Variables & Deployment

**Files:**
- Modify: `docker-compose.prod.yml` (add META env vars)

**Step 1: Add Meta environment variables to docker-compose**

Add to the `web` service environment:
```yaml
META_APP_ID: ${META_APP_ID}
META_APP_SECRET: ${META_APP_SECRET}
META_WEBHOOK_VERIFY_TOKEN: ${META_WEBHOOK_VERIFY_TOKEN}
```

**Step 2: Add `requests` to requirements if not already present**

Check `requirements.txt` for `requests`. If missing, add it.

**Step 3: Run migrations on server**

```bash
python manage.py makemigrations social
python manage.py migrate
```

**Step 4: Commit**

```bash
git add docker-compose.prod.yml requirements.txt
git commit -m "feat(social): add Meta API env vars to production config"
```

---

### Task 12: End-to-End Manual Test Checklist

This is not code — it's a verification checklist after deployment:

1. **Meta Developer Portal:**
   - [ ] Create Meta App at developers.facebook.com
   - [ ] Add "Messenger" and "Instagram" products
   - [ ] Configure webhook URL: `https://crm.bigbeachal.com/social/webhook/`
   - [ ] Set verify token to match `META_WEBHOOK_VERIFY_TOKEN` env var
   - [ ] Subscribe to `messages` webhook field

2. **CRM Social Accounts page:**
   - [ ] Click "Connect Meta Account" and complete OAuth
   - [ ] Verify Facebook page and Instagram account appear as connected

3. **Keyword Triggers:**
   - [ ] Create a trigger: keyword="Condos", contains, both platforms, with reply text and a PDF link
   - [ ] Verify it appears in the list as Active

4. **Test DM (Dev Mode — use a test account added as app tester):**
   - [ ] Send a DM containing "Condos" to Kelly's Instagram
   - [ ] Verify auto-reply received with text + link
   - [ ] Check Message Log shows the message with trigger matched
   - [ ] Check Contacts page shows new contact created with instagram_id in custom_fields

5. **Meta App Review:**
   - [ ] Record screencast showing the feature working
   - [ ] Write privacy policy page
   - [ ] Submit for review requesting `pages_messaging` + `instagram_messaging`

---

**Plan complete and saved to `docs/plans/2026-04-04-social-dm-automation-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open a new session with executing-plans, batch execution with checkpoints

**Which approach?**
