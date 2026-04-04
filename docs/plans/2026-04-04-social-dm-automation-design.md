# Social DM Automation — Phase 1 Design

**Date:** 2026-04-04
**Status:** Approved
**Goal:** Replace ManyChat with a built-in keyword-triggered DM automation system for Instagram and Facebook, integrated directly into the CRM.

## Overview

Kelly uses ManyChat to auto-reply to Instagram and Facebook DMs based on keywords (e.g., someone comments "Condos" and gets an automated reply with a PDF link). She wants this built into the CRM so she can stop paying for ManyChat, manage everything in one place, and have leads automatically captured.

**Phase 1** covers keyword triggers with single auto-replies and CRM actions. Phase 2 (future) adds multi-step conversation flows with branching logic and a visual flow builder.

## Architecture

New Django app: `apps/social/`

```
Instagram/Facebook DM or Comment
        ↓
  Meta Webhook (POST /social/webhook/)
        ↓
  Celery Task: process_incoming_message
        ↓
  Match keyword triggers
        ↓
  Execute actions:
    ├── Send DM reply via Meta Send API
    ├── Create/update contact in CRM
    ├── Add tags
    └── Enroll in campaign
```

Messages are processed async via Celery so the webhook returns a 200 within Meta's timeout. Request signatures are verified using the Meta app secret.

## Data Models

### SocialAccount

Links Kelly's Meta pages to the CRM team.

| Field | Type | Notes |
|-------|------|-------|
| team | FK → Team | Multi-tenant scoping |
| platform | CharField | `instagram` or `facebook` |
| page_id | CharField | Meta Page ID |
| page_name | CharField | Display name |
| access_token | TextField | Encrypted Page Access Token from OAuth |
| instagram_account_id | CharField | For IG-specific API calls, nullable |
| is_active | BooleanField | Enable/disable |
| webhook_verified | BooleanField | Whether Meta webhook verification passed |
| created_at | DateTimeField | |

### KeywordTrigger

One trigger = one keyword = one reply + CRM actions.

| Field | Type | Notes |
|-------|------|-------|
| team | FK → Team | Multi-tenant scoping |
| keyword | CharField | The trigger word (e.g., "Condos") |
| match_type | CharField | `exact`, `contains`, `starts_with` |
| platform | CharField | `instagram`, `facebook`, or `both` |
| is_active | BooleanField | Quick enable/disable |
| reply_text | TextField | The auto-reply message body |
| reply_link | URLField | Optional link (PDF, video page, etc.) |
| tags | JSONField | Tags to apply to the contact |
| campaign | FK → Campaign | Optional auto-enrollment, nullable |
| create_contact | BooleanField | Whether to add sender to CRM |
| notify_agent | BooleanField | Alert Kelly when triggered |
| created_at | DateTimeField | |
| updated_at | DateTimeField | |

### MessageLog

Record of every incoming message and outcome.

| Field | Type | Notes |
|-------|------|-------|
| social_account | FK → SocialAccount | Which connected account |
| sender_id | CharField | Meta's platform-scoped user ID |
| sender_name | CharField | Sender display name |
| message_text | TextField | The incoming message |
| platform | CharField | `instagram` or `facebook` |
| trigger_matched | FK → KeywordTrigger | Which trigger fired, nullable |
| contact_created | FK → Contact | If a contact was created, nullable |
| reply_sent | BooleanField | Whether auto-reply was sent |
| timestamp | DateTimeField | When message was received |

## Admin UI

### Keyword Triggers Page

**List view:** Table of all triggers showing keyword, platform, reply preview, campaign, active toggle. Create button at top.

**Create/Edit form:**
- Keyword (text)
- Match Type (dropdown: exact, contains, starts with)
- Platform (radio: Instagram, Facebook, Both)
- Auto-Reply Message (textarea)
- Link (optional URL — PDF, video, landing page)
- CRM Actions section:
  - Add to CRM (checkbox, default on)
  - Tags (multi-select, can create new)
  - Enroll in Campaign (dropdown of active campaigns)
  - Notify Me (checkbox)

### Social Accounts Page

- Connect/disconnect Instagram and Facebook via Meta OAuth
- Shows connection status, page name, last webhook received
- This is where the Meta OAuth flow is initiated

### Message Log Page

- Searchable table: sender name, message, platform, trigger matched (or "no match"), contact created
- Helps Kelly spot new keywords to add and see engagement

## Meta API Integration

### Setup Requirements

1. Create a Meta App in the Meta Developer Portal
2. Kelly connects pages via OAuth flow → store Page Access Token
3. Register webhook URL: `crm.bigbeachal.com/social/webhook/`
4. Submit for App Review requesting: `pages_messaging`, `instagram_messaging`, `pages_manage_metadata`
5. Kelly's Instagram must be a Business or Creator account (already is)

### Receiving Messages

- Meta POSTs to `/social/webhook/` for every DM and comment
- Verify request signature (X-Hub-Signature-256 header) using app secret
- Return 200 immediately, process async via Celery
- Payload includes: sender ID, message text, platform, timestamp

### Sending Replies

- Both platforms: `POST https://graph.facebook.com/v21.0/me/messages`
- Instagram uses Instagram-scoped sender ID, Facebook uses Page-scoped sender ID
- Reply body includes text + optional link from the KeywordTrigger

### Contact Capture

Meta does NOT provide sender email or phone (privacy rules). We get:
- Sender's display name
- Platform-scoped user ID

**Strategy:** Create contact with name + platform ID stored in `custom_fields`. If the auto-reply includes a link to a landing page with a form, that form captures email/phone and merges with the existing contact via platform ID lookup.

### 24-Hour Messaging Window

Meta only allows replies within 24 hours of the sender's last message. For keyword triggers this is not an issue — they message, we reply instantly. The MessageLog timestamp enforces this constraint.

## Phase 2 (Future)

- Multi-step conversation flows with branching logic
- Questionnaires with pre-populated clickable answer buttons
- Visual flow builder UI (drag-and-drop or step-by-step)
- Routing based on answers (different campaigns, tags, content per path)
- Proactive messaging via approved Message Templates
