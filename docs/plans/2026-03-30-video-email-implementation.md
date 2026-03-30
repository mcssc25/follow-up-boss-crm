# Video Email App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted video email platform (BombBomb alternative) as a new `videos` Django app with hybrid local/YouTube storage, webcam recording, email snippets, campaign integration, and per-recipient view tracking.

**Architecture:** New `videos` app following existing project conventions (team-based multi-tenancy, LoginRequiredMixin, Tailwind/HTMX templates). Videos stored locally or on YouTube (unlisted). Public landing pages at `/v/{uuid}` for playback with tracking. Celery tasks handle video processing (ffmpeg thumbnail extraction, WebM→MP4 conversion, YouTube upload).

**Tech Stack:** Django 5.1, Celery, ffmpeg, Pillow, YouTube Data API, MediaRecorder API (browser), HTMX, Tailwind CSS

---

## Phase 1: Core Models & Admin

### Task 1: Create the videos app skeleton

**Files:**
- Create: `apps/videos/__init__.py`
- Create: `apps/videos/apps.py`
- Create: `apps/videos/admin.py`
- Create: `apps/videos/models.py`
- Create: `apps/videos/urls.py`
- Create: `apps/videos/views.py`
- Create: `apps/videos/forms.py`
- Create: `apps/videos/tasks.py`
- Modify: `config/settings.py` (add to PROJECT_APPS)
- Modify: `config/urls.py` (add URL include)

**Step 1: Create app directory and files**

```bash
mkdir -p apps/videos
touch apps/videos/__init__.py
```

**Step 2: Create apps.py**

```python
from django.apps import AppConfig

class VideosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.videos'
    verbose_name = 'Videos'
```

**Step 3: Create models.py with Video and VideoView**

```python
import uuid as uuid_lib
from django.conf import settings
from django.db import models
from django.urls import reverse


class Video(models.Model):
    STORAGE_LOCAL = 'local'
    STORAGE_YOUTUBE = 'youtube'
    STORAGE_CHOICES = [
        (STORAGE_LOCAL, 'Local'),
        (STORAGE_YOUTUBE, 'YouTube'),
    ]

    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    video_file = models.FileField(upload_to='videos/', blank=True, null=True)
    youtube_id = models.CharField(max_length=20, blank=True)
    storage_type = models.CharField(
        max_length=10, choices=STORAGE_CHOICES, default=STORAGE_LOCAL,
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_PROCESSING,
    )
    thumbnail = models.ImageField(upload_to='video_thumbnails/', blank=True, null=True)
    duration = models.PositiveIntegerField(default=0, help_text='Duration in seconds')
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='videos',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='videos',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('videos:detail', kwargs={'pk': self.pk})

    def get_landing_url(self):
        return reverse('videos:landing', kwargs={'uuid': self.uuid})

    def get_full_landing_url(self):
        from django.contrib.sites.models import Site
        return f"https://crm.bigbeachal.com/v/{self.uuid}"

    def get_thumbnail_url(self):
        if self.thumbnail:
            return f"https://crm.bigbeachal.com{self.thumbnail.url}"
        return ''

    def get_email_snippet(self):
        landing = self.get_full_landing_url()
        thumb = self.get_thumbnail_url()
        return (
            f'<a href="{landing}">'
            f'<img src="{thumb}" alt="Click to watch video" '
            f'style="max-width:100%;border-radius:8px;">'
            f'</a>'
        )


class VideoView(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='views')
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_views',
    )
    tracking_token = models.UUIDField(default=uuid_lib.uuid4, unique=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    watched_duration = models.PositiveIntegerField(default=0, help_text='Seconds watched')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        who = self.contact or self.ip_address or 'Anonymous'
        return f"{who} viewed {self.video.title}"
```

**Step 4: Create admin.py**

```python
from django.contrib import admin
from .models import Video, VideoView


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'storage_type', 'status', 'team', 'created_at']
    list_filter = ['storage_type', 'status', 'team']
    search_fields = ['title']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(VideoView)
class VideoViewAdmin(admin.ModelAdmin):
    list_display = ['video', 'contact', 'watched_duration', 'viewed_at']
    list_filter = ['viewed_at']
    readonly_fields = ['tracking_token', 'viewed_at']
```

**Step 5: Create empty placeholder files**

```python
# urls.py
from django.urls import path

app_name = 'videos'

urlpatterns = []
```

```python
# views.py
# Views will be added in subsequent tasks
```

```python
# forms.py
# Forms will be added in subsequent tasks
```

```python
# tasks.py
# Celery tasks will be added in subsequent tasks
```

**Step 6: Register app in settings.py**

In `config/settings.py`, add `'apps.videos'` to PROJECT_APPS list (after `'apps.pwa'`).

**Step 7: Register URLs in config/urls.py**

