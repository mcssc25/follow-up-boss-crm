# PWA Implementation Plan for BigBeach CRM

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Progressive Web App capabilities (installability, offline caching, push notifications) to the existing Django CRM.

**Architecture:** Add a `manifest.json` and service worker as static files, a new `apps/pwa` Django app for push subscription management, and wire notifications into existing Celery tasks. Template changes are minimal — just meta tags and a small JS registration block in `base.html`.

**Tech Stack:** Web Push API, VAPID keys, `pywebpush` Python package, vanilla JS service worker, existing Celery infrastructure.

---

### Task 1: Create Web App Manifest and Placeholder Icons

**Files:**
- Create: `static/manifest.json`
- Create: `static/icons/icon-192.svg`
- Create: `static/icons/icon-512.svg`

**Step 1: Create the icon directory**

```bash
mkdir -p static/icons
```

**Step 2: Create SVG placeholder icons**

Create `static/icons/icon-192.svg` — a simple indigo square with "BC" text:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="24" fill="#4f46e5"/>
  <text x="96" y="110" font-family="Georgia, serif" font-size="72" font-weight="bold" fill="white" text-anchor="middle">BC</text>
</svg>
```

Create `static/icons/icon-512.svg` — same design, 512px:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="64" fill="#4f46e5"/>
  <text x="256" y="296" font-family="Georgia, serif" font-size="192" font-weight="bold" fill="white" text-anchor="middle">BC</text>
</svg>
```

**Step 3: Create manifest.json**

Create `static/manifest.json`:

```json
{
  "name": "BigBeach CRM",
  "short_name": "CRM",
  "description": "BigBeach AL Customer Relationship Manager",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f3f4f6",
  "theme_color": "#4f46e5",
  "orientation": "any",
  "icons": [
    {
      "src": "/static/icons/icon-192.svg",
      "sizes": "192x192",
      "type": "image/svg+xml",
      "purpose": "any"
    },
    {
      "src": "/static/icons/icon-512.svg",
      "sizes": "512x512",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}
```

**Step 4: Commit**

```bash
git add static/manifest.json static/icons/
git commit -m "feat(pwa): add web app manifest and placeholder icons"
```

---

### Task 2: Create the Service Worker

**Files:**
- Create: `static/sw.js`
- Create: `templates/pwa/offline.html`

**Step 1: Create the service worker**

Create `static/sw.js`:

```javascript
const CACHE_NAME = 'bigbeach-crm-v1';
const OFFLINE_URL = '/pwa/offline/';

// Pre-cache on install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([OFFLINE_URL]);
    })
  );
  self.skipWaiting();
});

// Clean old caches on activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip admin, API, and auth URLs
  const url = new URL(request.url);
  if (url.pathname.startsWith('/admin/') ||
      url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/accounts/')) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML pages: network-first, fallback to cache, then offline page
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then((cached) => {
            return cached || caches.match(OFFLINE_URL);
          });
        })
    );
    return;
  }
});

// Push notification handler
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'BigBeach CRM';
  const options = {
    body: data.body || '',
    icon: '/static/icons/icon-192.svg',
    badge: '/static/icons/icon-192.svg',
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
```

**Step 2: Create offline fallback template**

Create `templates/pwa/offline.html`:

```html
{% extends "base.html" %}
{% block title %}Offline — BigBeach CRM{% endblock %}
{% block unauthenticated_content %}
<div class="min-h-screen flex items-center justify-center bg-gray-100">
  <div class="text-center p-8">
    <div class="w-16 h-16 mx-auto mb-4 text-gray-400">
      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 11-12.728 0M12 9v4m0 4h.01"/></svg>
    </div>
    <h1 class="text-2xl font-bold text-gray-800 mb-2">You're Offline</h1>
    <p class="text-gray-600 mb-6">Check your connection and try again.</p>
    <button onclick="window.location.reload()" class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">Retry</button>
  </div>
</div>
{% endblock %}
{% block content %}
<div class="text-center py-20">
  <h1 class="text-2xl font-bold text-gray-800 mb-2">You're Offline</h1>
  <p class="text-gray-600 mb-6">Showing cached data. Check your connection and try again.</p>
  <button onclick="window.location.reload()" class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">Retry</button>
</div>
{% endblock %}
```

