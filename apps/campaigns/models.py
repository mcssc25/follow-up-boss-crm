import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='campaigns',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    next_campaign = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_campaigns',
        help_text='Campaign to auto-enroll contacts in after this one completes.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('campaigns:detail', kwargs={'pk': self.pk})

    def duplicate(self):
        """Create a copy of this campaign with all steps."""
        new_campaign = Campaign.objects.create(
            name=f"{self.name} (Copy)",
            description=self.description,
            team=self.team,
            created_by=self.created_by,
            is_active=False,
        )
        for step in self.steps.all():
            CampaignStep.objects.create(
                campaign=new_campaign,
                order=step.order,
                delay_days=step.delay_days,
                delay_hours=step.delay_hours,
                subject=step.subject,
                body=step.body,
                video_file=step.video_file if step.video_file else None,
            )
        return new_campaign


class CampaignStep(models.Model):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    order = models.PositiveIntegerField()
    delay_days = models.PositiveIntegerField(default=0)
    delay_hours = models.PositiveIntegerField(default=0)
    subject = models.CharField(max_length=200)
    body = models.TextField(
        help_text="HTML email body. Use {{first_name}}, {{agent_name}}, {{agent_phone}} for merge fields.",
    )
    video_file = models.FileField(upload_to='campaign_videos/', blank=True, null=True)
    video_thumbnail = models.ImageField(upload_to='campaign_thumbnails/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.campaign.name} - Step {self.order}"

    @property
    def total_delay_hours(self):
        return (self.delay_days * 24) + self.delay_hours


class CampaignEnrollment(models.Model):
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    current_step = models.ForeignKey(
        CampaignStep,
        on_delete=models.SET_NULL,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    paused_reason = models.CharField(max_length=100, blank=True)
    next_send_at = models.DateTimeField(null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.contact} enrolled in {self.campaign}"

    def pause(self, reason=""):
        self.is_active = False
        self.paused_reason = reason
        self.save()

    def resume(self):
        self.is_active = True
        self.paused_reason = ""
        self.next_send_at = timezone.now()
        self.save()

    def advance_to_next_step(self):
        next_steps = self.campaign.steps.filter(order__gt=self.current_step.order)
        if next_steps.exists():
            next_step = next_steps.first()
            self.current_step = next_step
            self.next_send_at = timezone.now() + timedelta(hours=next_step.total_delay_hours)
            self.save()
        else:
            self.is_active = False
            self.completed_at = timezone.now()
            self.save()
            # Auto-enroll in next campaign if configured
            if self.campaign.next_campaign and self.campaign.next_campaign.is_active:
                next_camp = self.campaign.next_campaign
                first_step = next_camp.steps.first()
                if first_step:
                    CampaignEnrollment.objects.create(
                        contact=self.contact,
                        campaign=next_camp,
                        current_step=first_step,
                        next_send_at=timezone.now(),
                    )


class EmailLog(models.Model):
    """Tracks individual email sends with open/click tracking."""
    enrollment = models.ForeignKey(
        CampaignEnrollment,
        on_delete=models.CASCADE,
        related_name='email_logs',
    )
    step = models.ForeignKey(
        CampaignStep,
        on_delete=models.CASCADE,
        related_name='email_logs',
    )
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Email {self.tracking_id} - Step {self.step.order}"
