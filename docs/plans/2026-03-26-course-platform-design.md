# Course Platform Design (Kajabi-Style)

**Date:** 2026-03-26
**Status:** Approved

## Overview

A course and video hosting platform built as a new Django app within the existing CRM project. External agents (not CRM users) sign up on a separate student portal to access structured courses with video lessons and PDF resources. Admin team manages courses from within the CRM.

## Requirements

- Course platform for external agents — separate from CRM users
- Free signup now, payment support later (some courses free, some paid)
- Structured courses: Courses → Modules → Lessons
- Content: embedded YouTube/Vimeo videos + PDF downloads
- Two unlock modes per course: time-based drip (weekly) OR completion-based
- Auto-track lesson views, show progress
- Full admin dashboard in CRM (stats, completion rates, announcements, future revenue)
- Separate student portal with its own clean UI (e.g., `courses.bigbeachal.com`)

## Approach

**New Django app + separate student portal** (Approach A). Single codebase, shared database, shared Celery. Student portal served on a subdomain with its own base template. Admin course management lives inside the existing CRM.

## Data Model

### User (existing model, extended)
- Add `student` to role choices: `admin`, `agent`, `student`
- Add `stripe_customer_id`: CharField (nullable, for future payments)

### Course
- `title`: CharField
- `slug`: SlugField (unique, URL-friendly)
- `description`: TextField
- `thumbnail`: ImageField (optional)
- `instructor`: FK → User
- `team`: FK → Team
- `unlock_mode`: CharField choices: `time_drip`, `completion_based`
- `drip_interval_days`: IntegerField (default 7, used for time_drip only)
- `is_published`: BooleanField (default False)
- `is_free`: BooleanField (default True)
- `price`: DecimalField (nullable, for future)
- `created_at`, `updated_at`: DateTimeField

### Module
- `course`: FK → Course (cascade delete)
- `title`: CharField
- `description`: TextField (optional)
- `order`: PositiveIntegerField

### Lesson
- `module`: FK → Module (cascade delete)
- `title`: CharField
- `description`: TextField (HTML, optional — lesson notes)
- `video_url`: URLField (YouTube/Vimeo embed link)
- `pdf_file`: FileField (optional)
- `order`: PositiveIntegerField
- `duration_minutes`: PositiveIntegerField (optional, for display)

### Enrollment
- `student`: FK → User
- `course`: FK → Course
- `enrolled_at`: DateTimeField (auto)
- `current_module_unlocked`: PositiveIntegerField (default 1)
- `next_unlock_date`: DateTimeField (nullable, for time_drip)
- Future fields: `payment_status`, `stripe_payment_id`
- Unique together: (student, course)

### LessonProgress
- `student`: FK → User
- `lesson`: FK → Lesson
- `started_at`: DateTimeField (auto)
- `completed_at`: DateTimeField (nullable)
- `is_completed`: BooleanField (default False)
- Unique together: (student, lesson)

### Announcement
- `course`: FK → Course
- `title`: CharField
- `body`: TextField (HTML)
- `created_by`: FK → User
- `send_email`: BooleanField (default False)
- `created_at`: DateTimeField (auto)

## Architecture & URL Routing

### Subdomain Setup
- CRM: `crm.bigbeachal.com` (existing)
- Student Portal: `courses.bigbeachal.com` (new)
- Same Django instance — Nginx routes both subdomains to Gunicorn

### Student Portal URLs (`courses.bigbeachal.com`)
```
/                          → Course catalog (published courses)
/signup/                   → Student registration
/login/                    → Student login
/logout/                   → Logout
/dashboard/                → My enrolled courses + progress
/course/<slug>/            → Course overview (enroll or continue)
/course/<slug>/module/<n>/lesson/<n>/  → Lesson view
/profile/                  → Student profile/settings
```

### CRM Admin URLs (existing CRM)
```
/courses/                  → Course list (admin)
/courses/create/           → Create course
/courses/<id>/edit/        → Edit course (modules, lessons, reorder)
/courses/<id>/students/    → Enrolled students + progress
/courses/<id>/stats/       → Completion rates, engagement
/courses/<id>/announcements/ → Send announcements
/courses/dashboard/        → Overall stats
```

### Middleware & Access Control
- `SubdomainMiddleware` detects subdomain, sets `request.portal = 'crm'` or `'courses'`
- Student role on CRM paths → redirect to portal
- Admin/agent can access both (CRM for management, portal for preview)

### Templates
- Student portal: `portal_base.html` — clean top navbar, no sidebar
- CRM admin: existing `base.html` with "Courses" added to sidebar nav

## Drip & Unlock Logic

### Time-based drip (`time_drip`)
- On enrollment: Module 1 unlocks, `next_unlock_date = enrolled_at + drip_interval_days`
- Celery beat task runs daily: checks enrollments where `next_unlock_date <= now()`, increments `current_module_unlocked`, sets next unlock date
- Students see locked modules with "Unlocks on [date]"

### Completion-based (`completion_based`)
- Module 1 unlocks on enrollment
- When all lessons in a module are completed → next module unlocks automatically
- Checked in real-time on lesson completion (no Celery needed)
- `next_unlock_date` not used

### Auto-Completion Tracking
- Opening a lesson creates `LessonProgress` with `started_at`
- HTMX request fires after 30 seconds → marks `is_completed = True`
- For completion-based courses: check if all lessons in module done → unlock next module

### Progress Display
- Course card: "X% complete" (completed lessons / total lessons)
- Module: progress bar + lock/unlock icon
- Lesson: checkmark if completed

## Admin Dashboard & Analytics

### Course Management
- Course builder: create course → add modules → add lessons, drag-to-reorder with HTMX
- Lesson editor: title, video URL, description (textarea/HTML), PDF upload
- "Preview as student" button

### Student Management
- Per-course student list: name, email, enrollment date, progress %, last active
- Bulk enroll by email, export CSV

### Analytics (`/courses/dashboard/`)
- Total students, active students (last 7 days), total courses (published/draft)
- Per-course: enrollment count, avg completion rate, drop-off module, most/least watched lessons
- Future: revenue totals

### Announcements
- Write announcement per course → banner on course page
- Optional email notification to all enrolled students via Celery

## Student Portal UI

### Catalog Page
- Top navbar: logo, "Courses", "My Dashboard", login/signup
- Grid of course cards: thumbnail, title, description, "Free" badge, lesson count

### Course Overview
- Hero: thumbnail, title, description, instructor
- Module list with lesson counts (locked modules grayed)
- "Enroll" / "Continue Learning" button
- Progress bar if enrolled

### Lesson View
- Breadcrumb: Course → Module → Lesson
- Embedded YouTube/Vimeo video (responsive iframe)
- Lesson notes (HTML) below video
- PDF download button if attached
- Sidebar/bottom: module lesson list with checkmarks, current highlighted
- Auto-complete after 30 seconds

### Student Dashboard
- "My Courses" grid with progress bars
- "Continue where you left off" link
- Recent announcements

### Design
- Tailwind CSS (CDN)
- Clean, modern, white/light — professional learning platform
- Mobile responsive
- HTMX for enrollment, completion, progress (no full page reloads)
