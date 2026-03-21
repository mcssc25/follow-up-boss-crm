from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.tasks.models import Task


class TaskViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1',
            email='agent1@test.com',
            password='testpass123',
            team=self.team,
        )
        self.client.login(username='agent1', password='testpass123')

    def test_task_list_view(self):
        Task.objects.create(
            title='Test Task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('tasks:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Task')

    def test_task_list_filter_overdue(self):
        Task.objects.create(
            title='Overdue Task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() - timedelta(hours=2),
            status='pending',
        )
        Task.objects.create(
            title='Future Task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
            status='pending',
        )
        response = self.client.get(reverse('tasks:list') + '?filter=overdue')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Overdue Task')
        self.assertNotContains(response, 'Future Task')

    def test_task_list_filter_completed(self):
        Task.objects.create(
            title='Done Task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now(),
            status='completed',
        )
        Task.objects.create(
            title='Pending Task',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
            status='pending',
        )
        response = self.client.get(reverse('tasks:list') + '?filter=completed')
        self.assertContains(response, 'Done Task')
        self.assertNotContains(response, 'Pending Task')

    def test_task_create_view(self):
        response = self.client.get(reverse('tasks:create'))
        self.assertEqual(response.status_code, 200)

    def test_task_create_post(self):
        due = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(reverse('tasks:create'), {
            'title': 'New Task',
            'due_date': due,
            'priority': 'high',
            'assigned_to': self.user.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(title='New Task').exists())

    def test_task_complete(self):
        task = Task.objects.create(
            title='Complete Me',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.post(reverse('tasks:complete', args=[task.pk]))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')

    def test_task_complete_get_not_allowed(self):
        task = Task.objects.create(
            title='No GET',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('tasks:complete', args=[task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_task_delete(self):
        task = Task.objects.create(
            title='Delete Me',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.post(reverse('tasks:delete', args=[task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_task_edit_view(self):
        task = Task.objects.create(
            title='Edit Me',
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('tasks:edit', args=[task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Me')

    def test_task_team_isolation(self):
        other_team = Team.objects.create(name='Other Team')
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            team=other_team,
        )
        task = Task.objects.create(
            title='Other Team Task',
            assigned_to=other_user,
            team=other_team,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('tasks:list'))
        self.assertNotContains(response, 'Other Team Task')
