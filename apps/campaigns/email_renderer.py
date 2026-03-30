def render_campaign_email(body, contact, agent):
    """Replace merge field placeholders with actual contact/agent values."""
    replacements = {
        '{{first_name}}': contact.first_name,
        '{{last_name}}': contact.last_name,
        '{{full_name}}': f"{contact.first_name} {contact.last_name}",
        '{{agent_name}}': agent.get_full_name() or agent.username,
        '{{agent_phone}}': getattr(agent, 'phone', ''),
        '{{agent_email}}': agent.email,
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value or '')
    return body


def get_video_html(step, contact, base_url):
    """Generate a clickable video thumbnail block for campaign emails."""
    # New Video model (preferred)
    if step.video and step.video.status == 'ready':
        from apps.videos.models import VideoView
        # Create a tracked view record for this recipient
        view = VideoView.objects.create(
            video=step.video,
            contact=contact,
        )
        tracked_url = f"{base_url}/v/{step.video.uuid}?t={view.tracking_token}"
        thumb_url = step.video.get_thumbnail_url()
        if thumb_url:
            return (
                '<div style="text-align: center; margin: 20px 0;">'
                f'<a href="{tracked_url}" style="display: inline-block; text-decoration: none;">'
                f'<img src="{thumb_url}" alt="Click to watch video" '
                f'style="max-width: 100%; border-radius: 8px;" />'
                '</a>'
                '</div>'
            )
        else:
            return (
                '<div style="text-align: center; margin: 20px 0;">'
                f'<a href="{tracked_url}" style="display: inline-block; text-decoration: none;">'
                '<div style="background: #000; padding: 40px 80px; border-radius: 8px; display: inline-block;">'
                '<span style="font-size: 48px; color: #fff;">&#9654;</span>'
                '<p style="color: #fff; margin-top: 10px; font-family: Arial, sans-serif;">'
                'Click to watch video</p>'
                '</div>'
                '</a>'
                '</div>'
            )

    # Legacy: old video_file field (no tracking)
    if step.video_file:
        video_url = f"{base_url}/campaigns/video/{step.id}/{contact.id}/"
        return (
            '<div style="text-align: center; margin: 20px 0;">'
            f'<a href="{video_url}" style="display: inline-block; text-decoration: none;">'
            '<div style="background: #000; padding: 40px 80px; border-radius: 8px; display: inline-block;">'
            '<span style="font-size: 48px; color: #fff;">&#9654;</span>'
            '<p style="color: #fff; margin-top: 10px; font-family: Arial, sans-serif;">'
            'Click to watch video</p>'
            '</div>'
            '</a>'
            '</div>'
        )

    return ''
