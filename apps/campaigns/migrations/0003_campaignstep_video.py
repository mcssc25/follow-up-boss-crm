import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0002_campaign_next_campaign_emaillog'),
        ('videos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaignstep',
            name='video',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='campaign_steps',
                to='videos.video',
            ),
        ),
    ]
