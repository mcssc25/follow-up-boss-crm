import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0001_initial'),
        ('contacts', '0002_tag_contact_tag_objects'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('duration_minutes', models.PositiveIntegerField(default=30)),
                ('color', models.CharField(default='#6366f1', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('min_advance_hours', models.PositiveIntegerField(default=24, help_text='Minimum hours in advance a booking can be made')),
                ('buffer_minutes', models.PositiveIntegerField(default=10, help_text='Buffer time between appointments')),
                ('timezone', models.CharField(default='America/Chicago', help_text='Timezone for availability display', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_types', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_types', to='accounts.team')),
                ('tags', models.ManyToManyField(blank=True, related_name='event_types', to='contacts.tag')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Availability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('event_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availabilities', to='scheduling.eventtype')),
            ],
            options={
                'ordering': ['day_of_week', 'start_time'],
                'verbose_name_plural': 'availabilities',
                'unique_together': {('event_type', 'day_of_week')},
            },
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone_number', models.CharField(max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('cancelled', 'Cancelled'), ('completed', 'Completed'), ('no_show', 'No Show')], default='scheduled', max_length=20)),
                ('cancel_token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('google_event_id', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='contacts.contact')),
                ('event_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='scheduling.eventtype')),
            ],
            options={
                'ordering': ['start_time'],
            },
        ),
    ]
