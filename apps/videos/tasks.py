import os
import tempfile

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

        if video.storage_type == Video.STORAGE_YOUTUBE:
            from .youtube import upload_to_youtube
            from django.conf import settings as django_settings
            user = video.created_by
            if user and user.gmail_access_token and user.gmail_refresh_token:
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

        video.status = Video.STATUS_READY
        video.save()

    except Exception:
        video.status = Video.STATUS_FAILED
        video.save()
        raise
