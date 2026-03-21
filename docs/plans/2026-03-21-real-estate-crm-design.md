# Real Estate CRM Design Document

**Date:** 2026-03-21
**Status:** Approved

## Overview

A self-hosted real estate CRM modeled after Follow Up Boss, built for a small team (2-5 users). Core workflow: capture leads from a landing page, enroll them in customizable email drip campaigns (text + video), and manage them through a deal pipeline to close.

## Tech Stack

- **Backend:** Python / Django
- **Database:** PostgreSQL
- **Background Tasks:** Celery + Redis
- **Email:** Gmail API (OAuth2, sends as the user)
- **Frontend:** Django templates + Tailwind CSS
- **Video Hosting:** Self-hosted on the VPS
- **Deployment:** Docker Compose on a VPS ($12-24/mo), Nginx reverse proxy, Let's Encrypt SSL
- **Domain:** Porkbun (point A record to VPS, e.g. crm.yourdomain.com)

## Architecture

```
Browser (team members)
    |
    v
Nginx (reverse proxy + static/media files + SSL)
    |
    v
Django App (Gunicorn)
    ├── Web UI (Tailwind CSS, server-rendered templates)
    ├── REST API (landing page lead capture)
    └── Gmail Integration (OAuth2)
    |
    v
PostgreSQL (all data)
    |
Redis --> Celery Workers
           ├── Drip campaign scheduler
           ├── Task/reminder notifications
           └── Email sending queue
```

## Data Model

### Users & Teams
- **User** — login credentials, role (admin/agent), Gmail OAuth tokens
- **Team** — groups users together, shared lead pool

### Contacts & Leads
- **Contact** — name, email, phone, address, source, assigned agent, tags, custom fields
- **ContactNote** — timestamped notes on a contact
- **ContactActivity** — auto-logged events (email sent, call logged, stage changed)

### Deal Pipeline
- **Pipeline** — named pipeline (e.g. "Buyer Pipeline", "Seller Pipeline")
- **PipelineStage** — ordered stages (New Lead > Contacted > Appointment > Under Contract > Closed Won / Closed Lost)
- **Deal** — links a contact to a pipeline stage, expected close date, deal value

### Drip Campaigns
- **Campaign** — name, description, active/inactive status
- **CampaignStep** — ordered steps: delay (hours/days), email subject, body (HTML), optional video attachment
- **CampaignEnrollment** — tracks which contact is in which campaign, current step, next send date

### Tasks & Reminders
- **Task** — title, description, due date/time, assigned agent, linked contact, status (pending/completed/overdue)

### Smart Lists
- **SmartList** — saved filter criteria (JSON): source, tags, stage, last contact date, assigned agent. Dynamically queries contacts when viewed.

## UI Screens

1. **Dashboard** — today's tasks, recent leads, pipeline summary, overdue follow-ups
2. **Contacts** — searchable/filterable table with bulk actions (tag, assign, enroll)
3. **Contact Detail** — contact info, deal stage, tags (left). Activity timeline, notes, actions (right)
4. **Pipeline Board** — drag-and-drop Kanban view of deals across stages
5. **Smart Lists** — saved filtered views with contact counts
6. **Campaigns** — list of drip campaigns, click to edit step sequence
7. **Tasks** — list view with filters (today, overdue, upcoming, by agent)
8. **Reports** — lead source breakdown, conversion rates, agent activity, campaign performance
9. **Settings** — team management, Gmail OAuth connection, pipeline/stage customization

Design approach: clean, minimal Tailwind CSS. Responsive for mobile browser use.

## Email Drip Campaign Flow

### Lead Capture
1. Landing page form submits to `POST /api/leads/`
2. Contact created, auto-assigned (round-robin, manual, or rule-based)
3. Auto-enrolled in designated campaign

### Campaign Execution
- Celery checks enrollments on a schedule and sends due emails
- Gmail API sends emails from the user's actual address (appears in Sent folder)
- Sending staggered throughout the day to stay within Gmail's 500/day limit

### Video Emails
- Pre-recorded videos uploaded to CRM and stored on the VPS
- Email contains a clickable thumbnail image
- Click goes to a hosted page on the user's domain that plays the video
- Video views are tracked (who watched, when)

### Campaign Customization
- Create unlimited campaigns
- Add/remove/reorder steps at any time
- Edit email subject and body with a rich text editor
- Merge fields: `{{first_name}}`, `{{agent_name}}`, `{{agent_phone}}`
- Upload or swap videos on any step
- Preview emails before saving
- Edits only affect contacts who haven't reached the edited step yet
- Option to reset a contact to a specific step

### Auto-Stop Rules
- Campaign pauses if the contact replies (allows real conversation)
- Can manually re-enroll or resume

## Lead Routing

- **Round-robin** — distributes evenly across team members
- **Manual** — all leads to a specific agent
- **Rule-based** — assign by source or tag
- **Notifications** — assigned agent gets email notification + dashboard alert

## Reporting

- Lead source ROI
- Conversion rates by pipeline stage
- Agent activity metrics
- Campaign performance (open rates, click rates, video views)
- Time-based filters (this week, month, quarter, custom)
