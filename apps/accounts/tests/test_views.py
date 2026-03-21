from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class LoginViewTest(TestCase):
    def test_login_page_loads(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_redirects_authenticated_user(self):
        User.objects.create_user(username='test', password='pass123')
        self.client.login(username='test', password='pass123')
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 302)

    def test_login_valid_credentials(self):
        User.objects.create_user(username='test', password='pass123')
        response = self.client.post('/accounts/login/', {
            'username': 'test',
            'password': 'pass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/')

    def test_login_invalid_credentials(self):
        response = self.client.post('/accounts/login/', {
            'username': 'bad',
            'password': 'bad',
        })
        self.assertEqual(response.status_code, 200)


class RegisterViewTest(TestCase):
    def test_register_page_loads(self):
        response = self.client.get('/accounts/register/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')

    def test_register_creates_user(self):
        response = self.client.post('/accounts/register/', {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new@test.com',
            'password1': 'complexpass123!',
            'password2': 'complexpass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_redirects_authenticated_user(self):
        User.objects.create_user(username='test', password='pass123')
        self.client.login(username='test', password='pass123')
        response = self.client.get('/accounts/register/')
        self.assertEqual(response.status_code, 302)


class ProfileViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test', password='pass123',
            first_name='Test', last_name='User',
        )

    def test_profile_requires_login(self):
        response = self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_profile_page_loads(self):
        self.client.login(username='test', password='pass123')
        response = self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')

    def test_profile_update(self):
        self.client.login(username='test', password='pass123')
        response = self.client.post('/accounts/profile/', {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@test.com',
            'phone': '555-1234',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.phone, '555-1234')


class DashboardViewTest(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads_for_authenticated_user(self):
        User.objects.create_user(username='test', password='pass123')
        self.client.login(username='test', password='pass123')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
