import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class EventType(models.Model):
    LOCATION_CHOICES = [
        ('phone', 'Phone Call'),
        ('google_meet', 'Google Meet'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_CHOICES, default='phone')
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_types')
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='event_types')
    tags = models.ManyToManyField('contacts.Tag', blank=True, related_name='event_types')
    color = models.CharField(max_length=7, default='#6366f1')
    is_active = models.BooleanField(default=True)
    min_advance_hours = models.PositiveIntegerField(default=24, help_text='Minimum hours in advance a booking can be made')
    buffer_minutes = models.PositiveIntegerField(default=10, help_text='Buffer time between appointments')
    timezone = models.CharField(max_length=50, default='America/Chicago', help_text='Timezone for availability display')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('scheduling:public_booking', kwargs={'slug': self.slug})

    def get_booking_url(self):
        return f"/schedule/{self.slug}/"


class Availability(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name_plural = 'availabilities'
        unique_together = ['event_type', 'day_of_week']

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'), ('cancelled', 'Cancelled'),
        ('completed', 'Completed'), ('no_show', 'No Show'),
    ]
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='bookings')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    cancel_token = models.UUIDField(default=uuid.uuid4, unique=True)
    google_event_id = models.CharField(max_length=255, blank=True)
    google_meet_url = models.URLField(max_length=500, blank=True)
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.start_time}"

    def get_cancel_url(self):
        return reverse('scheduling:cancel_booking', kwargs={'token': self.cancel_token})

    def get_reschedule_url(self):
        return reverse('scheduling:reschedule_booking', kwargs={'token': self.cancel_token})
