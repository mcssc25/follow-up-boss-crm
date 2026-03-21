# Real Estate CRM Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted real estate CRM with contact management, deal pipelines, customizable email drip campaigns (text + video), smart lists, tasks, and reporting — deployed via Docker Compose.

**Architecture:** Single Django application with Celery workers for background email sending and task scheduling. PostgreSQL for data, Redis as Celery broker. Gmail API for sending emails as the user. Nginx reverse proxy with SSL.

**Tech Stack:** Django 5.x, Celery, Redis, PostgreSQL, Tailwind CSS, Gmail API (OAuth2), Docker Compose, Gunicorn, Nginx

---

## Phase 1: Project Scaffolding & Infrastructure

### Task 1: Initialize Django Project

**Files:**
- Create: `requirements.txt`
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `config/asgi.py`
- Create: `config/celery.py`

**Step 1: Create requirements.txt**

```txt
Django>=5.1,<5.2
celery>=5.4,<6.0
redis>=5.0,<6.0
psycopg2-binary>=2.9,<3.0
django-celery-beat>=2.6,<3.0
django-celery-results>=2.5,<3.0
django-cors-headers>=4.3,<5.0
django-allauth>=0.60,<1.0
gunicorn>=22.0,<26.0
Pillow>=10.0,<13.0
google-auth-oauthlib>=1.2,<2.0
google-auth-httplib2>=0.2,<1.0
google-api-python-client>=2.100,<3.0
django-widget-tweaks>=1.5,<2.0
django-filter>=24.0,<25.0
whitenoise>=6.5,<7.0
python-dotenv>=1.0,<2.0
django-htmx>=1.17,<2.0
```

**Step 2: Create Django project**

Run: `django-admin startproject config .`

**Step 3: Create .env file**

```env
SECRET_KEY=change-me-in-production
DEBUG=True
DATABASE_URL=postgres://crm_user:crm_pass@localhost:5432/crm_db
REDIS_URL=redis://localhost:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

**Step 4: Configure settings.py**

Replace generated settings.py with production-ready settings:
- Load env vars from .env via python-dotenv
- Configure PostgreSQL database
- Configure Redis cache
- Configure Celery
- Configure static files with whitenoise
- Configure allauth for authentication
- Set up INSTALLED_APPS with all project apps
- Configure media root for video uploads

**Step 5: Configure Celery**

`config/celery.py`:
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('crm')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

`config/__init__.py`:
```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

**Step 6: Commit**

```bash
git init
git add .
git commit -m "feat: initialize Django project with Celery config"
```

---

### Task 2: Create Django Apps

**Files:**
- Create: `apps/accounts/` (models, views, urls, admin, forms)
- Create: `apps/contacts/`
- Create: `apps/pipeline/`
- Create: `apps/campaigns/`
- Create: `apps/tasks/`
- Create: `apps/reports/`
- Create: `apps/api/`

**Step 1: Create all apps**

```bash
mkdir -p apps
cd apps
python ../manage.py startapp accounts
python ../manage.py startapp contacts
python ../manage.py startapp pipeline
python ../manage.py startapp campaigns
python ../manage.py startapp tasks
python ../manage.py startapp reports
python ../manage.py startapp api
cd ..
```

**Step 2: Update each app's apps.py** with correct name (e.g. `apps.accounts`)

**Step 3: Register all apps in settings.py INSTALLED_APPS**

**Step 4: Commit**

```bash
git add .
git commit -m "feat: create all Django apps"
```

---

### Task 3: Docker Compose Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `nginx/nginx.conf`
- Create: `docker-entrypoint.sh`
- Create: `.dockerignore`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: crm_db
      POSTGRES_USER: crm_user
      POSTGRES_PASSWORD: crm_pass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U crm_user -d crm_db"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery:
    build: .
    command: celery -A config worker -l info
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery-beat:
    build: .
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf
      - static_files:/app/staticfiles
      - media_files:/app/media
    depends_on:
      - web

volumes:
  pgdata:
  static_files:
  media_files:
