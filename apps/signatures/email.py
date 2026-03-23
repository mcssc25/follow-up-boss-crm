from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_signing_request(signer):
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    signing_url = f"{base_url}{signer.get_signing_url()}"
    context = {
        'signer': signer,
        'document': signer.document,
        'signing_url': signing_url,
    }
    html = render_to_string('signatures/emails/signing_request.html', context)
    send_mail(
        subject=f"Please sign: {signer.document.title}",
        message=f"You have a document to sign. Visit: {signing_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[signer.email],
        html_message=html,
    )


def send_completion_notification(document):
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    context = {
        'document': document,
        'download_url': f"{base_url}/signatures/{document.pk}/download/",
    }
    html = render_to_string('signatures/emails/signing_complete.html', context)
    if document.created_by:
        send_mail(
            subject=f"Completed: {document.title}",
            message=f"All signers have completed {document.title}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[document.created_by.email],
            html_message=html,
        )


def send_signer_confirmation(signer):
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    context = {
        'signer': signer,
        'document': signer.document,
    }
    html = render_to_string('signatures/emails/signer_confirmation.html', context)
    send_mail(
        subject=f"Signed: {signer.document.title}",
        message=f"You have successfully signed {signer.document.title}.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[signer.email],
        html_message=html,
    )
