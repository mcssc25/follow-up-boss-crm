from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('signatures', '0012_documentfield_bold_documentfield_font_size_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='email_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]
