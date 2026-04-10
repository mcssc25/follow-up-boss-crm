# Task Notifications & Calendar Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Push-notify agents when tasks are created, remind them daily at 9 AM until deadline, and sync task due dates to Google Calendar (with cleanup on completion).

**Architecture:** Add `google_event_id` to Task model. Fire a Celery task on creation that sends push + creates calendar event. New daily Celery Beat job at 9 AM CT sends push reminders. On completion, delete calendar event and let existing status filter stop reminders.

**Tech Stack:** Django, Celery Beat (crontab), pywebpush (existing), Google Calendar API (existing `GoogleCalendarService`)

---

### Task 1: Add `google_event_id` field to Task model

**Files:**
- Modify: `apps/tasks/models.py:6-33`
- Create: migration via `makemigrations`

**Step 1: Add field to model**

In `apps/tasks/models.py`, add after `created_at` (line 33):

```python
google_event_id = models.CharField(max_length=255, blank=True, default='')
```

**Step 2: Create and run migration**

Run:
```bash
python manage.py makemigrations tasks
python manage.py migrate
```

Expected: Migration created and applied successfully.

**Step 3: Commit**

```bash
git add apps/tasks/models.py apps/tasks/migrations/
git commit -m "feat(tasks): add google_event_id field for calendar sync"
```

---

### Task 2: Create `create_task_notifications` Celery task

**Files:**
- Modify: `apps/tasks/tasks.py`
- Test: `apps/tasks/tests/test_tasks.py` (create if needed)

**Step 1: Write the test**

Create `apps/tasks/tests/test_tasks.py`:

```python
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.tasks.models import Task
from apps.tasks.tasks import create_task_notifications


class CreateTaskNotificationsTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1',
            email='agent1@test.com',
            password='testpass123',
            team=self.team,
        )
        self.task = Task.objects.create(
            title='Call buyer',
            description='Follow up on offer',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=2),
            priority='high',
        )

    @patch('apps.tasks.tasks.send_push_notification')
    def test_sends_push_notification(self, mock_push):
        create_task_notifications(self.task.id)
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args
        self.assertEqual(call_kwargs[1]['user'], self.user)
        self.assertIn('Call buyer', call_kwargs[1]['title'])

    @patch('apps.tasks.tasks.GoogleCalendarService')
    @patch('apps.tasks.tasks.send_push_notification')
    def test_creates_calendar_event_when_gmail_connected(self, mock_push, mock_cal_cls):
        self.user.gmail_connected = True
        self.user.save()

        mock_service = MagicMock()
        mock_cal_cls.return_value = mock_service
        mock_service.service.events.return_value.insert.return_value.execute.return_value = {
            'id': 'gcal_event_123',
        }

        create_task_notifications(self.task.id)

        mock_cal_cls.assert_called_once_with(self.user)
        self.task.refresh_from_db()
        self.assertEqual(self.task.google_event_id, 'gcal_event_123')

    @patch('apps.tasks.tasks.GoogleCalendarService')
    @patch('apps.tasks.tasks.send_push_notification')
    def test_skips_calendar_when_gmail_not_connected(self, mock_push, mock_cal_cls):
        self.user.gmail_connected = False
        self.user.save()

        create_task_notifications(self.task.id)

        mock_cal_cls.assert_not_called()
        self.task.refresh_from_db()
        self.assertEqual(self.task.google_event_id, '')

    @patch('apps.tasks.tasks.send_push_notification')
    def test_handles_missing_task(self, mock_push):
        # Should not raise
        create_task_notifications(99999)
        mock_push.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_tasks -v2`
