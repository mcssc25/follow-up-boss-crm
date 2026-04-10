from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0002_alter_socialaccount_access_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='keywordtrigger',
            name='response_type',
            field=models.CharField(
                choices=[
                    ('message', 'Send DM'),
                    ('private_reply', 'Private Reply to Comment'),
                ],
                default='message',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='keywordtrigger',
            name='trigger_event',
            field=models.CharField(
                choices=[
                    ('message', 'DM'),
                    ('comment', 'Comment'),
                    ('both', 'DM or Comment'),
                ],
                default='message',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='comment_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='event_type',
            field=models.CharField(
                choices=[('message', 'DM'), ('comment', 'Comment')],
                default='message',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='external_event_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='post_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='raw_payload',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='reply_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='socialaccount',
            name='app_subscribed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='socialaccount',
            name='last_webhook_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='socialaccount',
            name='last_webhook_error',
            field=models.TextField(blank=True, default=''),
        ),
    ]
