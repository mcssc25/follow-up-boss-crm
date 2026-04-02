"""
Step 2: Copy existing assigned_to FK data into TaskAssignment through model,
including google_event_id.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    TaskAssignment = apps.get_model("tasks", "TaskAssignment")
    for task in Task.objects.filter(assigned_to_old__isnull=False):
        TaskAssignment.objects.get_or_create(
            task=task,
            user_id=task.assigned_to_old_id,
            defaults={"google_event_id": task.google_event_id or ""},
        )


def backwards(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    TaskAssignment = apps.get_model("tasks", "TaskAssignment")
    for assignment in TaskAssignment.objects.all():
        Task.objects.filter(pk=assignment.task_id).update(
            assigned_to_old_id=assignment.user_id,
            google_event_id=assignment.google_event_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0004_taskassignment_multi_assign"),
    ]

    operations = [
        # First rename old FK so it doesn't conflict with the new M2M field name
        migrations.RenameField(
            model_name="task",
            old_name="assigned_to",
            new_name="assigned_to_old",
        ),
        # Run the data migration
        migrations.RunPython(forwards, backwards),
    ]