```

**Step 3: Create nginx.conf**

```nginx
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    location /static/ {
        alias /app/staticfiles/;
    }

    location /media/ {
        alias /app/media/;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Step 4: Create docker-entrypoint.sh**

```bash
#!/bin/bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec "$@"
```

**Step 5: Verify docker-compose builds**

Run: `docker-compose build`
Expected: Successful build

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add Docker Compose setup with Nginx, PostgreSQL, Redis"
```

---

## Phase 2: User Authentication & Team Management

### Task 4: User Model & Authentication

**Files:**
- Create: `apps/accounts/models.py`
- Create: `apps/accounts/forms.py`
- Create: `apps/accounts/views.py`
- Create: `apps/accounts/urls.py`
- Create: `apps/accounts/admin.py`
- Create: `templates/accounts/login.html`
- Create: `templates/accounts/register.html`
- Create: `templates/accounts/profile.html`
- Test: `apps/accounts/tests/test_models.py`
- Test: `apps/accounts/tests/test_views.py`

**Step 1: Write failing test for User model**

```python
# apps/accounts/tests/test_models.py
from django.test import TestCase
from apps.accounts.models import User, Team

class UserModelTest(TestCase):
    def test_create_user_with_role(self):
        team = Team.objects.create(name="Test Team")
        user = User.objects.create_user(
            username="agent1",
            email="agent1@test.com",
            password="testpass123",
            role="agent",
            team=team
        )
        self.assertEqual(user.role, "agent")
        self.assertEqual(user.team, team)

    def test_user_is_admin(self):
        user = User.objects.create_user(
            username="admin1",
            email="admin@test.com",
            password="testpass123",
            role="admin"
        )
        self.assertTrue(user.is_admin)
```

**Step 2: Run test to verify it fails**

Run: `python manage.py test apps.accounts.tests.test_models -v 2`
Expected: FAIL — User model doesn't exist yet

**Step 3: Implement User and Team models**

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Team(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('agent', 'Agent'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='agent')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    phone = models.CharField(max_length=20, blank=True)
    gmail_access_token = models.TextField(blank=True)
    gmail_refresh_token = models.TextField(blank=True)
    gmail_token_expiry = models.DateTimeField(null=True, blank=True)
    gmail_connected = models.BooleanField(default=False)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
```

**Step 4: Set AUTH_USER_MODEL in settings.py**

```python
AUTH_USER_MODEL = 'accounts.User'
```

**Step 5: Run migrations and tests**

```bash
python manage.py makemigrations accounts
python manage.py migrate
python manage.py test apps.accounts.tests.test_models -v 2
```
Expected: PASS

**Step 6: Implement login/register views and templates**

Use django-allauth for login/logout/register flows. Create templates extending a base template.

**Step 7: Write view tests**

```python
# apps/accounts/tests/test_views.py
from django.test import TestCase, Client
from apps.accounts.models import User

class AuthViewTest(TestCase):
    def test_login_page_loads(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_login_redirects_to_dashboard(self):
        user = User.objects.create_user(username='test', password='pass123')
        self.client.login(username='test', password='pass123')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
```

**Step 8: Run all tests**

Run: `python manage.py test apps.accounts -v 2`
Expected: All PASS

**Step 9: Commit**

```bash
git add .
git commit -m "feat: add User model with roles, Team model, auth views"
```

---

## Phase 3: Contact Management

### Task 5: Contact Model

**Files:**
- Create: `apps/contacts/models.py`
- Create: `apps/contacts/admin.py`
- Test: `apps/contacts/tests/test_models.py`

**Step 1: Write failing test**

```python
# apps/contacts/tests/test_models.py
from django.test import TestCase
from apps.contacts.models import Contact, ContactNote, ContactActivity
from apps.accounts.models import User, Team

class ContactModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )

    def test_create_contact(self):
        contact = Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="555-1234",
            source="landing_page",
            assigned_to=self.agent,
            team=self.team
        )
        self.assertEqual(str(contact), "John Doe")
        self.assertEqual(contact.assigned_to, self.agent)

    def test_add_note(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        note = ContactNote.objects.create(
            contact=contact, author=self.agent, content="Called, left voicemail"
        )
        self.assertEqual(contact.notes.count(), 1)

    def test_log_activity(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        activity = ContactActivity.objects.create(
            contact=contact,
            activity_type="email_sent",
            description="Welcome email sent"
        )
        self.assertEqual(contact.activities.count(), 1)
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement Contact models**

```python
# apps/contacts/models.py
from django.db import models
from django.conf import settings

class Contact(models.Model):
    SOURCE_CHOICES = [
        ('landing_page', 'Landing Page'),
        ('manual', 'Manual Entry'),
        ('referral', 'Referral'),
        ('zillow', 'Zillow'),
        ('realtor', 'Realtor.com'),
        ('other', 'Other'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    source_detail = models.CharField(max_length=200, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contacts'
    )
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='contacts')
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class ContactNote(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class ContactActivity(models.Model):
    ACTIVITY_TYPES = [
        ('email_sent', 'Email Sent'),
        ('email_opened', 'Email Opened'),
        ('email_replied', 'Email Replied'),
        ('call_logged', 'Call Logged'),
        ('note_added', 'Note Added'),
        ('stage_changed', 'Stage Changed'),
        ('campaign_enrolled', 'Campaign Enrolled'),
        ('video_viewed', 'Video Viewed'),
    ]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'activities'
```

**Step 4: Run migrations and tests**

```bash
python manage.py makemigrations contacts
python manage.py migrate
python manage.py test apps.contacts.tests.test_models -v 2
```
Expected: PASS

**Step 5: Register in admin.py**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add Contact, ContactNote, ContactActivity models"
```

---

### Task 6: Contact Views (List, Detail, Create, Edit)

**Files:**
- Create: `apps/contacts/views.py`
- Create: `apps/contacts/forms.py`
- Create: `apps/contacts/urls.py`
- Create: `templates/contacts/contact_list.html`
- Create: `templates/contacts/contact_detail.html`
- Create: `templates/contacts/contact_form.html`
- Create: `templates/base.html` (with sidebar navigation)
- Test: `apps/contacts/tests/test_views.py`

**Step 1: Write failing view tests**

```python
# apps/contacts/tests/test_views.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.contacts.models import Contact

class ContactViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_contact_list(self):
        Contact.objects.create(
            first_name="John", last_name="Doe",
            team=self.team, assigned_to=self.user
        )
        response = self.client.get('/contacts/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_create_contact(self):
        response = self.client.post('/contacts/create/', {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@example.com',
            'source': 'manual',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Contact.objects.filter(last_name='Smith').exists())

    def test_contact_detail(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )
        response = self.client.get(f'/contacts/{contact.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")
```

**Step 2: Run tests — expect FAIL**

**Step 3: Create base template with sidebar**

The base template should include:
- Sidebar with nav links: Dashboard, Contacts, Pipeline, Campaigns, Tasks, Reports, Settings
- Top bar with user name and logout
- Main content area
- Tailwind CSS via CDN (simplest setup)

**Step 4: Implement contact views**

- `ContactListView` — filterable list with search, source filter, tag filter, assigned agent filter
- `ContactDetailView` — full profile with activity timeline, notes, deal info
- `ContactCreateView` — form to add new contact
- `ContactUpdateView` — edit contact info
- Bulk actions via POST (tag, assign, delete, enroll in campaign)

**Step 5: Create URL config**

```python
# apps/contacts/urls.py
from django.urls import path
from . import views

app_name = 'contacts'
urlpatterns = [
    path('', views.ContactListView.as_view(), name='list'),
    path('create/', views.ContactCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ContactDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ContactUpdateView.as_view(), name='edit'),
    path('<int:pk>/note/', views.add_note, name='add_note'),
    path('<int:pk>/log-activity/', views.log_activity, name='log_activity'),
    path('bulk-action/', views.bulk_action, name='bulk_action'),
]
```

**Step 6: Run tests — expect PASS**

**Step 7: Commit**

```bash
git add .
git commit -m "feat: add contact list, detail, create, edit views with templates"
```

---

## Phase 4: Deal Pipeline

### Task 7: Pipeline Models

**Files:**
- Create: `apps/pipeline/models.py`
- Create: `apps/pipeline/admin.py`
- Test: `apps/pipeline/tests/test_models.py`

**Step 1: Write failing test**

```python
# apps/pipeline/tests/test_models.py
from django.test import TestCase
from apps.pipeline.models import Pipeline, PipelineStage, Deal
from apps.contacts.models import Contact
from apps.accounts.models import User, Team

class PipelineModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )

    def test_create_pipeline_with_stages(self):
        pipeline = Pipeline.objects.create(name="Buyer Pipeline", team=self.team)
        stage1 = PipelineStage.objects.create(
            pipeline=pipeline, name="New Lead", order=1
        )
        stage2 = PipelineStage.objects.create(
            pipeline=pipeline, name="Contacted", order=2
        )
        self.assertEqual(pipeline.stages.count(), 2)

    def test_create_deal(self):
        pipeline = Pipeline.objects.create(name="Buyer", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="New Lead", order=1
        )
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage,
            assigned_to=self.agent,
            value=350000
        )
        self.assertEqual(deal.value, 350000)
        self.assertEqual(deal.stage.name, "New Lead")

    def test_move_deal_to_stage(self):
        pipeline = Pipeline.objects.create(name="Buyer", team=self.team)
        stage1 = PipelineStage.objects.create(pipeline=pipeline, name="New", order=1)
        stage2 = PipelineStage.objects.create(pipeline=pipeline, name="Contacted", order=2)
        deal = Deal.objects.create(
            contact=self.contact, pipeline=pipeline,
            stage=stage1, assigned_to=self.agent
        )
        deal.stage = stage2
        deal.save()
        self.assertEqual(deal.stage, stage2)
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement models**

```python
# apps/pipeline/models.py
from django.db import models
from django.conf import settings

class Pipeline(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='pipelines')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PipelineStage(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.pipeline.name} — {self.name}"

class Deal(models.Model):
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE, related_name='deals')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='deals')
    stage = models.ForeignKey(PipelineStage, on_delete=models.CASCADE, related_name='deals')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deals'
    )
    title = models.CharField(max_length=200, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    won = models.BooleanField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Deal: {self.contact}"
```

**Step 4: Run migrations and tests — expect PASS**

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Pipeline, PipelineStage, Deal models"
```

---

### Task 8: Pipeline Kanban Board View

**Files:**
- Create: `apps/pipeline/views.py`
- Create: `apps/pipeline/urls.py`
- Create: `templates/pipeline/board.html`
- Create: `templates/pipeline/deal_card.html`
- Test: `apps/pipeline/tests/test_views.py`

**Step 1: Write failing view test**

```python
# apps/pipeline/tests/test_views.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.pipeline.models import Pipeline, PipelineStage, Deal
from apps.contacts.models import Contact

class PipelineBoardViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")
        self.pipeline = Pipeline.objects.create(name="Buyer", team=self.team)
        self.stage = PipelineStage.objects.create(
            pipeline=self.pipeline, name="New Lead", order=1
        )

    def test_board_loads(self):
        response = self.client.get(f'/pipeline/{self.pipeline.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Lead")

    def test_move_deal_api(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )
        deal = Deal.objects.create(
            contact=contact, pipeline=self.pipeline,
            stage=self.stage, assigned_to=self.user
        )
        new_stage = PipelineStage.objects.create(
            pipeline=self.pipeline, name="Contacted", order=2
        )
        response = self.client.post(
            f'/pipeline/deal/{deal.id}/move/',
            {'stage_id': new_stage.id},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        deal.refresh_from_db()
        self.assertEqual(deal.stage, new_stage)
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement views**

- `PipelineBoardView` — renders Kanban board with stages as columns, deals as cards
- `move_deal` — AJAX endpoint for drag-and-drop (updates deal stage)
- Use htmx or vanilla JS for drag-and-drop

**Step 4: Create Kanban board template**

Use Tailwind CSS grid with columns per stage. Each deal card shows contact name, value, days in stage. Drag-and-drop via SortableJS (lightweight, no framework needed).

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add pipeline Kanban board with drag-and-drop"
```

---

## Phase 5: Email Drip Campaigns

### Task 9: Campaign Models

**Files:**
- Create: `apps/campaigns/models.py`
- Create: `apps/campaigns/admin.py`
- Test: `apps/campaigns/tests/test_models.py`

**Step 1: Write failing test**

```python
# apps/campaigns/tests/test_models.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.campaigns.models import Campaign, CampaignStep, CampaignEnrollment
from apps.contacts.models import Contact
from apps.accounts.models import User, Team

class CampaignModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )

    def test_create_campaign_with_steps(self):
        campaign = Campaign.objects.create(
            name="Buyer Drip", team=self.team, created_by=self.agent
        )
        step1 = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Welcome!", body="<p>Hi {{first_name}}</p>"
        )
        step2 = CampaignStep.objects.create(
            campaign=campaign, order=2,
            delay_days=3, delay_hours=0,
            subject="Check this out", body="<p>Video intro</p>",
            video_file="videos/intro.mp4"
        )
        self.assertEqual(campaign.steps.count(), 2)

    def test_enroll_contact(self):
        campaign = Campaign.objects.create(
            name="Buyer Drip", team=self.team, created_by=self.agent
        )
        step1 = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Welcome!", body="Hi"
        )
        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            next_send_at=timezone.now()
        )
        self.assertTrue(enrollment.is_active)

    def test_pause_on_reply(self):
        campaign = Campaign.objects.create(
            name="Test", team=self.team, created_by=self.agent
        )
        step = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Hi", body="Hello"
        )
        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step,
            next_send_at=timezone.now()
        )
        enrollment.pause(reason="contact_replied")
        self.assertFalse(enrollment.is_active)
        self.assertEqual(enrollment.paused_reason, "contact_replied")
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement models**

```python
# apps/campaigns/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Campaign(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='campaigns')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def duplicate(self):
        """Create a copy of this campaign with all steps."""
        new_campaign = Campaign.objects.create(
            name=f"{self.name} (Copy)",
            description=self.description,
            team=self.team,
            created_by=self.created_by,
            is_active=False
        )
        for step in self.steps.all():
            CampaignStep.objects.create(
                campaign=new_campaign,
                order=step.order,
                delay_days=step.delay_days,
                delay_hours=step.delay_hours,
                subject=step.subject,
                body=step.body,
                video_file=step.video_file
            )
        return new_campaign

class CampaignStep(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField()
    delay_days = models.PositiveIntegerField(default=0)
    delay_hours = models.PositiveIntegerField(default=0)
    subject = models.CharField(max_length=200)
    body = models.TextField(help_text="HTML email body. Use {{first_name}}, {{agent_name}}, {{agent_phone}} for merge fields.")
    video_file = models.FileField(upload_to='campaign_videos/', blank=True, null=True)
    video_thumbnail = models.ImageField(upload_to='campaign_thumbnails/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Step {self.order}: {self.subject}"

    @property
    def total_delay_hours(self):
        return (self.delay_days * 24) + self.delay_hours

class CampaignEnrollment(models.Model):
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE, related_name='enrollments')
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='enrollments')
    current_step = models.ForeignKey(CampaignStep, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    paused_reason = models.CharField(max_length=100, blank=True)
    next_send_at = models.DateTimeField(null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def pause(self, reason=""):
        self.is_active = False
        self.paused_reason = reason
        self.save()

    def resume(self):
        self.is_active = True
        self.paused_reason = ""
        self.next_send_at = timezone.now()
        self.save()

    def advance_to_next_step(self):
        next_steps = self.campaign.steps.filter(order__gt=self.current_step.order)
        if next_steps.exists():
            next_step = next_steps.first()
            self.current_step = next_step
            self.next_send_at = timezone.now() + timezone.timedelta(
                hours=next_step.total_delay_hours
            )
            self.save()
        else:
            self.is_active = False
            self.completed_at = timezone.now()
            self.save()
```

**Step 4: Run migrations and tests — expect PASS**

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Campaign, CampaignStep, CampaignEnrollment models"
```

---

### Task 10: Gmail OAuth2 Integration

**Files:**
- Create: `apps/accounts/gmail.py`
- Create: `apps/accounts/views_gmail.py`
- Test: `apps/accounts/tests/test_gmail.py`

**Step 1: Write failing test**

```python
# apps/accounts/tests/test_gmail.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.accounts.gmail import GmailService

class GmailServiceTest(TestCase):
    @patch('apps.accounts.gmail.build')
    def test_send_email(self, mock_build):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.users().messages().send().execute.return_value = {'id': '123'}

        gmail = GmailService(access_token="fake", refresh_token="fake")
        result = gmail.send_email(
            to="test@example.com",
            subject="Hello",
            body_html="<p>Hi there</p>",
            from_email="agent@gmail.com"
        )
        self.assertTrue(result['success'])
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement GmailService**

```python
# apps/accounts/gmail.py
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class GmailService:
    def __init__(self, access_token, refresh_token, client_id=None, client_secret=None):
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri='https://oauth2.googleapis.com/token'
        )
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def send_email(self, to, subject, body_html, from_email, reply_to=None):
        try:
            message = MIMEMultipart('alternative')
            message['to'] = to
            message['from'] = from_email
            message['subject'] = subject
            if reply_to:
                message['Reply-To'] = reply_to

            html_part = MIMEText(body_html, 'html')
            message.attach(html_part)

            raw = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')

            result = self.service.users().messages().send(
                userId='me', body={'raw': raw}
            ).execute()

            return {'success': True, 'message_id': result.get('id')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
```

**Step 4: Implement OAuth views**

- `gmail_connect` — redirects to Google OAuth consent screen
- `gmail_callback` — handles OAuth callback, stores tokens on User model

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add Gmail OAuth2 integration for sending emails"
```

---

### Task 11: Celery Tasks for Drip Campaign Execution

**Files:**
- Create: `apps/campaigns/tasks.py`
- Create: `apps/campaigns/email_renderer.py`
- Test: `apps/campaigns/tests/test_tasks.py`

**Step 1: Write failing test**

```python
# apps/campaigns/tests/test_tasks.py
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from apps.campaigns.models import Campaign, CampaignStep, CampaignEnrollment
from apps.campaigns.tasks import process_due_emails
from apps.campaigns.email_renderer import render_campaign_email
from apps.contacts.models import Contact
from apps.accounts.models import User, Team

class CampaignTaskTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team,
            email="agent@gmail.com"
        )
        self.agent.gmail_connected = True
        self.agent.gmail_access_token = "fake_token"
        self.agent.gmail_refresh_token = "fake_refresh"
        self.agent.save()
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe",
            email="john@example.com",
            team=self.team, assigned_to=self.agent
        )

    def test_render_merge_fields(self):
        body = "<p>Hi {{first_name}}, call {{agent_name}} at {{agent_phone}}</p>"
        rendered = render_campaign_email(body, self.contact, self.agent)
        self.assertIn("John", rendered)

    @patch('apps.campaigns.tasks.GmailService')
    def test_process_due_emails(self, mock_gmail_class):
        mock_gmail = mock_gmail_class.return_value
        mock_gmail.send_email.return_value = {'success': True, 'message_id': '123'}

        campaign = Campaign.objects.create(
            name="Test", team=self.team, created_by=self.agent
        )
        step1 = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Welcome {{first_name}}",
            body="<p>Hi {{first_name}}</p>"
        )
        step2 = CampaignStep.objects.create(
            campaign=campaign, order=2,
            delay_days=3, delay_hours=0,
            subject="Follow up",
            body="<p>Checking in</p>"
        )
        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            next_send_at=timezone.now() - timezone.timedelta(minutes=1)
        )

        process_due_emails()

        mock_gmail.send_email.assert_called_once()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.current_step, step2)
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement email renderer**

```python
# apps/campaigns/email_renderer.py
import re

def render_campaign_email(body, contact, agent):
    replacements = {
        '{{first_name}}': contact.first_name,
        '{{last_name}}': contact.last_name,
        '{{full_name}}': f"{contact.first_name} {contact.last_name}",
        '{{agent_name}}': agent.get_full_name() or agent.username,
        '{{agent_phone}}': getattr(agent, 'phone', ''),
        '{{agent_email}}': agent.email,
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value or '')
    return body
```

**Step 4: Implement Celery task**

```python
# apps/campaigns/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import CampaignEnrollment
from .email_renderer import render_campaign_email
from apps.accounts.gmail import GmailService
from apps.contacts.models import ContactActivity

@shared_task
def process_due_emails():
    """Find all enrollments with due emails and send them."""
    due_enrollments = CampaignEnrollment.objects.filter(
        is_active=True,
        next_send_at__lte=timezone.now(),
        contact__email__gt='',
        campaign__is_active=True
    ).select_related(
        'contact', 'contact__assigned_to', 'campaign', 'current_step'
    )

    for enrollment in due_enrollments:
        send_campaign_email.delay(enrollment.id)

@shared_task
def send_campaign_email(enrollment_id):
    """Send a single campaign email and advance the enrollment."""
    try:
        enrollment = CampaignEnrollment.objects.select_related(
            'contact', 'contact__assigned_to', 'current_step', 'campaign'
        ).get(id=enrollment_id, is_active=True)
    except CampaignEnrollment.DoesNotExist:
        return

    contact = enrollment.contact
    agent = contact.assigned_to
    step = enrollment.current_step

    if not agent or not agent.gmail_connected:
        return

    # Render email
    rendered_body = render_campaign_email(step.body, contact, agent)
    rendered_subject = render_campaign_email(step.subject, contact, agent)

    # Send via Gmail
    gmail = GmailService(
        access_token=agent.gmail_access_token,
        refresh_token=agent.gmail_refresh_token
    )
    result = gmail.send_email(
        to=contact.email,
        subject=rendered_subject,
        body_html=rendered_body,
        from_email=agent.email
    )

    if result['success']:
        # Log activity
        ContactActivity.objects.create(
            contact=contact,
            activity_type='email_sent',
            description=f"Campaign email: {rendered_subject}",
            metadata={'campaign_id': enrollment.campaign.id, 'step_order': step.order}
        )
        # Update last contacted
        contact.last_contacted_at = timezone.now()
        contact.save(update_fields=['last_contacted_at'])
        # Advance to next step
        enrollment.advance_to_next_step()
```

**Step 5: Register periodic task in settings**

```python
# In config/settings.py
CELERY_BEAT_SCHEDULE = {
    'process-due-campaign-emails': {
        'task': 'apps.campaigns.tasks.process_due_emails',
        'schedule': 300.0,  # Every 5 minutes
    },
}
```

**Step 6: Run tests — expect PASS**

**Step 7: Commit**

```bash
git add .
git commit -m "feat: add Celery tasks for drip campaign email sending"
```

---

### Task 12: Campaign Management Views

**Files:**
- Create: `apps/campaigns/views.py`
- Create: `apps/campaigns/forms.py`
- Create: `apps/campaigns/urls.py`
- Create: `templates/campaigns/campaign_list.html`
- Create: `templates/campaigns/campaign_detail.html`
- Create: `templates/campaigns/campaign_form.html`
- Create: `templates/campaigns/step_form.html`
- Test: `apps/campaigns/tests/test_views.py`

**Step 1: Write failing view tests**

```python
# apps/campaigns/tests/test_views.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.campaigns.models import Campaign, CampaignStep

class CampaignViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_campaign_list(self):
        Campaign.objects.create(
            name="Buyer Drip", team=self.team, created_by=self.user
        )
        response = self.client.get('/campaigns/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buyer Drip")

    def test_create_campaign(self):
        response = self.client.post('/campaigns/create/', {
            'name': 'Seller Drip',
            'description': 'For seller leads',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Campaign.objects.filter(name='Seller Drip').exists())

    def test_add_step_to_campaign(self):
        campaign = Campaign.objects.create(
            name="Test", team=self.team, created_by=self.user
        )
        response = self.client.post(f'/campaigns/{campaign.id}/add-step/', {
            'order': 1,
            'delay_days': 0,
            'delay_hours': 0,
            'subject': 'Welcome!',
            'body': '<p>Hello</p>',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(campaign.steps.count(), 1)

    def test_edit_step(self):
        campaign = Campaign.objects.create(
            name="Test", team=self.team, created_by=self.user
        )
        step = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Old Subject", body="Old body"
        )
        response = self.client.post(f'/campaigns/step/{step.id}/edit/', {
            'order': 1,
            'delay_days': 2,
            'delay_hours': 0,
            'subject': 'New Subject',
            'body': '<p>New body</p>',
        })
        step.refresh_from_db()
        self.assertEqual(step.subject, 'New Subject')
        self.assertEqual(step.delay_days, 2)
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement views**

- `CampaignListView` — all campaigns with enrollment counts
- `CampaignDetailView` — shows steps in order, enrollment stats
- `CampaignCreateView` — create new campaign
- `CampaignUpdateView` — edit name, description, toggle active
- `add_step` — add a step to a campaign
- `edit_step` — edit an existing step (subject, body, delay, video)
- `delete_step` — remove a step
- `reorder_steps` — AJAX endpoint for drag-and-drop reordering
- `duplicate_campaign` — creates a copy
- `enroll_contact` — enroll a contact from the contact detail page
- Rich text editor: use a simple WYSIWYG like TinyMCE (CDN) or Quill for the email body

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add campaign management views with step editor"
```

---

### Task 13: Video Upload & Hosting

**Files:**
- Create: `apps/campaigns/video.py`
- Create: `templates/campaigns/video_player.html`
- Modify: `apps/campaigns/views.py` (add video tracking view)
- Test: `apps/campaigns/tests/test_video.py`

**Step 1: Write failing test**

```python
# apps/campaigns/tests/test_video.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.campaigns.models import Campaign, CampaignStep
from apps.contacts.models import Contact

class VideoTrackingTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe",
            email="john@test.com", team=self.team
        )

    def test_video_page_loads(self):
        campaign = Campaign.objects.create(
            name="Test", team=self.team, created_by=self.user
        )
        step = CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Watch this", body="Video",
            video_file="campaign_videos/test.mp4"
        )
        response = self.client.get(
            f'/campaigns/video/{step.id}/{self.contact.id}/'
        )
        self.assertEqual(response.status_code, 200)
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement video player page and tracking**

- Simple page that plays the video (HTML5 video player)
- On page load, log a `video_viewed` activity on the contact
- Track view duration if possible (JS sends beacon on unload)
- Video files served from media directory via Nginx

**Step 4: In campaign email templates, video steps include a thumbnail that links to the video player page**

The URL pattern: `/campaigns/video/<step_id>/<contact_id>/`
This allows per-contact view tracking.

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add video hosting page with view tracking"
```

---

## Phase 6: Tasks & Smart Lists

### Task 14: Task/Reminder Model & Views

**Files:**
- Create: `apps/tasks/models.py`
- Create: `apps/tasks/views.py`
- Create: `apps/tasks/forms.py`
- Create: `apps/tasks/urls.py`
- Create: `apps/tasks/admin.py`
- Create: `templates/tasks/task_list.html`
- Create: `templates/tasks/task_form.html`
- Test: `apps/tasks/tests/test_models.py`
- Test: `apps/tasks/tests/test_views.py`

**Step 1: Write failing model test**

```python
# apps/tasks/tests/test_models.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.tasks.models import Task
from apps.contacts.models import Contact
from apps.accounts.models import User, Team

class TaskModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )

    def test_create_task(self):
        task = Task.objects.create(
            title="Call John",
            assigned_to=self.agent,
            contact=self.contact,
            due_date=timezone.now() + timedelta(days=1),
            team=self.team
        )
        self.assertEqual(task.status, 'pending')

    def test_overdue_task(self):
        task = Task.objects.create(
            title="Call John",
            assigned_to=self.agent,
            contact=self.contact,
            due_date=timezone.now() - timedelta(days=1),
            team=self.team
        )
        self.assertTrue(task.is_overdue)
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement Task model**

```python
# apps/tasks/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_tasks'
    )
    contact = models.ForeignKey(
        'contacts.Contact', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tasks'
    )
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='tasks')
    due_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']

    @property
    def is_overdue(self):
        return self.status == 'pending' and self.due_date < timezone.now()

    def complete(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def __str__(self):
        return self.title
```

**Step 4: Implement views**

- `TaskListView` — filter by: today, overdue, upcoming, by agent, by contact
- `TaskCreateView` — create task, optionally linked to a contact
- `task_complete` — mark task as done (AJAX-friendly)
- Quick-add from contact detail page

**Step 5: Write view tests, run all tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add Task model and views with overdue detection"
```

---

### Task 15: Smart Lists

**Files:**
- Create: `apps/contacts/smart_lists.py`
- Modify: `apps/contacts/models.py` (add SmartList model)
- Modify: `apps/contacts/views.py` (add smart list views)
- Create: `templates/contacts/smart_list_form.html`
- Create: `templates/contacts/smart_list_results.html`
- Test: `apps/contacts/tests/test_smart_lists.py`

**Step 1: Write failing test**

```python
# apps/contacts/tests/test_smart_lists.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.contacts.models import Contact, SmartList
from apps.accounts.models import User, Team

class SmartListTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )

    def test_filter_by_source(self):
        Contact.objects.create(
            first_name="A", last_name="B",
            source="landing_page", team=self.team
        )
        Contact.objects.create(
            first_name="C", last_name="D",
            source="manual", team=self.team
        )
        smart_list = SmartList.objects.create(
            name="Landing Page Leads",
            team=self.team,
            filters={"source": "landing_page"}
        )
        results = smart_list.get_contacts()
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().first_name, "A")

    def test_filter_no_contact_30_days(self):
        old = Contact.objects.create(
            first_name="Old", last_name="Lead", team=self.team,
            last_contacted_at=timezone.now() - timedelta(days=45)
        )
        recent = Contact.objects.create(
            first_name="Recent", last_name="Lead", team=self.team,
            last_contacted_at=timezone.now() - timedelta(days=5)
        )
        smart_list = SmartList.objects.create(
            name="No Contact 30 Days",
            team=self.team,
            filters={"last_contacted_days_ago_gt": 30}
        )
        results = smart_list.get_contacts()
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().first_name, "Old")
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement SmartList model with dynamic filtering**

