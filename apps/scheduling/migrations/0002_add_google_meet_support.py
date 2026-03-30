from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='location_type',
            field=models.CharField(
                choices=[('phone', 'Phone Call'), ('google_meet', 'Google Meet')],
                default='phone',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='google_meet_url',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='booking',
            name='reminder_24h_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='booking',
            name='reminder_1h_sent',
            field=models.BooleanField(default=False),
        ),
    ]
