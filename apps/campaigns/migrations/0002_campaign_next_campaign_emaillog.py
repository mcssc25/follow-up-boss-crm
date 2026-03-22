import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='next_campaign',
            field=models.ForeignKey(
                blank=True,
                help_text='Campaign to auto-enroll contacts in after this one completes.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='previous_campaigns',
                to='campaigns.campaign',
            ),
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_logs', to='campaigns.campaignenrollment')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_logs', to='campaigns.campaignstep')),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
    ]
