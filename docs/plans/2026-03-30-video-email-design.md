# Video Email App Design (BombBomb Alternative)

**Date:** 2026-03-30
**Status:** Approved

## Overview

Self-hosted video email platform as a new `videos` Django app. Record or upload videos, host them on the server or YouTube (unlisted), and use them in manual Gmail sends or automated campaign emails. Per-recipient tracking when sent through campaigns, anonymous view counts for shared links.

## Data Models

### Video
- `uuid` — public URL identifier
- `title` — user-facing name
- `video_file` — local file (nullable, for local storage)
- `youtube_id` — YouTube video ID (nullable, for YouTube storage)
- `storage_type` — `local` or `youtube`
- `thumbnail` — auto-generated frame with play button overlay (always local)
- `duration` — extracted from video metadata
- `team` — FK to Team
- `created_by` — FK to User
- `created_at` / `updated_at`

### VideoView
- `video` — FK to Video
- `contact` — nullable FK to Contact (for tracked campaign links)
- `tracking_token` — unique per-recipient token
- `ip_address` / `user_agent` — basic visitor info
- `watched_duration` — seconds watched
- `viewed_at`

### CampaignStep (existing, modified)
- `video` — nullable FK to Video (replaces or supplements existing video_file/video_thumbnail fields)

## Architecture

### Recording & Upload

- Video library page in CRM sidebar — grid of videos with thumbnails
- **Webcam recorder:** MediaRecorder API in browser with live preview, record/stop/re-record
  - Before recording: toggle to choose "Save to Server" or "Save to YouTube"
  - Records to WebM blob in browser memory
  - On save: uploads blob to server, Celery task processes it
- **File upload:** Drag-and-drop or file picker, same destination choice
  - Files over ~50MB default to YouTube suggestion
- **Processing (Celery task):**
  - If local: convert WebM to MP4 via ffmpeg, store in `media/videos/`
  - If YouTube: upload to YouTube as unlisted via YouTube Data API
  - Both: extract thumbnail frame at 1s via ffmpeg, overlay play button via Pillow, store in `media/video_thumbnails/`
  - Extract duration from metadata

### YouTube Integration

- Uses existing Google OAuth credentials, adds YouTube Data API scope
- Upload as unlisted — accessible only via direct link (matches BombBomb behavior)
- YouTube video ID stored on Video model for iframe embedding
- Upload handled by Celery background task

### Public Landing Page

- URL: `crm.bigbeachal.com/v/{uuid}`
- Branded page: video player + logo + contact info
- Local videos: HTML5 `<video>` player
- YouTube videos: YouTube iframe embed
- Tracking: if `?t={token}` query param present, logs VideoView tied to specific contact; otherwise logs anonymous view
- JavaScript sends watch progress to `/v/{uuid}/track/` via POST every 10 seconds (debounced)

### Gmail Usage (Manual Sends)

- "Copy Email Snippet" button on video library / video detail page
- Copies HTML block to clipboard:
  ```html
  <a href="https://crm.bigbeachal.com/v/{uuid}">
    <img src="https://crm.bigbeachal.com/media/video_thumbnails/{file}"
         alt="Click to watch video" style="max-width:100%;border-radius:8px;">
  </a>
  ```
- Paste into Gmail compose — recipient sees thumbnail with play button

### Campaign Integration

- Campaign step builder: pick a video from library or record new one
- Email renderer inserts thumbnail image + tracked link per recipient
- Each recipient gets unique tracking token: `/v/{uuid}?t={token}`
- VideoView records link contact to view

### Analytics

- Video detail page shows:
  - Total views / unique viewers
  - Per-contact watch list: who watched, when, how long
- Watch duration tracked via JS timeupdate events on landing page

## Storage

- **Local:** `media/videos/` (MP4) and `media/video_thumbnails/` (JPEG)
- **YouTube:** unlisted uploads, only YouTube ID stored locally
- **Hybrid strategy:** small recordings local, larger videos to YouTube
- **Current VPS:** 48GB total, ~39GB free — sufficient for initial use, upgrade when needed

## Dependencies

- `ffmpeg` — apt install on DigitalOcean server (thumbnail extraction, WebM to MP4 conversion)
- YouTube Data API — scope added to existing Google OAuth
- No new Python packages (Pillow + Celery already installed)

## URL Structure

```
/videos/                    — video library (grid view)
/videos/upload/             — upload form
/videos/record/             — webcam recorder
/videos/<id>/               — video detail + analytics
/videos/<id>/edit/          — edit title, thumbnail
/videos/<id>/delete/        — delete video
/videos/<id>/snippet/       — get email snippet HTML
/v/<uuid>/                  — public landing page
/v/<uuid>/track/            — watch progress endpoint (POST)
```
