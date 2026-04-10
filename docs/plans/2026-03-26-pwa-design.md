# PWA Design for BigBeach CRM

**Date:** 2026-03-26
**Status:** Approved

## Goal

Turn the existing responsive Django CRM into an installable Progressive Web App so it can be used from an Android phone like a native app, with offline reading and push notifications.

## Components

### 1. Web App Manifest (`static/manifest.json`)

- App name: "BigBeach CRM", short name: "CRM"
- Theme/background color: Indigo 600 (`#4f46e5`)
- Display mode: `standalone` (no browser chrome)
- Placeholder icons: colored squares with "BC" text (48, 72, 96, 128, 144, 192, 512px)
- Start URL: `/` (dashboard)

### 2. Service Worker (`static/sw.js`)

- **Static assets (CSS, JS, icons):** Cache-first strategy — serve from cache, update in background
- **HTML pages:** Network-first strategy — try network, fall back to cached version if offline
- Pages cached as user visits them (runtime caching)
- Pre-cache: manifest, icons, offline fallback page
- Offline fallback: show cached page if available, otherwise a branded "You're offline" page

### 3. Push Notifications

- New Django app: `apps/pwa/`
- Models: `PushSubscription` (stores browser push subscription JSON per user)
- API endpoints:
  - `POST /pwa/subscribe/` — save push subscription
  - `POST /pwa/unsubscribe/` — remove subscription
- Uses Web Push protocol with VAPID keys (no Firebase dependency)
- Python package: `pywebpush`
- VAPID keys stored in environment variables
- Initial notification triggers:
  - New contact created
  - Task due reminder
- Notification payload includes title, body, URL to open on click

### 4. Template Changes (`base.html`)

- Add `<link rel="manifest" href="/static/manifest.json">`
- Add `<meta name="theme-color" content="#4f46e5">`
- Add service worker registration script
- Add "Install App" prompt banner (shown once to mobile visitors, dismissible)
- Add offline indicator banner (hidden by default, toggled by service worker via postMessage)

### 5. Install Prompt UX

- Intercept `beforeinstallprompt` event
- Show a subtle top banner: "Add BigBeach CRM to your home screen" with Install/Dismiss buttons
- Store dismissal in localStorage so it doesn't re-appear
- Banner only shows on mobile (check `navigator.userAgent` or screen width)

## Out of Scope

- App store listing (PWAs install from browser)
- Offline form submission / background sync
- Complex offline data sync
- iOS-specific workarounds (Safari PWA support is limited)

## Technical Notes

- Static files served via WhiteNoise — service worker and manifest served as regular static files
- HTMX pages cache well since they're full HTML responses
- Service worker scope: `/` (root, since static files are served from root via WhiteNoise)
- Django's CSRF token handling works fine with service worker caching since forms fetch fresh tokens on network-first pages