```python
# Add to apps/contacts/models.py
class SmartList(models.Model):
    name = models.CharField(max_length=200)
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='smart_lists')
    filters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_contacts(self):
        qs = Contact.objects.filter(team=self.team)
        f = self.filters

        if 'source' in f:
            qs = qs.filter(source=f['source'])
        if 'assigned_to' in f:
            qs = qs.filter(assigned_to_id=f['assigned_to'])
        if 'tags_contain' in f:
            qs = qs.filter(tags__contains=f['tags_contain'])
        if 'last_contacted_days_ago_gt' in f:
            cutoff = timezone.now() - timedelta(days=f['last_contacted_days_ago_gt'])
            qs = qs.filter(
                models.Q(last_contacted_at__lt=cutoff) |
                models.Q(last_contacted_at__isnull=True)
            )
        if 'created_days_ago_lt' in f:
            cutoff = timezone.now() - timedelta(days=f['created_days_ago_lt'])
            qs = qs.filter(created_at__gte=cutoff)
        if 'has_deal_in_stage' in f:
            qs = qs.filter(deals__stage_id=f['has_deal_in_stage'])
        if 'no_deal' in f and f['no_deal']:
            qs = qs.filter(deals__isnull=True)

        return qs.distinct()

    def __str__(self):
        return self.name
```

