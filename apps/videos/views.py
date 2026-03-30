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
    # Delete from YouTube if applicable
    if video.storage_type == Video.STORAGE_YOUTUBE and video.youtube_id:
        try:
            from .youtube import delete_from_youtube
            from django.conf import settings as django_settings
            user = request.user
            if user.gmail_access_token and user.gmail_refresh_token:
                delete_from_youtube(video.youtube_id, {
                    'access_token': user.gmail_access_token,
                    'refresh_token': user.gmail_refresh_token,
                    'client_id': django_settings.GOOGLE_CLIENT_ID,
                    'client_secret': django_settings.GOOGLE_CLIENT_SECRET,
                })
        except Exception:
            pass  # Still delete from CRM even if YouTube delete fails
    video.delete()
    messages.success(request, 'Video deleted.')
    return redirect('videos:list')


@login_required
def video_snippet(request, pk):
    """Return email snippet HTML as JSON."""
    video = get_object_or_404(Video, pk=pk, team=request.user.team)
    return JsonResponse({'snippet': video.get_email_snippet()})


@login_required
@require_POST
def video_push_to_youtube(request, pk):
    """Push a local video to YouTube."""
    video = get_object_or_404(Video, pk=pk, team=request.user.team)
    if video.storage_type != Video.STORAGE_LOCAL or not video.video_file:
        messages.error(request, 'This video is not stored locally.')
        return redirect('videos:detail', pk=video.pk)
    from .tasks import push_to_youtube_task
    push_to_youtube_task.delay(video.id, request.user.id)
    messages.success(request, 'Uploading to YouTube in the background. This may take a minute.')
    return redirect('videos:detail', pk=video.pk)


# --- Public views (no login required) ---

def video_landing(request, uuid):
    """Public landing page for watching a video."""
    video = get_object_or_404(Video, uuid=uuid, status=Video.STATUS_READY)

    # Check for tracking token
    tracking_token = request.GET.get('t')
    contact = None
    if tracking_token:
        try:
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

    # Send push notification to video creator
    if video.created_by:
        from apps.pwa.push import send_push_notification
        if contact:
            body = f'{contact} watched your video "{video.title}"'
        else:
            body = f'Someone watched your video "{video.title}"'
        send_push_notification(
            video.created_by,
            'Video Viewed',
            body,
            url=video.get_absolute_url(),
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