Add these two lines to urlpatterns:
```python
path('videos/', include('apps.videos.urls')),
path('v/', include('apps.videos.urls_public')),
```

Create `apps/videos/urls_public.py`:
```python
from django.urls import path

app_name = 'videos_public'

urlpatterns = []
```

**Step 8: Run makemigrations and migrate**

```bash
python manage.py makemigrations videos
python manage.py migrate
```

**Step 9: Commit**

```bash
git add apps/videos/ config/settings.py config/urls.py
git commit -m "feat(videos): add videos app with Video and VideoView models"
```

---

## Phase 2: Video Processing (Celery + ffmpeg)

### Task 2: Thumbnail generation and video processing task

**Files:**
- Create: `apps/videos/processing.py`
- Modify: `apps/videos/tasks.py`

**Step 1: Create processing.py with ffmpeg + Pillow helpers**

```python
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw


def extract_thumbnail(video_path, output_path, timestamp='00:00:01'):
    """Extract a frame from a video file using ffmpeg."""
    subprocess.run(
        [
            'ffmpeg', '-y', '-i', str(video_path),
            '-ss', timestamp, '-vframes', '1',
            '-vf', 'scale=640:-1',
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )


def overlay_play_button(image_path):
    """Draw a semi-transparent play button circle on a thumbnail."""
    img = Image.open(image_path).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cx, cy = img.size[0] // 2, img.size[1] // 2
    radius = min(img.size) // 6

    # Semi-transparent dark circle
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(0, 0, 0, 160),
    )

    # White triangle (play icon)
    tri_size = radius * 0.6
    x1 = cx - tri_size * 0.4
    y1 = cy - tri_size
    x2 = cx - tri_size * 0.4
    y2 = cy + tri_size
    x3 = cx + tri_size * 0.8
    y3 = cy
    draw.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=(255, 255, 255, 230))

    result = Image.alpha_composite(img, overlay).convert('RGB')
    result.save(image_path, 'JPEG', quality=85)


def get_video_duration(video_path):
    """Get duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return int(float(result.stdout.strip()))
    except (ValueError, AttributeError):
        return 0


def convert_webm_to_mp4(webm_path, mp4_path):
    """Convert WebM recording to MP4 for broad compatibility."""
    subprocess.run(
        [
            'ffmpeg', '-y', '-i', str(webm_path),
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k',
            str(mp4_path),
        ],
        capture_output=True,
        check=True,
    )
```

**Step 2: Create Celery task in tasks.py**

```python
import os
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files import File


@shared_task
def process_video(video_id):
    """Process an uploaded video: convert if needed, generate thumbnail, extract duration."""
    from .models import Video
    from .processing import (
        convert_webm_to_mp4,
        extract_thumbnail,
        get_video_duration,
        overlay_play_button,
    )

    try:
        video = Video.objects.get(pk=video_id)
    except Video.DoesNotExist:
        return

    try:
        video_path = video.video_file.path

        # Convert WebM to MP4 if needed
        if video_path.endswith('.webm'):
            mp4_path = video_path.rsplit('.', 1)[0] + '.mp4'
            convert_webm_to_mp4(video_path, mp4_path)
            os.remove(video_path)
            video.video_file.name = video.video_file.name.rsplit('.', 1)[0] + '.mp4'
            video_path = mp4_path

        # Extract duration
        video.duration = get_video_duration(video_path)

        # Generate thumbnail
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name

        extract_thumbnail(video_path, tmp_path)
        overlay_play_button(tmp_path)

        thumb_name = f"{video.uuid}.jpg"
        with open(tmp_path, 'rb') as f:
            video.thumbnail.save(thumb_name, File(f), save=False)

        os.unlink(tmp_path)

        video.status = Video.STATUS_READY
        video.save()

    except Exception:
        video.status = Video.STATUS_FAILED
        video.save()
        raise
```

**Step 3: Commit**

```bash
git add apps/videos/processing.py apps/videos/tasks.py
git commit -m "feat(videos): add ffmpeg processing and Celery thumbnail generation task"
```

---

## Phase 3: Video Library UI (Upload + List + Detail)

### Task 3: Forms, views, and URL routing

**Files:**
- Modify: `apps/videos/forms.py`
- Modify: `apps/videos/views.py`
- Modify: `apps/videos/urls.py`

**Step 1: Create forms.py**

```python
from django import forms
from .models import Video

INPUT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
)


class VideoUploadForm(forms.ModelForm):
    storage_type = forms.ChoiceField(
        choices=Video.STORAGE_CHOICES,
        initial=Video.STORAGE_LOCAL,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'storage_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CSS,
                'placeholder': 'Give your video a name...',
            }),
            'video_file': forms.ClearableFileInput(attrs={
                'class': INPUT_CSS,
                'accept': 'video/*',
            }),
        }


class VideoEditForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CSS,
            }),
        }
```

**Step 2: Create views.py**

