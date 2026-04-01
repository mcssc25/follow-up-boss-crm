from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
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
        create_task_notifications(99999)
        mock_push.assert_not_called()
