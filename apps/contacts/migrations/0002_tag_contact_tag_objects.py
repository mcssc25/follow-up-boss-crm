from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('color', models.CharField(default='#6366f1', help_text='Hex color code, e.g. #6366f1', max_length=7)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='accounts.team')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('name', 'team')},
            },
        ),
        migrations.AddField(
            model_name='contact',
            name='tag_objects',
            field=models.ManyToManyField(blank=True, related_name='contacts', to='contacts.tag'),
        ),
    ]