```python
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .forms import VideoEditForm, VideoUploadForm
from .models import Video, VideoView
from .tasks import process_video


class VideoListView(LoginRequiredMixin, ListView):
    model = Video
    template_name = 'videos/video_list.html'
    context_object_name = 'videos'

    def get_queryset(self):
        return Video.objects.filter(team=self.request.user.team)


class VideoDetailView(LoginRequiredMixin, DetailView):
    model = Video
    template_name = 'videos/video_detail.html'

    def get_queryset(self):
        return Video.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        views = self.object.views.all()
        ctx['total_views'] = views.count()
        ctx['unique_viewers'] = views.exclude(contact=None).values('contact').distinct().count()
        ctx['recent_views'] = views.select_related('contact')[:20]
        ctx['email_snippet'] = self.object.get_email_snippet()
        return ctx


@login_required
def video_upload(request):
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.team = request.user.team
            video.created_by = request.user
            video.save()
            process_video.delay(video.id)
            messages.success(request, 'Video uploaded! Processing will complete shortly.')
            return redirect('videos:detail', pk=video.pk)
    else:
        form = VideoUploadForm()
    return render(request, 'videos/video_upload.html', {'form': form})


@login_required
def video_record(request):
    """Webcam recorder page."""
    return render(request, 'videos/video_record.html')


@login_required
@require_POST
def video_record_save(request):
    """Save a webcam recording blob uploaded via fetch."""
    video_blob = request.FILES.get('video')
    title = request.POST.get('title', 'Untitled Recording')
    storage_type = request.POST.get('storage_type', Video.STORAGE_LOCAL)

    if not video_blob:
        return JsonResponse({'error': 'No video data'}, status=400)

    video = Video.objects.create(
        title=title,
        video_file=video_blob,
        storage_type=storage_type,
        team=request.user.team,
        created_by=request.user,
    )
    process_video.delay(video.id)
    return JsonResponse({
        'id': video.pk,
        'redirect': video.get_absolute_url(),
    })


@login_required
def video_edit(request, pk):
    video = get_object_or_404(Video, pk=pk, team=request.user.team)
    if request.method == 'POST':
        form = VideoEditForm(request.POST, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, 'Video updated.')
            return redirect('videos:detail', pk=video.pk)
    else:
        form = VideoEditForm(instance=video)
    return render(request, 'videos/video_edit.html', {'form': form, 'video': video})


@login_required
@require_POST
def video_delete(request, pk):
    video = get_object_or_404(Video, pk=pk, team=request.user.team)
    video.delete()
    messages.success(request, 'Video deleted.')
    return redirect('videos:list')


@login_required
def video_snippet(request, pk):
    """Return email snippet HTML as JSON."""
    video = get_object_or_404(Video, pk=pk, team=request.user.team)
    return JsonResponse({'snippet': video.get_email_snippet()})


# --- Public views (no login required) ---

def video_landing(request, uuid):
    """Public landing page for watching a video."""
    video = get_object_or_404(Video, uuid=uuid, status=Video.STATUS_READY)

    # Check for tracking token
    tracking_token = request.GET.get('t')
    contact = None
    if tracking_token:
        try:
            from apps.contacts.models import Contact
            view_record = VideoView.objects.get(tracking_token=tracking_token)
            contact = view_record.contact
            # Update the existing view record
            view_record.ip_address = request.META.get('REMOTE_ADDR')
            view_record.user_agent = request.META.get('HTTP_USER_AGENT', '')
            view_record.save()
        except VideoView.DoesNotExist:
            pass

    if not tracking_token or not contact:
        # Create anonymous view
        VideoView.objects.create(
            video=video,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    return render(request, 'videos/video_landing.html', {
        'video': video,
        'tracking_token': tracking_token or '',
    })


@csrf_exempt
@require_POST
def video_track(request, uuid):
    """Track watch progress from the landing page JS."""
    video = get_object_or_404(Video, uuid=uuid)
    try:
        data = json.loads(request.body)
        duration = int(data.get('duration', 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid data'}, status=400)

    tracking_token = data.get('token')
    if tracking_token:
        try:
            view = VideoView.objects.get(tracking_token=tracking_token)
            view.watched_duration = max(view.watched_duration, duration)
            view.save(update_fields=['watched_duration'])
            return JsonResponse({'ok': True})
        except VideoView.DoesNotExist:
            pass

    # Update most recent anonymous view from this IP
    ip = request.META.get('REMOTE_ADDR')
    view = video.views.filter(
        ip_address=ip, contact=None,
    ).order_by('-viewed_at').first()
    if view:
        view.watched_duration = max(view.watched_duration, duration)
        view.save(update_fields=['watched_duration'])

    return JsonResponse({'ok': True})
```

**Step 3: Create urls.py**