**Step 3: Commit**

```bash
git add static/sw.js templates/pwa/offline.html
git commit -m "feat(pwa): add service worker with offline caching"
```

---

### Task 3: Create the PWA Django App (models + views)

**Files:**
- Create: `apps/pwa/__init__.py`
- Create: `apps/pwa/apps.py`
- Create: `apps/pwa/models.py`
- Create: `apps/pwa/views.py`
- Create: `apps/pwa/urls.py`
- Modify: `config/settings.py:68-79` (add `'apps.pwa'` to PROJECT_APPS)
- Modify: `config/settings.py` (add VAPID settings)
- Modify: `config/urls.py:13-31` (add pwa URL include)

**Step 1: Create the app directory**

```bash
mkdir -p apps/pwa
```

**Step 2: Create `apps/pwa/__init__.py`**

Empty file.

**Step 3: Create `apps/pwa/apps.py`**

```python
from django.apps import AppConfig


class PwaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pwa'
    verbose_name = 'Progressive Web App'
```

**Step 4: Create `apps/pwa/models.py`**

```python
from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    subscription_json = models.JSONField(
        help_text='Browser push subscription object from the Push API',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Push subscription for {self.user} ({self.created_at:%Y-%m-%d})"
```

**Step 5: Create `apps/pwa/views.py`**

```python
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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
```

**Step 6: Create `apps/pwa/urls.py`**

```python
from django.urls import path

from . import views

app_name = 'pwa'

urlpatterns = [
    path('offline/', views.offline_view, name='offline'),
    path('vapid-key/', views.vapid_public_key, name='vapid_key'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),
]
```

**Step 7: Register app in settings**

In `config/settings.py`, add `'apps.pwa'` to `PROJECT_APPS` (after line 78):

```python
PROJECT_APPS = [
    'apps.accounts',
    'apps.contacts',
    'apps.pipeline',
    'apps.campaigns',
    'apps.tasks',
    'apps.reports',
    'apps.api',
    'apps.signatures',
    'apps.scheduling',
    'apps.courses',
    'apps.pwa',
]
```

Add VAPID settings at end of `config/settings.py` (before the Logging section, around line 303):

```python
# ---------------------------------------------------------------------------
# Push Notifications (Web Push / VAPID)
# ---------------------------------------------------------------------------

VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.getenv('VAPID_ADMIN_EMAIL', 'admin@bigbeachal.com')
```

**Step 8: Add pwa URLs to config/urls.py**

