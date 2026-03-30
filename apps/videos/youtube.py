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
            'description': 'Video email from Big Beach AL CRM',
            'categoryId': '22',
        },
        'status': {
            'privacyStatus': 'unlisted',
            'embeddable': True,
        },
    }

    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = request.execute()
    return response['id']