```python
from django.urls import path
from . import views

app_name = 'videos'

urlpatterns = [
    path('', views.VideoListView.as_view(), name='list'),
    path('upload/', views.video_upload, name='upload'),
    path('record/', views.video_record, name='record'),
    path('record/save/', views.video_record_save, name='record_save'),
    path('<int:pk>/', views.VideoDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.video_edit, name='edit'),
    path('<int:pk>/delete/', views.video_delete, name='delete'),
    path('<int:pk>/snippet/', views.video_snippet, name='snippet'),
]
```

**Step 4: Create urls_public.py**

```python
from django.urls import path
from . import views

app_name = 'videos_public'

urlpatterns = [
    path('<uuid:uuid>/', views.video_landing, name='landing'),
    path('<uuid:uuid>/track/', views.video_track, name='track'),
]
```

**Step 5: Commit**

```bash
git add apps/videos/
git commit -m "feat(videos): add forms, views, and URL routing for video library"
```

---

## Phase 4: Templates

### Task 4: Video library templates (list, upload, detail, edit)

**Files:**
- Create: `templates/videos/video_list.html`
- Create: `templates/videos/video_upload.html`
- Create: `templates/videos/video_detail.html`
- Create: `templates/videos/video_edit.html`
- Modify: `templates/base.html` (add sidebar link)

**Step 1: Create video_list.html (grid of video cards with thumbnails)**

