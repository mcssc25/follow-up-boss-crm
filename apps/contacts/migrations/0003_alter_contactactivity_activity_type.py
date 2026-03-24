from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0002_tag_contact_tag_objects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactactivity',
            name='activity_type',
            field=models.CharField(
                choices=[
                    ('email_sent', 'Email Sent'),
                    ('email_opened', 'Email Opened'),
                    ('email_replied', 'Email Replied'),
                    ('call_logged', 'Call Logged'),
                    ('call_scheduled', 'Call Scheduled'),
                    ('note_added', 'Note Added'),
                    ('stage_changed', 'Stage Changed'),
                    ('campaign_enrolled', 'Campaign Enrolled'),
                    ('video_viewed', 'Video Viewed'),
                ],
                max_length=20,
            ),
        ),
    ]
