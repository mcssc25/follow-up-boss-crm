from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='preview_gif',
            field=models.FileField(blank=True, null=True, upload_to='video_thumbnails/'),
        ),
    ]
