"""
Step 3: Remove old assigned_to FK and google_event_id, add new M2M field.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0005_migrate_assigned_to_data"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Remove the old FK
        migrations.RemoveField(
            model_name="task",
            name="assigned_to_old",
        ),
        # Remove google_event_id from Task (now on TaskAssignment)
        migrations.RemoveField(
            model_name="task",
            name="google_event_id",
        ),
        # Add the M2M through field
        migrations.AddField(
            model_name="task",
            name="assigned_to",
            field=models.ManyToManyField(
                blank=True,
                related_name="assigned_tasks",
                through="tasks.TaskAssignment",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