Add `path('pwa/', include('apps.pwa.urls')),` to urlpatterns in `config/urls.py`:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('contacts/', include('apps.contacts.urls')),
    path('pipeline/', include('apps.pipeline.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('reports/', include('apps.reports.urls')),
    path('api/', include('apps.api.urls')),
    path('signatures/', include('apps.signatures.urls')),
    path('', include('apps.scheduling.urls')),
    path('courses/', include('apps.courses.urls_admin')),
    path('portal/', include('apps.courses.urls_portal')),
    path('pwa/', include('apps.pwa.urls')),
]
```

**Step 9: Create and run migration**

```bash
cd "c:/Users/daved/AntiGravity Projects/follow up boss"
python manage.py makemigrations pwa
python manage.py migrate
```

**Step 10: Commit**

```bash
git add apps/pwa/ config/settings.py config/urls.py
git commit -m "feat(pwa): add pwa app with push subscription model and views"
```

---

### Task 4: Create Push Notification Utility

**Files:**
- Create: `apps/pwa/push.py`

**Step 1: Create push notification helper**

Create `apps/pwa/push.py`:

```python
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_push_notification(user, title, body, url='/'):
    """Send a push notification to all of a user's subscribed devices."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — skipping push notification")
        return 0

    from .models import PushSubscription

    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', '')
    vapid_claims = {
        'sub': f"mailto:{getattr(settings, 'VAPID_ADMIN_EMAIL', '')}",
    }

    if not vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY not configured — skipping push")
        return 0

    subscriptions = PushSubscription.objects.filter(user=user)
    sent = 0

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url,
    })

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub.subscription_json,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expired or invalid — clean up
                sub.delete()
                logger.info("Removed expired push subscription %s", sub.pk)
            else:
                logger.error("Push failed for subscription %s: %s", sub.pk, e)

    return sent
```

**Step 2: Commit**

```bash
git add apps/pwa/push.py
git commit -m "feat(pwa): add push notification utility with pywebpush"
```

---

### Task 5: Wire Push Notifications into Existing Tasks

**Files:**
- Modify: `apps/tasks/tasks.py` (add push call to `send_due_reminders`)
- Modify: `apps/contacts/views.py` (add push on new contact creation)

**Step 1: Add push to task reminders**

In `apps/tasks/tasks.py`, after the existing `notify_task_reminder(task)` call (around line 29), add:

```python
from apps.pwa.push import send_push_notification

# Inside send_due_reminders(), after notify_task_reminder(task):
        send_push_notification(
            user=task.assigned_to,
            title='Task Due Soon',
            body=f'{task.title} is due in less than an hour',
            url=f'/tasks/',
        )
```

**Step 2: Add push on new contact creation**

Find the contact creation view in `apps/contacts/views.py`. After a new contact is successfully saved, add:

```python
from apps.pwa.push import send_push_notification

# After contact save in the create view:
send_push_notification(
    user=request.user,
    title='New Contact Added',
    body=f'{contact.first_name} {contact.last_name} has been added',
    url=f'/contacts/{contact.pk}/',
)
```

Note: The exact insertion point depends on the create view's structure. Look for `form.save()` or `contact.save()` and add the push call right after it.

**Step 3: Commit**

```bash
git add apps/tasks/tasks.py apps/contacts/views.py
git commit -m "feat(pwa): wire push notifications into task reminders and contact creation"
```

---

### Task 6: Update base.html with PWA Meta Tags and Service Worker Registration

**Files:**
- Modify: `templates/base.html:3-9` (add meta tags and manifest link in `<head>`)
- Modify: `templates/base.html:118-121` (add service worker registration script before `</body>`)

**Step 1: Add PWA meta tags to `<head>`**

In `templates/base.html`, after the existing `<meta name="viewport">` tag (line 5), add:

```html
    <meta name="theme-color" content="#4f46e5">
    <link rel="manifest" href="{% static 'manifest.json' %}">
    <link rel="icon" type="image/svg+xml" href="{% static 'icons/icon-192.svg' %}">
    <link rel="apple-touch-icon" href="{% static 'icons/icon-192.svg' %}">
```

Also add `{% load static %}` at the very top of the file (line 1, before `<!DOCTYPE html>`).

**Step 2: Add service worker registration and install prompt before `</body>`**

Before the closing `</body>` tag (line 120), add:

```html
<!-- PWA: Service Worker + Install Prompt + Offline Banner -->
<div id="offline-banner" class="hidden fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-yellow-900 text-center text-sm py-2 font-medium">
    You're offline — showing cached data
</div>

<div id="install-banner" class="hidden fixed bottom-0 left-0 right-0 z-50 bg-indigo-600 text-white px-4 py-3 flex items-center justify-between lg:hidden">
    <span class="text-sm font-medium">Add BigBeach CRM to your home screen</span>
    <div class="flex space-x-2">
        <button id="install-btn" class="px-3 py-1 bg-white text-indigo-600 rounded text-sm font-medium">Install</button>
        <button id="dismiss-btn" class="px-3 py-1 text-indigo-200 text-sm">Dismiss</button>
    </div>
</div>

<script>
// Service Worker Registration
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js', { scope: '/' })
        .then((reg) => console.log('SW registered:', reg.scope))
        .catch((err) => console.warn('SW registration failed:', err));
}

// Offline detection
window.addEventListener('online', () => document.getElementById('offline-banner')?.classList.add('hidden'));
window.addEventListener('offline', () => document.getElementById('offline-banner')?.classList.remove('hidden'));

// Install prompt
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    if (localStorage.getItem('pwa-install-dismissed')) return;
    deferredPrompt = e;
    document.getElementById('install-banner')?.classList.remove('hidden');
});

document.getElementById('install-btn')?.addEventListener('click', () => {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(() => {
            deferredPrompt = null;
            document.getElementById('install-banner')?.classList.add('hidden');
        });
    }
});

document.getElementById('dismiss-btn')?.addEventListener('click', () => {
    document.getElementById('install-banner')?.classList.add('hidden');
    localStorage.setItem('pwa-install-dismissed', '1');
});

// Push notification subscription
{% if user.is_authenticated %}
(async function setupPush() {
    if (!('PushManager' in window) || !('serviceWorker' in navigator)) return;
    try {
        const reg = await navigator.serviceWorker.ready;
        const existing = await reg.pushManager.getSubscription();
        if (existing) return; // Already subscribed

        const res = await fetch('/pwa/vapid-key/');
        const { public_key } = await res.json();
        if (!public_key) return;

        const permission = await Notification.requestPermission();
        if (permission !== 'granted') return;

        const subscription = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(public_key),
        });

        await fetch('/pwa/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}',
            },
            body: JSON.stringify({ subscription: subscription.toJSON() }),
        });
    } catch (err) {
        console.warn('Push setup failed:', err);
    }
})();

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}
{% endif %}
</script>
```

**Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat(pwa): add manifest link, service worker registration, and install prompt to base.html"
```

---

### Task 7: Install pywebpush and Generate VAPID Keys

**Step 1: Install pywebpush**

```bash
pip install pywebpush
pip freeze | grep -i webpush >> requirements.txt
```

Or if using a requirements file directly, add `pywebpush` to `requirements.txt`.

**Step 2: Generate VAPID keys**

```bash
python -c "
from pywebpush import webpush
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PUBLIC_KEY=' + v.public_key.public_bytes_raw().hex())
print('VAPID_PRIVATE_KEY=' + v.private_key.private_bytes_raw().hex())
"
```

Alternative simpler approach — use the `vapid` CLI if available, or generate in a Django shell:

```bash
python -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import base64

private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
raw_private = private_key.private_numbers().private_value.to_bytes(32, 'big')
raw_public = private_key.public_key().public_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.X962,
    format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PublicFormat']).PublicFormat.UncompressedPoint,
)
print('VAPID_PRIVATE_KEY=' + base64.urlsafe_b64encode(raw_private).decode().rstrip('='))
print('VAPID_PUBLIC_KEY=' + base64.urlsafe_b64encode(raw_public).decode().rstrip('='))
"
```

**Step 3: Add VAPID keys to `.env` on server**

Add the generated keys to the `.env` file on the DigitalOcean VPS:

```
VAPID_PUBLIC_KEY=<generated_public_key>
VAPID_PRIVATE_KEY=<generated_private_key>
VAPID_ADMIN_EMAIL=admin@bigbeachal.com
```

**Step 4: Commit requirements**

```bash
git add requirements.txt
git commit -m "feat(pwa): add pywebpush dependency"
```

---

### Task 8: Configure Service Worker Scope (WhiteNoise)

**Context:** The service worker at `/static/sw.js` can only control pages under `/static/` by default. We need it to control `/` (the whole site). Two options:

**Option A (recommended): Add a Django view that serves sw.js from root scope**

Add to `apps/pwa/views.py`:

```python
from django.views.static import serve
from django.conf import settings as django_settings
import os

def service_worker_view(request):
    """Serve service worker from root scope."""
    sw_path = os.path.join(django_settings.BASE_DIR, 'static', 'sw.js')
    response = render(request, 'pwa/sw.js', content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response
```

Actually simpler — serve it directly:

Add to `apps/pwa/views.py`:

```python
from django.http import FileResponse

def service_worker_view(request):
    """Serve sw.js from root URL with correct scope header."""
    sw_path = settings.BASE_DIR / 'static' / 'sw.js'
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response
```

Add to `apps/pwa/urls.py`:

```python
path('sw.js', views.service_worker_view, name='service_worker'),
```

Add to `config/urls.py` (at root level, before the pwa/ include):

```python
path('sw.js', include('apps.pwa.urls_sw')),
```

Or simpler — add the sw.js route directly in `config/urls.py`:

```python
from apps.pwa.views import service_worker_view

urlpatterns = [
    path('sw.js', service_worker_view, name='service_worker'),
    # ... existing patterns ...
]
```

Then update the registration in `base.html` to use `/sw.js` instead of `/static/sw.js`:

```javascript
navigator.serviceWorker.register('/sw.js', { scope: '/' })
```

**Step: Commit**

```bash
git add apps/pwa/views.py config/urls.py templates/base.html
git commit -m "feat(pwa): serve service worker from root URL for full scope"
```

---

### Task 9: Deploy to Server

**Step 1: SSH to server and pull changes**

```bash
ssh root@<server-ip>
cd /opt/crm
git pull origin master
```

**Step 2: Install new dependency**

```bash
source venv/bin/activate
pip install pywebpush
```

**Step 3: Run migrations**

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

**Step 4: Generate and set VAPID keys**

```bash
python -c "from cryptography.hazmat.primitives.asymmetric import ec; from cryptography.hazmat.backends import default_backend; import base64; k=ec.generate_private_key(ec.SECP256R1(),default_backend()); print('VAPID_PRIVATE_KEY='+base64.urlsafe_b64encode(k.private_numbers().private_value.to_bytes(32,'big')).decode().rstrip('=')); print('VAPID_PUBLIC_KEY='+base64.urlsafe_b64encode(k.public_key().public_bytes(encoding=__import__('cryptography.hazmat.primitives.serialization',fromlist=['Encoding']).Encoding.X962,format=__import__('cryptography.hazmat.primitives.serialization',fromlist=['PublicFormat']).PublicFormat.UncompressedPoint)).decode().rstrip('='))"
```

Add output to `.env` file, then restart:

```bash
sudo systemctl restart gunicorn
```

**Step 5: Test on phone**

1. Open `crm.bigbeachal.com` in Chrome on Android
2. Should see "Add BigBeach CRM to your home screen" banner
3. Tap Install
4. App should appear on home screen with indigo BC icon
5. Open the app — should load full-screen without browser chrome
6. Turn on airplane mode — previously visited pages should load from cache
7. Accept notification permission when prompted

---

### Summary of All New/Modified Files

**New files:**
- `static/manifest.json`
- `static/icons/icon-192.svg`
- `static/icons/icon-512.svg`
- `static/sw.js`
- `templates/pwa/offline.html`
- `apps/pwa/__init__.py`
- `apps/pwa/apps.py`
- `apps/pwa/models.py`
- `apps/pwa/views.py`
- `apps/pwa/urls.py`
- `apps/pwa/push.py`

**Modified files:**
- `config/settings.py` — add `apps.pwa` to INSTALLED_APPS, add VAPID settings
- `config/urls.py` — add `pwa/` URL include and root `sw.js` route
- `templates/base.html` — add manifest link, meta tags, SW registration, install prompt, push setup
- `apps/tasks/tasks.py` — add push notification to task reminders
- `apps/contacts/views.py` — add push notification on contact creation
- `requirements.txt` — add `pywebpush`
