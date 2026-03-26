import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models
from django.urls import reverse


class Course(models.Model):
    UNLOCK_MODE_CHOICES = [
        ('time_drip', 'Time Drip'),
        ('completion_based', 'Completion Based'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_taught',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='courses',
    )
    unlock_mode = models.CharField(
        max_length=20,
        choices=UNLOCK_MODE_CHOICES,
        default='completion_based',
    )
    drip_interval_days = models.PositiveIntegerField(default=7)
    is_published = models.BooleanField(default=False)
    is_free = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('portal:course_detail', kwargs={'slug': self.slug})

    @property
    def total_modules(self):
        return self.modules.count()

    @property
    def total_lessons(self):
        return Lesson.objects.filter(module__course=self).count()


class Module(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']

    def __str__(self):
        return f'{self.course.title} - {self.title}'

    @property
    def total_lessons(self):
        return self.lessons.count()


class Lesson(models.Model):
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text='Lesson notes (HTML allowed)')
    video_url = models.URLField(blank=True)
    pdf_file = models.FileField(upload_to='courses/pdfs/', blank=True)
    order = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['module', 'order']

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        """Convert YouTube/Vimeo URLs to embed format."""
        url = self.video_url
        if not url:
            return ''

        # Already an embed URL
        if '/embed/' in url or 'player.vimeo.com' in url:
            return url

        parsed = urlparse(url)

        # youtube.com/watch?v=ID
        if parsed.hostname in ('www.youtube.com', 'youtube.com'):
            qs = parse_qs(parsed.query)
            video_id = qs.get('v', [None])[0]
            if video_id:
                return f'https://www.youtube-nocookie.com/embed/{video_id}'

        # youtu.be/ID
        if parsed.hostname == 'youtu.be':
            video_id = parsed.path.lstrip('/').split('?')[0]
            if video_id:
                return f'https://www.youtube-nocookie.com/embed/{video_id}'

        # vimeo.com/ID
        if parsed.hostname in ('www.vimeo.com', 'vimeo.com'):
            video_id = parsed.path.lstrip('/')
            if video_id:
                return f'https://player.vimeo.com/video/{video_id}'

        return url


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    current_module_unlocked = models.PositiveIntegerField(default=1)
    next_unlock_date = models.DateTimeField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, blank=True, default='free')
    stripe_payment_id = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f'{self.student} enrolled in {self.course}'

    def is_module_unlocked(self, module_order):
        """Check if a module is unlocked for this enrollment."""
        return module_order <= self.current_module_unlocked

    def unlock_next_module(self):
        """Unlock the next module in sequence."""
        self.current_module_unlocked += 1
        self.save(update_fields=['current_module_unlocked'])

    @property
    def progress_percent(self):
        """Calculate completion percentage based on completed lessons."""
        total = Lesson.objects.filter(module__course=self.course).count()
        if total == 0:
            return 0
        completed = LessonProgress.objects.filter(
            student=self.student,
            lesson__module__course=self.course,
            is_completed=True,
        ).count()
        return int((completed / total) * 100)


class LessonProgress(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ['student', 'lesson']

    def __str__(self):
        status = 'completed' if self.is_completed else 'in progress'
        return f'{self.student} - {self.lesson} ({status})'


class Announcement(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='announcements',
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_announcements',
    )
    send_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