```html
{% extends "base.html" %}
{% block title %}Videos{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto">
    <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-bold text-gray-900">Videos</h1>
        <div class="flex space-x-3">
            <a href="{% url 'videos:record' %}"
               class="inline-flex items-center px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" stroke-width="2"/>
                    <circle cx="12" cy="12" r="4" fill="currentColor"/>
                </svg>
                Record
            </a>
            <a href="{% url 'videos:upload' %}"
               class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                Upload
            </a>
        </div>
    </div>

    {% if videos %}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {% for video in videos %}
        <a href="{% url 'videos:detail' video.pk %}"
           class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
            <div class="aspect-video bg-gray-100 relative">
                {% if video.thumbnail %}
                    <img src="{{ video.thumbnail.url }}" alt="{{ video.title }}"
                         class="w-full h-full object-cover">
                {% else %}
                    <div class="flex items-center justify-center h-full text-gray-400">
                        {% if video.status == 'processing' %}
                            <svg class="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                            </svg>
                        {% else %}
                            <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                            </svg>
                        {% endif %}
                    </div>
                {% endif %}
                {% if video.duration %}
                <span class="absolute bottom-2 right-2 bg-black bg-opacity-75 text-white text-xs px-1.5 py-0.5 rounded">
                    {{ video.duration|divisibleby:60 }}:{{ video.duration|divisibleby:60|stringformat:"02d" }}
                </span>
                {% endif %}
            </div>
            <div class="p-3">
                <h3 class="text-sm font-medium text-gray-900 truncate">{{ video.title }}</h3>
                <div class="flex items-center justify-between mt-1">
                    <span class="text-xs text-gray-500">{{ video.created_at|timesince }} ago</span>
                    <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                        {% if video.status == 'ready' %}bg-green-100 text-green-800
                        {% elif video.status == 'processing' %}bg-yellow-100 text-yellow-800
                        {% else %}bg-red-100 text-red-800{% endif %}">
                        {{ video.get_status_display }}
                    </span>
                </div>
                {% if video.storage_type == 'youtube' %}
                <span class="text-xs text-red-600 mt-1 inline-block">YouTube</span>
                {% endif %}
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No videos yet</h3>
        <p class="mt-1 text-sm text-gray-500">Record or upload your first video to get started.</p>
        <div class="mt-4 flex justify-center space-x-3">
            <a href="{% url 'videos:record' %}" class="inline-flex items-center px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700">Record</a>
            <a href="{% url 'videos:upload' %}" class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">Upload</a>
        </div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 2: Create video_upload.html**

```html
{% extends "base.html" %}
{% block title %}Upload Video{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="mb-6">
        <a href="{% url 'videos:list' %}" class="text-sm text-indigo-600 hover:text-indigo-800">&larr; Back to Videos</a>
    </div>
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h1 class="text-xl font-bold text-gray-900 mb-6">Upload Video</h1>
        <form method="post" enctype="multipart/form-data">
            {% csrf_token %}
            <div class="space-y-4">
                <div>
                    <label for="id_title" class="block text-sm font-medium text-gray-700">Title</label>
                    {{ form.title }}
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Save to</label>
                    <div class="flex space-x-4">
                        {% for radio in form.storage_type %}
                        <label class="flex items-center space-x-2 cursor-pointer">
                            {{ radio.tag }}
                            <span class="text-sm text-gray-700">{{ radio.choice_label }}</span>
                        </label>
                        {% endfor %}
                    </div>
                    <p class="mt-1 text-xs text-gray-500">Large files? Choose YouTube to save server space.</p>
                </div>
                <div>
                    <label for="id_video_file" class="block text-sm font-medium text-gray-700">Video File</label>
                    {{ form.video_file }}
                </div>
            </div>
            <div class="mt-6">
                <button type="submit"
                        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">
                    Upload
                </button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
```

**Step 3: Create video_detail.html (analytics + email snippet)**

```html
{% extends "base.html" %}
{% block title %}{{ video.title }}{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto">
    <div class="mb-6 flex items-center justify-between">
        <a href="{% url 'videos:list' %}" class="text-sm text-indigo-600 hover:text-indigo-800">&larr; Back to Videos</a>
        <div class="flex space-x-2">
            <a href="{% url 'videos:edit' video.pk %}"
               class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm rounded-md hover:bg-gray-50">Edit</a>
            <form method="post" action="{% url 'videos:delete' video.pk %}" onsubmit="return confirm('Delete this video?')">
                {% csrf_token %}
                <button class="inline-flex items-center px-3 py-1.5 border border-red-300 text-red-600 text-sm rounded-md hover:bg-red-50">Delete</button>
            </form>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Video Preview -->
        <div class="lg:col-span-2">
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                <div class="aspect-video bg-black">
                    {% if video.storage_type == 'youtube' and video.youtube_id %}
                        <iframe src="https://www.youtube.com/embed/{{ video.youtube_id }}"
                                class="w-full h-full" frameborder="0"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowfullscreen></iframe>
                    {% elif video.video_file %}
                        <video controls class="w-full h-full">
                            <source src="{{ video.video_file.url }}" type="video/mp4">
                        </video>
                    {% endif %}
                </div>
                <div class="p-4">
                    <h1 class="text-lg font-bold text-gray-900">{{ video.title }}</h1>
                    <div class="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                        <span>{{ video.created_at|date:"M j, Y" }}</span>
                        {% if video.duration %}<span>{{ video.duration }}s</span>{% endif %}
                        <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                            {% if video.storage_type == 'youtube' %}bg-red-100 text-red-800{% else %}bg-blue-100 text-blue-800{% endif %}">
                            {{ video.get_storage_type_display }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sidebar: Email Snippet + Stats -->
        <div class="space-y-4">
            <!-- Email Snippet -->
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-2">Email Snippet</h3>
                <p class="text-xs text-gray-500 mb-3">Copy and paste into Gmail to send a video email.</p>
                <div class="bg-gray-50 rounded p-2 text-xs font-mono text-gray-600 break-all max-h-24 overflow-y-auto mb-3">
                    {{ email_snippet|truncatechars:200 }}
                </div>
                <button onclick="copySnippet()" id="copy-btn"
                        class="w-full inline-flex justify-center items-center px-3 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">
                    Copy to Clipboard
                </button>
            </div>

            <!-- Stats -->
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-3">Analytics</h3>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-2xl font-bold text-gray-900">{{ total_views }}</p>
                        <p class="text-xs text-gray-500">Total Views</p>
                    </div>
                    <div>
                        <p class="text-2xl font-bold text-gray-900">{{ unique_viewers }}</p>
                        <p class="text-xs text-gray-500">Unique Contacts</p>
                    </div>
                </div>
            </div>

            <!-- Recent Views -->
            {% if recent_views %}
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-3">Recent Views</h3>
                <ul class="space-y-2">
                    {% for view in recent_views %}
                    <li class="flex items-center justify-between text-sm">
                        <span class="text-gray-700">
                            {% if view.contact %}
                                {{ view.contact }}
                            {% else %}
                                Anonymous ({{ view.ip_address }})
                            {% endif %}
                        </span>
                        <span class="text-xs text-gray-500">{{ view.watched_duration }}s</span>
                    </li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
    </div>
</div>

<script>
function copySnippet() {
    fetch("{% url 'videos:snippet' video.pk %}")
        .then(r => r.json())
        .then(data => {
            const blob = new Blob([data.snippet], {type: 'text/html'});
            const item = new ClipboardItem({'text/html': blob, 'text/plain': new Blob([data.snippet], {type: 'text/plain'})});
            navigator.clipboard.write([item]).then(() => {
                const btn = document.getElementById('copy-btn');
                btn.textContent = 'Copied!';
                setTimeout(() => btn.textContent = 'Copy to Clipboard', 2000);
            });
        });
}
</script>
{% endblock %}
```

**Step 4: Create video_edit.html**

```html
{% extends "base.html" %}
{% block title %}Edit {{ video.title }}{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="mb-6">
        <a href="{% url 'videos:detail' video.pk %}" class="text-sm text-indigo-600 hover:text-indigo-800">&larr; Back to Video</a>
    </div>
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h1 class="text-xl font-bold text-gray-900 mb-6">Edit Video</h1>
        <form method="post">
            {% csrf_token %}
            <div class="space-y-4">
                <div>
                    <label for="id_title" class="block text-sm font-medium text-gray-700">Title</label>
                    {{ form.title }}
                </div>
            </div>
            <div class="mt-6">
                <button type="submit"
                        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700">
                    Save
                </button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
```

**Step 5: Add sidebar link in base.html**

Find the sidebar `<nav>` section and add this link after the existing nav items (before the closing `</nav>`):

```html
<a href="/videos/"
   class="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-800 {% if '/videos/' in request.path %}bg-gray-800 text-white{% else %}text-gray-300{% endif %}">
    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
    </svg>
    Videos
</a>
```

**Step 6: Commit**

```bash
git add templates/videos/ templates/base.html
git commit -m "feat(videos): add video library templates and sidebar navigation"
```

---

## Phase 5: Webcam Recorder

### Task 5: Browser-based webcam recording page

**Files:**
- Create: `templates/videos/video_record.html`

**Step 1: Create video_record.html with MediaRecorder API**

```html
{% extends "base.html" %}
{% block title %}Record Video{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto">
    <div class="mb-6">
        <a href="{% url 'videos:list' %}" class="text-sm text-indigo-600 hover:text-indigo-800">&larr; Back to Videos</a>
    </div>

    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h1 class="text-xl font-bold text-gray-900 mb-6">Record Video</h1>

        <!-- Settings (before recording) -->
        <div id="settings-panel" class="mb-6 space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input type="text" id="video-title" placeholder="Give your video a name..."
                       class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Save to</label>
                <div class="flex space-x-4">
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input type="radio" name="storage" value="local" checked class="text-indigo-600">
                        <span class="text-sm text-gray-700">Server</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input type="radio" name="storage" value="youtube" class="text-indigo-600">
                        <span class="text-sm text-gray-700">YouTube</span>
                    </label>
                </div>
            </div>
        </div>

        <!-- Video preview -->
        <div class="aspect-video bg-black rounded-lg overflow-hidden mb-4">
            <video id="preview" autoplay muted playsinline class="w-full h-full object-cover"></video>
            <video id="playback" controls class="w-full h-full hidden"></video>
        </div>

        <!-- Timer -->
        <div id="timer" class="text-center text-lg font-mono text-gray-600 mb-4 hidden">00:00</div>

        <!-- Controls -->
        <div class="flex justify-center space-x-3">
            <button id="btn-start"
                    class="inline-flex items-center px-6 py-2 bg-red-600 text-white text-sm font-medium rounded-full hover:bg-red-700">
                <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>
                Start Recording
            </button>
            <button id="btn-stop"
                    class="inline-flex items-center px-6 py-2 bg-gray-600 text-white text-sm font-medium rounded-full hover:bg-gray-700 hidden">
                <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
                Stop
            </button>
            <button id="btn-redo"
                    class="inline-flex items-center px-6 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-full hover:bg-gray-50 hidden">
                Re-record
            </button>
            <button id="btn-save"
                    class="inline-flex items-center px-6 py-2 bg-indigo-600 text-white text-sm font-medium rounded-full hover:bg-indigo-700 hidden">
                Save Video
            </button>
        </div>

        <!-- Status -->
        <div id="status" class="text-center text-sm text-gray-500 mt-4"></div>
    </div>
</div>

<script>
let mediaRecorder, chunks = [], stream, timerInterval, seconds = 0;

const preview = document.getElementById('preview');
const playback = document.getElementById('playback');
const timer = document.getElementById('timer');
const status = document.getElementById('status');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const btnRedo = document.getElementById('btn-redo');
const btnSave = document.getElementById('btn-save');

async function initCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({video: true, audio: true});
        preview.srcObject = stream;
    } catch (err) {
        status.textContent = 'Camera access denied. Please allow camera permissions.';
    }
}

btnStart.addEventListener('click', () => {
    chunks = [];
    seconds = 0;
    mediaRecorder = new MediaRecorder(stream, {mimeType: 'video/webm'});
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    mediaRecorder.onstop = onRecordingStop;
    mediaRecorder.start(1000);

    btnStart.classList.add('hidden');
    btnStop.classList.remove('hidden');
    timer.classList.remove('hidden');
    timerInterval = setInterval(() => {
        seconds++;
        const m = String(Math.floor(seconds / 60)).padStart(2, '0');
        const s = String(seconds % 60).padStart(2, '0');
        timer.textContent = `${m}:${s}`;
    }, 1000);
});

btnStop.addEventListener('click', () => {
    mediaRecorder.stop();
    clearInterval(timerInterval);
    btnStop.classList.add('hidden');
});

function onRecordingStop() {
    const blob = new Blob(chunks, {type: 'video/webm'});
    playback.src = URL.createObjectURL(blob);
    preview.classList.add('hidden');
    playback.classList.remove('hidden');
    btnRedo.classList.remove('hidden');
    btnSave.classList.remove('hidden');
}

btnRedo.addEventListener('click', () => {
    playback.classList.add('hidden');
    preview.classList.remove('hidden');
    btnRedo.classList.add('hidden');
    btnSave.classList.add('hidden');
    btnStart.classList.remove('hidden');
    timer.classList.add('hidden');
    seconds = 0;
    timer.textContent = '00:00';
});

btnSave.addEventListener('click', async () => {
    const blob = new Blob(chunks, {type: 'video/webm'});
    const title = document.getElementById('video-title').value || 'Untitled Recording';
    const storage = document.querySelector('input[name="storage"]:checked').value;

    const formData = new FormData();
    formData.append('video', blob, 'recording.webm');
    formData.append('title', title);
    formData.append('storage_type', storage);

    btnSave.disabled = true;
    btnSave.textContent = 'Saving...';
    status.textContent = 'Uploading video...';

    try {
        const resp = await fetch("{% url 'videos:record_save' %}", {
            method: 'POST',
            headers: {'X-CSRFToken': '{{ csrf_token }}'},
            body: formData,
        });
        const data = await resp.json();
        if (data.redirect) {
            window.location.href = data.redirect;
        }
    } catch (err) {
        status.textContent = 'Upload failed. Please try again.';
        btnSave.disabled = false;
        btnSave.textContent = 'Save Video';
    }
});

initCamera();
</script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/videos/video_record.html
git commit -m "feat(videos): add webcam recorder with MediaRecorder API"
```

---

## Phase 6: Public Landing Page

### Task 6: Video landing page template with watch tracking

**Files:**
- Create: `templates/videos/video_landing.html`

**Step 1: Create video_landing.html (public, no base.html extend)**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ video.title }} - Big Beach AL</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="max-w-3xl mx-auto py-8 px-4">
        <!-- Logo / Branding -->
        <div class="text-center mb-6">
            <h2 class="text-lg font-bold text-gray-800">Big Beach AL</h2>
        </div>

        <!-- Video Player -->
        <div class="bg-white rounded-xl shadow-lg overflow-hidden">
            <div class="aspect-video bg-black">
                {% if video.storage_type == 'youtube' and video.youtube_id %}
                    <iframe id="yt-player"
                            src="https://www.youtube.com/embed/{{ video.youtube_id }}?enablejsapi=1"
                            class="w-full h-full" frameborder="0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowfullscreen></iframe>
                {% elif video.video_file %}
                    <video id="video-player" controls class="w-full h-full">
                        <source src="{{ video.video_file.url }}" type="video/mp4">
                    </video>
                {% endif %}
            </div>
            <div class="p-6">
                <h1 class="text-xl font-bold text-gray-900">{{ video.title }}</h1>
            </div>
        </div>

        <!-- Footer -->
        <div class="text-center mt-8 text-sm text-gray-400">
            Sent with Big Beach AL CRM
        </div>
    </div>

    <script>
    (function() {
        const token = '{{ tracking_token }}';
        const trackUrl = '/v/{{ video.uuid }}/track/';
        let lastReported = 0;

        function sendProgress(duration) {
            if (duration <= lastReported) return;
            lastReported = duration;
            navigator.sendBeacon(trackUrl, JSON.stringify({
                duration: Math.round(duration),
                token: token || null,
            }));
        }

        // HTML5 video tracking
        const player = document.getElementById('video-player');
        if (player) {
            let interval;
            player.addEventListener('play', () => {
                interval = setInterval(() => sendProgress(player.currentTime), 10000);
            });
            player.addEventListener('pause', () => {
                clearInterval(interval);
                sendProgress(player.currentTime);
            });
            player.addEventListener('ended', () => {
                clearInterval(interval);
                sendProgress(player.duration);
            });
        }
    })();
    </script>
</body>
</html>
```

**Step 2: Commit**

```bash
git add templates/videos/video_landing.html
git commit -m "feat(videos): add public landing page with watch progress tracking"
```

---

## Phase 7: YouTube Upload Integration

### Task 7: YouTube Data API upload via Celery

**Files:**
- Create: `apps/videos/youtube.py`
- Modify: `apps/videos/tasks.py` (add YouTube upload path)

**Step 1: Create youtube.py helper**

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload_to_youtube(video_path, title, credentials_dict):
    """Upload a video to YouTube as unlisted. Returns the YouTube video ID."""
    creds = Credentials(
        token=credentials_dict['access_token'],
        refresh_token=credentials_dict.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=credentials_dict['client_id'],
        client_secret=credentials_dict['client_secret'],
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
    )

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': f'Video email from Big Beach AL CRM',
            'categoryId': '22',  # People & Blogs
        },
        'status': {
            'privacyStatus': 'unlisted',
        },
    }

    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = request.execute()
    return response['id']
```

**Step 2: Update tasks.py to handle YouTube uploads**

Add to the `process_video` task, after the WebM→MP4 conversion and thumbnail generation:

```python
# At the end of the try block, after thumbnail generation:

if video.storage_type == Video.STORAGE_YOUTUBE:
    from .youtube import upload_to_youtube
    # Get OAuth credentials from the user's account
    user = video.created_by
    if hasattr(user, 'gmail_access_token') and user.gmail_refresh_token:
        from django.conf import settings as django_settings
        creds = {
            'access_token': user.gmail_access_token,
            'refresh_token': user.gmail_refresh_token,
            'client_id': django_settings.GOOGLE_CLIENT_ID,
            'client_secret': django_settings.GOOGLE_CLIENT_SECRET,
        }
        video.youtube_id = upload_to_youtube(video_path, video.title, creds)
        # Remove local video file after YouTube upload to save space
        if os.path.exists(video_path):
            os.remove(video_path)
        video.video_file = None
```

**Note:** YouTube Data API scope (`https://www.googleapis.com/auth/youtube.upload`) needs to be added to the Google OAuth consent screen and the allauth social login config. The exact fields for Gmail credentials on the User model should be verified during implementation.

**Step 3: Add `google-api-python-client` to requirements.txt**

Check if already installed (used for Gmail API). If not:
```
google-api-python-client
```

**Step 4: Commit**

```bash
git add apps/videos/youtube.py apps/videos/tasks.py requirements.txt
git commit -m "feat(videos): add YouTube unlisted upload via Data API"
```

---

## Phase 8: Campaign Integration

### Task 8: Link videos to campaign email steps

**Files:**
- Modify: `apps/campaigns/models.py` (add Video FK to CampaignStep)
- Modify: `apps/campaigns/forms.py` (add video picker)
- Modify: campaign step templates (show video thumbnail in email)

**Step 1: Add Video FK to CampaignStep**

In `apps/campaigns/models.py`, add to CampaignStep:
```python
video = models.ForeignKey(
    'videos.Video',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='campaign_steps',
)
```

**Step 2: Run makemigrations**

```bash
python manage.py makemigrations campaigns
python manage.py migrate
```

**Step 3: Update campaign step form to include video picker**

Add `video` to the CampaignStep form fields. Use a select widget filtered to ready videos from the user's team.

**Step 4: Update campaign email rendering**

When a CampaignStep has a linked video, insert the thumbnail+tracked link into the email HTML. Generate a unique VideoView tracking token per recipient:

```python
from apps.videos.models import VideoView

# In the email sending logic for each recipient:
if step.video:
    view = VideoView.objects.create(
        video=step.video,
        contact=recipient_contact,
    )
    tracked_url = f"https://crm.bigbeachal.com/v/{step.video.uuid}?t={view.tracking_token}"
    thumb_url = step.video.get_thumbnail_url()
    video_html = (
        f'<a href="{tracked_url}">'
        f'<img src="{thumb_url}" alt="Click to watch" style="max-width:100%;border-radius:8px;">'
        f'</a>'
    )
    # Insert video_html into the email body
```

**Step 5: Commit**

```bash
git add apps/campaigns/ apps/videos/
git commit -m "feat(videos): integrate video picker into campaign email steps with per-recipient tracking"
```

---

## Phase 9: Server Setup

### Task 9: Install ffmpeg on the DigitalOcean server

**Step 1: SSH into server and install ffmpeg**

```bash
ssh root@157.245.89.79
apt-get update && apt-get install -y ffmpeg
ffmpeg -version  # verify
```

**Step 2: Add YouTube upload scope to Google OAuth config**

In Django admin or settings, add `https://www.googleapis.com/auth/youtube.upload` to the Google OAuth scopes. This requires updating the Google Cloud Console OAuth consent screen to include the YouTube Data API scope.

**Step 3: Deploy the new code**

```bash
cd /opt/crm
git pull
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart gunicorn
```

**Step 4: Create media directories**

```bash
mkdir -p /opt/crm/media/videos
mkdir -p /opt/crm/media/video_thumbnails
```

**Step 5: Commit any server config changes**

No code commit needed for this task — it's infrastructure setup.

---

## Summary

| Phase | Task | Description |
|-------|------|-------------|
| 1 | Task 1 | App skeleton, models, admin, settings registration |
| 2 | Task 2 | ffmpeg processing + Celery thumbnail task |
| 3 | Task 3 | Forms, views, URL routing |
| 4 | Task 4 | Templates: list, upload, detail, edit + sidebar |
| 5 | Task 5 | Webcam recorder (MediaRecorder API) |
| 6 | Task 6 | Public landing page with watch tracking |
| 7 | Task 7 | YouTube upload integration |
| 8 | Task 8 | Campaign step video integration |
| 9 | Task 9 | Server deployment (ffmpeg, OAuth, deploy) |
