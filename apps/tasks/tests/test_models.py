from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.tasks.models import Task


class TaskModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1',
            email='agent1@test.com',
            password='testpass123',
            team=self.team,
        )

    def test_create_task(self):
        task = Task.objects.create(
            title='Follow up with client',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.priority, 'medium')
        self.assertIsNone(task.completed_at)

    def test_str(self):
        task = Task.objects.create(
            title='Call buyer',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(str(task), 'Call buyer')

    def test_is_overdue_true(self):
        task = Task.objects.create(
            title='Overdue task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() - timedelta(hours=1),
            status='pending',
        )
        self.assertTrue(task.is_overdue)

    def test_is_overdue_false_when_future(self):
        task = Task.objects.create(
            title='Future task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
            status='pending',
        )
        self.assertFalse(task.is_overdue)

    def test_is_overdue_false_when_completed(self):
        task = Task.objects.create(
            title='Done task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() - timedelta(hours=1),
            status='completed',
        )
        self.assertFalse(task.is_overdue)

    def test_complete(self):
        task = Task.objects.create(
            title='Complete me',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        task.complete()
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)

    def test_ordering(self):
        t1 = Task.objects.create(
            title='Later',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=2),
        )
        t2 = Task.objects.create(
            title='Sooner',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        tasks = list(Task.objects.filter(team=self.team))
        self.assertEqual(tasks[0], t2)
        self.assertEqual(tasks[1], t1)
