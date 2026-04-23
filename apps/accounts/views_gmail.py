import os

from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow

# Allow OAuth over HTTP (before SSL is set up)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' if not getattr(settings, 'SECURE_SSL_REDIRECT', False) else '0'
# Tolerate Google dropping unverified scopes (e.g. youtube) from the consent grant.
# Without this, oauthlib raises on any scope mismatch and the callback 500s.
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/youtube',
]


def _build_flow(request, state=None, code_verifier=None):
    """Build a Google OAuth Flow instance."""
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=request.build_absolute_uri('/accounts/gmail/callback/'),
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    return flow


@login_required
def gmail_connect(request):
    """Redirect user to Google OAuth consent screen."""
    flow = _build_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline', prompt='consent'
    )
    request.session['gmail_oauth_state'] = state
    request.session['gmail_code_verifier'] = flow.code_verifier
    return redirect(authorization_url)


@login_required
def gmail_callback(request):
    """Handle OAuth callback, store tokens."""
    state = request.session.get('gmail_oauth_state')
    code_verifier = request.session.get('gmail_code_verifier')
    flow = _build_flow(request, state=state, code_verifier=code_verifier)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials

    user = request.user
    user.gmail_access_token = credentials.token
    user.gmail_refresh_token = credentials.refresh_token
    user.gmail_token_expiry = credentials.expiry
    user.gmail_connected = True
    user.save()

    return redirect('accounts:profile')


@login_required
def gmail_disconnect(request):
    """Disconnect Gmail."""
    if request.method == 'POST':
        user = request.user
        user.gmail_access_token = ''
        user.gmail_refresh_token = ''
        user.gmail_token_expiry = None
        user.gmail_connected = False
        user.save()
    return redirect('accounts:profile')
