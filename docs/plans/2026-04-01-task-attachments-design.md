# Task Attachments Design

## Overview

Add document attachment support to CRM tasks, allowing users to attach PDFs, images, and other files (up to 50MB each) to any task. Multiple attachments per task supported.

## Data Model

### TaskAttachment

| Field       | Type                     | Details                              |
|-------------|--------------------------|--------------------------------------|
| task        | ForeignKey(Task)         | CASCADE delete                       |
| file        | FileField                | upload_to='task_attachments/'        |
| filename    | CharField(max_length=255)| Original uploaded filename           |
| uploaded_by | ForeignKey(User)         | SET_NULL, nullable                   |
| created_at  | DateTimeField            | auto_now_add                         |

- 50MB max file size validation on the model/form level
- Accepts common file types (PDF, JPEG, PNG, Word, Excel, etc.)

## Task Create/Edit Form

- Add a multi-file input at the bottom of the existing `task_form.html`
- Handle uploads via `request.FILES.getlist()` in `TaskCreateView` and `TaskUpdateView`
- Files saved as `TaskAttachment` records linked to the task
- No formset needed — simple file list handling in `form_valid()`

## Task List Integration

- Paperclip icon + attachment count badge on task rows that have attachments
- Clicking the icon opens an HTMX-powered panel below the row showing:
  - List of attached files (name, size, download link, delete button)
  - Upload input to add more files without navigating to the edit page
- Upload and delete handled via dedicated HTMX endpoints

## URL Endpoints

| Method | URL                                          | Purpose                    |
|--------|----------------------------------------------|----------------------------|
| GET    | `/tasks/<pk>/attachments/`                   | HTMX partial: file list    |
| POST   | `/tasks/<pk>/attachments/upload/`            | HTMX file upload           |
| POST   | `/tasks/<pk>/attachments/<att_pk>/delete/`   | HTMX delete attachment     |

## Templates

- `templates/tasks/_attachments.html` — partial for the expandable attachment panel (file list + upload input + delete buttons)
- Modified `templates/tasks/task_form.html` — add multi-file input field
- Modified `templates/tasks/task_list.html` — add paperclip icon/badge and HTMX panel trigger

## File Storage

Uses existing `FileSystemStorage` backend and `MEDIA_ROOT` configuration. Files stored under `media/task_attachments/`.