Expected: ImportError or failures (function doesn't exist yet).

**Step 3: Write the implementation**

In `apps/tasks/tasks.py`, add imports at the top and new task after existing tasks:

Add to imports (after existing imports):
```python
from apps.scheduling.calendar import GoogleCalendarService
```

Add new Celery task:
```python
@shared_task
def create_task_notifications(task_id):
    """Send push notification and create calendar event when a task is created."""
    try:
        task = Task.objects.select_related('assigned_to').get(pk=task_id)
    except Task.DoesNotExist:
        logger.warning("Task %s not found for notification", task_id)
        return

    agent = task.assigned_to
    due_str = task.due_date.strftime('%b %d at %I:%M %p')

    # Push notification
    send_push_notification(
        user=agent,
        title=f'New Task: {task.title}',
        body=f'Due {due_str} — Priority: {task.get_priority_display()}',
        url='/tasks/',
    )

    # Google Calendar event
    if not agent.gmail_connected:
        logger.info("Skipping calendar for task %s — agent Gmail not connected", task_id)
        return

    try:
        cal = GoogleCalendarService(agent)
        event = {
            'summary': task.title,
            'description': (
                f"Priority: {task.get_priority_display()}\n"
                f"{task.description}"
            ).strip(),
            'start': {
                'dateTime': task.due_date.isoformat(),
                'timeZone': 'America/Chicago',
            },
            'end': {
                'dateTime': (task.due_date + timedelta(minutes=30)).isoformat(),
                'timeZone': 'America/Chicago',
            },
        }
        result = cal.service.events().insert(
            calendarId='primary', body=event, sendUpdates='none',
        ).execute()
        event_id = result.get('id', '')
        if event_id:
            task.google_event_id = event_id
            task.save(update_fields=['google_event_id'])
            logger.info("Created calendar event %s for task %s", event_id, task_id)
    except Exception:
        logger.exception("Failed to create calendar event for task %s", task_id)
```

**Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.tasks.tests.test_tasks -v2`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add apps/tasks/tasks.py apps/tasks/tests/test_tasks.py
git commit -m "feat(tasks): push notification + calendar event on task creation"
```

---

### Task 3: Wire up `TaskCreateView` to fire the notification

**Files:**
- Modify: `apps/tasks/views.py:68-71`

**Step 1: Write the test**

Add to `apps/tasks/tests/test_views.py`:

```python
from unittest.mock import patch

class TaskCreateNotificationTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1', email='a@test.com', password='testpass123', team=self.team,
        )
        self.client.login(username='agent1', password='testpass123')

    @patch('apps.tasks.views.create_task_notifications')
    def test_create_task_fires_notification(self, mock_notify):
        from django.utils import timezone
        due = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post('/tasks/create/', {
            'title': 'Test task',
            'due_date': due,
            'priority': 'high',
            'assigned_to': self.user.pk,
        })
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title='Test task')
        mock_notify.delay.assert_called_once_with(task.pk)
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_views.TaskCreateNotificationTest -v2`
Expected: FAIL — `delay` not called yet.

**Step 3: Update the view**

In `apps/tasks/views.py`, add import at top:

```python
from apps.tasks.tasks import create_task_notifications
```

Replace `form_valid` in `TaskCreateView` (lines 68-71):

```python
    def form_valid(self, form):
        form.instance.team = self.request.user.team
        response = super().form_valid(form)
        create_task_notifications.delay(self.object.pk)
        messages.success(self.request, 'Task created successfully.')
        return response
```

**Step 4: Run test to verify it passes**

Run: `python manage.py test apps.tasks.tests.test_views.TaskCreateNotificationTest -v2`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tasks/views.py apps/tasks/tests/test_views.py
git commit -m "feat(tasks): fire notification celery task on task creation"
```

---

### Task 4: Add daily 9 AM reminder Celery task

**Files:**
- Modify: `apps/tasks/tasks.py`
- Modify: `config/settings.py:284-305` (CELERY_BEAT_SCHEDULE)

**Step 1: Write the test**

Add to `apps/tasks/tests/test_tasks.py`:

```python
class DailyTaskRemindersTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1', email='a@test.com', password='testpass123', team=self.team,
        )

    @patch('apps.tasks.tasks.send_push_notification')
    def test_sends_reminder_for_pending_future_tasks(self, mock_push):
        from apps.tasks.tasks import send_daily_task_reminders
        Task.objects.create(
            title='Future task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=2),
        )
        count = send_daily_task_reminders()
        self.assertEqual(count, 1)
        mock_push.assert_called_once()
        self.assertIn('Future task', mock_push.call_args[1]['body'])

    @patch('apps.tasks.tasks.send_push_notification')
    def test_skips_completed_tasks(self, mock_push):
        from apps.tasks.tasks import send_daily_task_reminders
        Task.objects.create(
            title='Done task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=2),
            status='completed',
        )
        count = send_daily_task_reminders()
        self.assertEqual(count, 0)
        mock_push.assert_not_called()

    @patch('apps.tasks.tasks.send_push_notification')
    def test_skips_overdue_tasks(self, mock_push):
        from apps.tasks.tasks import send_daily_task_reminders
        Task.objects.create(
            title='Overdue task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() - timedelta(days=1),
        )
        count = send_daily_task_reminders()
        self.assertEqual(count, 0)
        mock_push.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_tasks.DailyTaskRemindersTest -v2`
Expected: ImportError — function doesn't exist yet.

**Step 3: Add the Celery task**

In `apps/tasks/tasks.py`, add:

```python
@shared_task
def send_daily_task_reminders():
    """Daily 9 AM push reminder for all pending tasks with future deadlines."""
    now = timezone.now()
    pending_tasks = (
        Task.objects.filter(status='pending', due_date__gt=now)
        .select_related('assigned_to')
    )

    count = 0
    for task in pending_tasks:
        due_str = task.due_date.strftime('%b %d at %I:%M %p')
        send_push_notification(
            user=task.assigned_to,
            title='Task Reminder',
            body=f'{task.title} — due {due_str}',
            url='/tasks/',
        )
        count += 1

    logger.info("Sent %d daily task reminders", count)
    return count
