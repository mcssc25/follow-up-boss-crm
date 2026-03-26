from celery import shared_task
from django.utils import timezone


@shared_task
def process_drip_unlocks():
    """Check all time_drip enrollments and unlock modules where next_unlock_date has passed."""
    from .models import Enrollment

    due_enrollments = Enrollment.objects.filter(
        course__unlock_mode='time_drip',
        next_unlock_date__lte=timezone.now(),
        next_unlock_date__isnull=False,
    ).select_related('course')

    unlocked = 0
    for enrollment in due_enrollments:
        if enrollment.current_module_unlocked < enrollment.course.total_modules:
            enrollment.current_module_unlocked += 1
            enrollment.next_unlock_date = timezone.now() + timezone.timedelta(
                days=enrollment.course.drip_interval_days
            )
            enrollment.save()
            unlocked += 1
        else:
            enrollment.next_unlock_date = None
            enrollment.save()

    return f'{unlocked} module(s) unlocked'


@shared_task
def send_announcement_email(announcement_pk):
    """Send announcement email to all enrolled students."""
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from .models import Announcement

    announcement = Announcement.objects.select_related('course').get(pk=announcement_pk)
    enrolled_emails = list(
        announcement.course.enrollments.values_list('student__email', flat=True)
    )

    if not enrolled_emails:
        return 'No enrolled students'

    send_mail(
        subject=f'[{announcement.course.title}] {announcement.title}',
        message=announcement.body,
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=enrolled_emails,
        fail_silently=True,
    )

    return f'Sent to {len(enrolled_emails)} student(s)'
