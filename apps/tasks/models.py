from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Task(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed')]
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    due_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    google_event_id = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return self.status == 'pending' and self.due_date < timezone.now()

    def complete(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


def validate_file_size(value):
    limit = 50 * 1024 * 1024  # 50MB
    if value.size > limit:
        raise ValidationError('File size must be under 50 MB.')


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(
        upload_to='task_attachments/',
        validators=[validate_file_size],
    )
    filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.filename

    @property
    def size_display(self):
        try:
            size = self.file.size
        except (FileNotFoundError, OSError):
            return "N/A"
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
