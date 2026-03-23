from django.conf import settings
from django.template.loader import render_to_string

from apps.accounts.gmail import GmailService


def _get_gmail_service(user):
    """Build a GmailService from the user's OAuth credentials."""
    return GmailService(
        access_token=user.gmail_access_token,
        refresh_token=user.gmail_refresh_token,
    )


def send_signing_request(signer, sender):
    """Send signing request email via Gmail OAuth.

    Args:
        signer: DocumentSigner instance
        sender: User instance (document creator) whose Gmail credentials to use
    """
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    signing_url = f"{base_url}{signer.get_signing_url()}"
    context = {
        'signer': signer,
        'document': signer.document,
        'signing_url': signing_url,
    }
    html = render_to_string('signatures/emails/signing_request.html', context)
    gmail = _get_gmail_service(sender)
    gmail.send_email(
        to=signer.email,
        subject=f"Please sign: {signer.document.title}",
        body_html=html,
        from_email=sender.email,
    )


def send_completion_notification(document):
    """Notify document creator that all signers have completed."""
    if not document.created_by:
        return
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    context = {
        'document': document,
        'download_url': f"{base_url}/signatures/{document.pk}/download/",
    }
    html = render_to_string('signatures/emails/signing_complete.html', context)
    sender = document.created_by
    gmail = _get_gmail_service(sender)
    gmail.send_email(
        to=sender.email,
        subject=f"Completed: {document.title}",
        body_html=html,
        from_email=sender.email,
    )


def send_signer_confirmation(signer):
    """Send confirmation to signer after they've signed."""
    sender = signer.document.created_by
    if not sender:
        return
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    context = {
        'signer': signer,
        'document': signer.document,
    }
    html = render_to_string('signatures/emails/signer_confirmation.html', context)
    gmail = _get_gmail_service(sender)
    gmail.send_email(
        to=signer.email,
        subject=f"Signed: {signer.document.title}",
        body_html=html,
        from_email=sender.email,
    )