**Step 4: Implement views for creating/viewing smart lists**

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add SmartList with dynamic contact filtering"
```

---

## Phase 7: Lead Capture API

### Task 16: REST API for Lead Capture

**Files:**
- Create: `apps/api/views.py`
- Create: `apps/api/urls.py`
- Create: `apps/api/serializers.py`
- Create: `apps/api/lead_routing.py`
- Test: `apps/api/tests/test_lead_capture.py`

**Step 1: Write failing test**

```python
# apps/api/tests/test_lead_capture.py
import json
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.contacts.models import Contact
from apps.campaigns.models import Campaign, CampaignStep

class LeadCaptureAPITest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent1 = User.objects.create_user(
            username="agent1", password="pass", team=self.team
        )
        self.agent2 = User.objects.create_user(
            username="agent2", password="pass", team=self.team
        )

    def test_capture_lead(self):
        response = self.client.post(
            '/api/leads/',
            json.dumps({
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
                'phone': '555-1234',
                'source': 'landing_page',
            }),
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Contact.objects.filter(email='john@example.com').exists())
        contact = Contact.objects.get(email='john@example.com')
        self.assertIsNotNone(contact.assigned_to)

    def test_lead_auto_enrolls_in_campaign(self):
        campaign = Campaign.objects.create(
            name="Default", team=self.team,
            created_by=self.agent1, is_active=True
        )
        CampaignStep.objects.create(
            campaign=campaign, order=1,
            delay_days=0, delay_hours=0,
            subject="Welcome", body="Hi"
        )
        # Set as default campaign in team settings (or via API param)
        response = self.client.post(
            '/api/leads/',
            json.dumps({
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane@example.com',
                'campaign_id': campaign.id,
            }),
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        self.assertEqual(response.status_code, 201)
        contact = Contact.objects.get(email='jane@example.com')
        self.assertTrue(contact.enrollments.filter(campaign=campaign).exists())

    def test_round_robin_assignment(self):
        for i in range(4):
            self.client.post(
                '/api/leads/',
                json.dumps({
                    'first_name': f'Lead{i}',
                    'last_name': 'Test',
                    'email': f'lead{i}@example.com',
                }),
                content_type='application/json',
                HTTP_X_API_KEY='test-api-key'
            )
        agent1_count = Contact.objects.filter(assigned_to=self.agent1).count()
        agent2_count = Contact.objects.filter(assigned_to=self.agent2).count()
        self.assertEqual(agent1_count, 2)
        self.assertEqual(agent2_count, 2)
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement lead routing**

```python
# apps/api/lead_routing.py
from apps.accounts.models import User
from apps.contacts.models import Contact

def round_robin_assign(team):
    """Assign to the agent with the fewest contacts."""
    agents = User.objects.filter(team=team, is_active=True)
    if not agents.exists():
        return None
    return agents.annotate(
        contact_count=models.Count('contacts')
    ).order_by('contact_count').first()
```

**Step 4: Implement API view**

```python
# apps/api/views.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.contacts.models import Contact, ContactActivity
from apps.campaigns.models import Campaign, CampaignEnrollment
from apps.api.lead_routing import round_robin_assign

@csrf_exempt
@require_POST
def capture_lead(request):
    # API key auth (simple)
    api_key = request.headers.get('X-Api-Key')
    team = validate_api_key(api_key)
    if not team:
        return JsonResponse({'error': 'Invalid API key'}, status=401)

    data = json.loads(request.body)

    # Create contact
    contact = Contact.objects.create(
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        source=data.get('source', 'landing_page'),
        source_detail=data.get('utm_source', ''),
        team=team,
        assigned_to=round_robin_assign(team)
    )

    # Log activity
    ContactActivity.objects.create(
        contact=contact,
        activity_type='campaign_enrolled',
        description=f"New lead captured from {contact.source}"
    )

    # Auto-enroll in campaign if specified
    campaign_id = data.get('campaign_id')
    if campaign_id:
        try:
            campaign = Campaign.objects.get(id=campaign_id, team=team, is_active=True)
            first_step = campaign.steps.first()
            if first_step:
                CampaignEnrollment.objects.create(
                    contact=contact,
                    campaign=campaign,
                    current_step=first_step,
                    next_send_at=timezone.now()
                )
        except Campaign.DoesNotExist:
            pass

    # TODO: Send notification to assigned agent

    return JsonResponse({
        'status': 'created',
        'contact_id': contact.id,
        'assigned_to': str(contact.assigned_to) if contact.assigned_to else None
    }, status=201)
```

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add lead capture API with round-robin assignment"
```

---

## Phase 8: Dashboard & Reporting

### Task 17: Dashboard

**Files:**
- Create: `apps/reports/views.py`
- Create: `apps/reports/urls.py`
- Create: `templates/dashboard.html`
- Test: `apps/reports/tests/test_views.py`

**Step 1: Write failing test**

```python
# apps/reports/tests/test_views.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team

class DashboardViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_dashboard_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_stats(self):
        response = self.client.get('/')
        self.assertContains(response, "Today")
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement dashboard view**

Dashboard displays:
- Today's tasks (due today, overdue)
- New leads this week
- Pipeline summary (deals per stage, total value)
- Recent activity feed
- Campaign performance snapshot

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add dashboard with stats and activity feed"
```

---

### Task 18: Reports

**Files:**
- Modify: `apps/reports/views.py`
- Create: `templates/reports/lead_source.html`
- Create: `templates/reports/conversion.html`
- Create: `templates/reports/agent_activity.html`
- Create: `templates/reports/campaign_performance.html`
- Test: `apps/reports/tests/test_reports.py`

**Step 1: Write failing test**

```python
# apps/reports/tests/test_reports.py
from django.test import TestCase, Client
from apps.accounts.models import User, Team
from apps.contacts.models import Contact

class ReportViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_lead_source_report(self):
        Contact.objects.create(
            first_name="A", last_name="B",
            source="landing_page", team=self.team
        )
        response = self.client.get('/reports/lead-sources/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Landing Page")
```

**Step 2: Run test — expect FAIL**

**Step 3: Implement report views**

- **Lead Source Report** — contacts grouped by source, with conversion rates
- **Conversion Report** — funnel from lead → each pipeline stage → closed
- **Agent Activity** — emails sent, tasks completed, deals closed per agent
- **Campaign Performance** — per campaign: enrolled, emails sent, opens, video views, replies
- Date range filters on all reports
- Simple charts via Chart.js (CDN)

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add reporting views with lead source and conversion reports"
```

---

## Phase 9: Settings & Polish

### Task 19: Settings Views

**Files:**
- Create: `apps/accounts/views_settings.py`
- Create: `templates/settings/team.html`
- Create: `templates/settings/pipelines.html`
- Create: `templates/settings/gmail.html`
- Create: `templates/settings/api_keys.html`
- Create: `templates/settings/lead_routing.html`

**Step 1: Implement settings pages**

- **Team Management** — invite users, set roles, deactivate
- **Pipeline Settings** — create/edit pipelines and stages
- **Gmail Connection** — OAuth connect/disconnect flow
- **API Keys** — generate/revoke keys for landing page integration
- **Lead Routing** — configure round-robin vs manual vs rule-based

**Step 2: Write tests for critical settings**

**Step 3: Commit**

```bash
git add .
git commit -m "feat: add settings pages for team, pipeline, Gmail, API keys"
```

---

### Task 20: Notifications

**Files:**
- Create: `apps/accounts/notifications.py`
- Create: `apps/tasks/tasks.py` (Celery task for reminders)
- Modify: `config/settings.py` (add to beat schedule)

**Step 1: Implement notification system**

- New lead notification → email to assigned agent
- Task due reminder → email 1 hour before due
- Overdue task alert → daily digest email

**Step 2: Add Celery beat schedules**

```python
CELERY_BEAT_SCHEDULE = {
    'process-due-campaign-emails': {
        'task': 'apps.campaigns.tasks.process_due_emails',
        'schedule': 300.0,
    },
    'send-task-reminders': {
        'task': 'apps.tasks.tasks.send_due_reminders',
        'schedule': 3600.0,  # Every hour
    },
}
```

**Step 3: Write tests, run all — expect PASS**

**Step 4: Commit**

```bash
git add .
git commit -m "feat: add email notifications for new leads and task reminders"
```

---

### Task 21: Landing Page Integration Guide

**Files:**
- Create: `templates/settings/integration_guide.html`

**Step 1: Create an in-app integration guide page**

Show the user exactly how to add a form to their Porkbun landing page that submits to the CRM API. Include:
- HTML form snippet they can copy/paste
- JavaScript fetch example
- API endpoint URL and required headers
- How to pass campaign_id for auto-enrollment

**Step 2: Commit**

```bash
git add .
git commit -m "feat: add landing page integration guide"
```

---

## Phase 10: Deployment

### Task 22: Production Configuration

**Files:**
- Create: `config/settings_production.py`
- Modify: `docker-compose.yml` (production overrides)
- Create: `docker-compose.prod.yml`
- Create: `nginx/nginx-ssl.conf`
- Create: `deploy.sh`

**Step 1: Create production settings**

- DEBUG=False
- Proper ALLOWED_HOSTS
- Secure cookies
- HTTPS redirect
- Database connection pooling

**Step 2: Create SSL Nginx config**

Use Certbot/Let's Encrypt for SSL on `crm.yourdomain.com`

**Step 3: Create deploy script**

```bash
#!/bin/bash
set -e
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker-compose exec web python manage.py migrate --noinput
docker-compose exec web python manage.py collectstatic --noinput
echo "Deployment complete!"
```

**Step 4: Commit**

```bash
git add .
git commit -m "feat: add production deployment config with SSL"
```

---

### Task 23: Create Superuser & Seed Default Data

**Files:**
- Create: `apps/accounts/management/commands/setup_initial_data.py`

**Step 1: Management command to seed defaults**

- Create default pipelines: "Buyer Pipeline" (New Lead → Contacted → Showing → Offer → Under Contract → Closed Won / Closed Lost), "Seller Pipeline" (New Lead → Listing Appointment → Listed → Under Contract → Closed)
- Create sample smart lists: "New This Week", "No Contact 30 Days", "Hot Leads"
- Create a sample drip campaign template

**Step 2: Commit**

```bash
git add .
git commit -m "feat: add management command for initial data seeding"
```

---

## Execution Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| 1 | 1-3 | Project scaffold, Docker setup |
| 2 | 4 | User auth, team management |
| 3 | 5-6 | Contact CRUD with activity tracking |
| 4 | 7-8 | Deal pipeline with Kanban board |
| 5 | 9-13 | Full drip campaign system with Gmail + video |
| 6 | 14-15 | Tasks/reminders + smart lists |
| 7 | 16 | Lead capture API |
| 8 | 17-18 | Dashboard + reports |
| 9 | 19-21 | Settings, notifications, integration guide |
| 10 | 22-23 | Production deployment |

**Total: 23 tasks across 10 phases**