```

**Step 4: Add to Celery Beat schedule**

In `config/settings.py`, add to `CELERY_BEAT_SCHEDULE` dict (before the closing `}`):

```python
    'send-daily-task-reminders': {
        'task': 'apps.tasks.tasks.send_daily_task_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM CT
    },
```

**Step 5: Run tests to verify they pass**

Run: `python manage.py test apps.tasks.tests.test_tasks.DailyTaskRemindersTest -v2`
Expected: All 3 tests PASS.

**Step 6: Commit**

```bash
git add apps/tasks/tasks.py config/settings.py
git commit -m "feat(tasks): daily 9 AM push reminder for pending tasks"
```

---

### Task 5: Delete calendar event on task completion

**Files:**
- Modify: `apps/tasks/views.py:108-116` (task_complete view)

**Step 1: Write the test**

Add to `apps/tasks/tests/test_views.py`:

```python
class TaskCompleteCalendarTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1', email='a@test.com', password='testpass123', team=self.team,
            gmail_connected=True,
        )
        self.client.login(username='agent1', password='testpass123')

    @patch('apps.tasks.views.GoogleCalendarService')
    def test_complete_deletes_calendar_event(self, mock_cal_cls):
        task = Task.objects.create(
            title='Task with event',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
            google_event_id='gcal_123',
        )
        mock_service = MagicMock()
        mock_cal_cls.return_value = mock_service

        response = self.client.post(f'/tasks/{task.pk}/complete/')
        self.assertEqual(response.status_code, 302)

        mock_cal_cls.assert_called_once_with(self.user)
        mock_service.delete_event.assert_called_once_with('gcal_123')

        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')

    @patch('apps.tasks.views.GoogleCalendarService')
    def test_complete_skips_calendar_when_no_event_id(self, mock_cal_cls):
        task = Task.objects.create(
            title='Task without event',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )

        response = self.client.post(f'/tasks/{task.pk}/complete/')
        self.assertEqual(response.status_code, 302)

        mock_cal_cls.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.tasks.tests.test_views.TaskCompleteCalendarTest -v2`
Expected: FAIL — calendar service not called.

**Step 3: Update task_complete view**

In `apps/tasks/views.py`, add import at top:

```python
from apps.scheduling.calendar import GoogleCalendarService
```

Replace `task_complete` function (lines 108-116):

```python
@login_required
def task_complete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    task = get_object_or_404(Task, pk=pk, team=request.user.team)

    # Delete calendar event if one exists
    if task.google_event_id and task.assigned_to.gmail_connected:
        try:
            cal = GoogleCalendarService(task.assigned_to)
            cal.delete_event(task.google_event_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to delete calendar event for task %s", task.pk
            )

    task.complete()
    messages.success(request, f'Task "{task.title}" marked as completed.')
    return redirect('tasks:list')
```

**Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.tasks.tests.test_views.TaskCompleteCalendarTest -v2`
Expected: All 2 tests PASS.

**Step 5: Run full test suite**

Run: `python manage.py test apps.tasks -v2`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add apps/tasks/views.py apps/tasks/tests/test_views.py
git commit -m "feat(tasks): delete calendar event when task marked complete"
```

---

### Task 6: Final integration check

**Step 1: Run full test suite**

Run: `python manage.py test apps.tasks -v2`
Expected: All tests pass.

**Step 2: Verify migrations**

Run: `python manage.py showmigrations tasks`
Expected: All migrations applied.

**Step 3: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "feat(tasks): task notifications and calendar sync complete"
```
