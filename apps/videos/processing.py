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
