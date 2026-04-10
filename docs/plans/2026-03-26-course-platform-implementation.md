# Course Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Kajabi-style course platform as a new Django app with a separate student portal and CRM admin management.

**Architecture:** New `courses` Django app within the existing project. Student portal served on a subdomain (`courses.bigbeachal.com`) with its own base template (`portal_base.html`). CRM admin views use existing `base.html`. `SubdomainMiddleware` routes requests by subdomain. Celery handles drip scheduling.

**Tech Stack:** Django 5.1, PostgreSQL, Tailwind CSS (CDN), HTMX, Celery + Redis, embedded YouTube/Vimeo

---

### Task 1: Extend User Model with Student Role

**Files:**
- Modify: `apps/accounts/models.py` (add `student` role + `stripe_customer_id`)
- Create: `apps/accounts/migrations/XXXX_add_student_role.py` (auto-generated)

**Step 1: Add student role and stripe field to User model**

In `apps/accounts/models.py`, update `ROLE_CHOICES` and add field:

```python
ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('agent', 'Agent'),
    ('student', 'Student'),
]

role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='agent')
# ... existing fields ...
stripe_customer_id = models.CharField(max_length=255, blank=True, help_text='For future payment integration')
```

Also add a helper property:

```python
@property
def is_student(self):
    return self.role == 'student'
```

**Step 2: Generate migration**

Run: `docker-compose exec web python manage.py makemigrations accounts -n add_student_role`

**Step 3: Apply migration**

Run: `docker-compose exec web python manage.py migrate`

**Step 4: Commit**

```bash
git add apps/accounts/models.py apps/accounts/migrations/
git commit -m "feat(courses): add student role and stripe_customer_id to User model"
```

---

### Task 2: Create Courses App — Models

**Files:**
- Create: `apps/courses/__init__.py`
- Create: `apps/courses/apps.py`
- Create: `apps/courses/models.py`
- Create: `apps/courses/admin.py`

**Step 1: Create app directory structure**

Run: `mkdir -p apps/courses && touch apps/courses/__init__.py`

**Step 2: Create apps.py**

Create `apps/courses/apps.py`:

```python
from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courses'
    verbose_name = 'Courses'
```

**Step 3: Create models.py**

Create `apps/courses/models.py`:

```python
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Course(models.Model):
    UNLOCK_MODE_CHOICES = [
        ('time_drip', 'Time-based drip (weekly release)'),
        ('completion_based', 'Completion-based (unlock on finish)'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_taught',
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='courses',
    )
    unlock_mode = models.CharField(
        max_length=20,
        choices=UNLOCK_MODE_CHOICES,
        default='completion_based',
    )
    drip_interval_days = models.PositiveIntegerField(
        default=7,
        help_text='Days between module unlocks (only for time_drip mode)',
    )
    is_published = models.BooleanField(default=False)
    is_free = models.BooleanField(default=True)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='For future payment integration',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('portal:course_detail', kwargs={'slug': self.slug})

    @property
    def total_lessons(self):
        return Lesson.objects.filter(module__course=self).count()

    @property
    def total_modules(self):
        return self.modules.count()


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    @property
    def total_lessons(self):
        return self.lessons.count()


class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text='Lesson notes (HTML allowed)')
    video_url = models.URLField(blank=True, help_text='YouTube or Vimeo embed URL')
    pdf_file = models.FileField(upload_to='courses/pdfs/', blank=True)
    order = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['module', 'order']

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        """Convert a standard YouTube/Vimeo URL to an embeddable one."""
        url = self.video_url
        if not url:
            return ''
        # YouTube
        if 'youtube.com/watch' in url:
            video_id = url.split('v=')[1].split('&')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        # Vimeo
        if 'vimeo.com/' in url and 'player.vimeo.com' not in url:
            video_id = url.split('vimeo.com/')[1].split('?')[0]
            return f'https://player.vimeo.com/video/{video_id}'
        return url


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    current_module_unlocked = models.PositiveIntegerField(default=1)
    next_unlock_date = models.DateTimeField(null=True, blank=True)
    # Future payment fields
    payment_status = models.CharField(max_length=20, blank=True, default='free')
    stripe_payment_id = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student} enrolled in {self.course}"

    def is_module_unlocked(self, module_order):
        """Check if a module (by its order, 1-indexed) is unlocked for this student."""
        return module_order <= self.current_module_unlocked

    def unlock_next_module(self):
        """Unlock the next module. Returns True if a new module was unlocked."""
        total = self.course.total_modules
        if self.current_module_unlocked < total:
            self.current_module_unlocked += 1
            if self.course.unlock_mode == 'time_drip':
                self.next_unlock_date = timezone.now() + timezone.timedelta(
                    days=self.course.drip_interval_days
                )
            self.save()
            return True
        return False

    @property
    def progress_percent(self):
        total = self.course.total_lessons
        if total == 0:
            return 0
        completed = LessonProgress.objects.filter(
            student=self.student,
            lesson__module__course=self.course,
            is_completed=True,
        ).count()
        return int((completed / total) * 100)


class LessonProgress(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ['student', 'lesson']
        verbose_name_plural = 'lesson progress'

    def __str__(self):
        status = 'completed' if self.is_completed else 'in progress'
        return f"{self.student} - {self.lesson} ({status})"


class Announcement(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    body = models.TextField(help_text='Announcement content (HTML allowed)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_announcements',
    )
    send_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course.title}: {self.title}"
```

**Step 4: Create admin.py**

Create `apps/courses/admin.py`:

```python
from django.contrib import admin
from .models import Course, Module, Lesson, Enrollment, LessonProgress, Announcement


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'is_published', 'unlock_mode', 'created_at']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order']
    inlines = [LessonInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'enrolled_at', 'current_module_unlocked']


admin.site.register(Lesson)
admin.site.register(LessonProgress)
admin.site.register(Announcement)
```

**Step 5: Register app in settings**

In `config/settings.py`, add `'apps.courses'` to `PROJECT_APPS`.

**Step 6: Generate and apply migrations**

Run: `docker-compose exec web python manage.py makemigrations courses`
Run: `docker-compose exec web python manage.py migrate`

**Step 7: Commit**

```bash
git add apps/courses/ config/settings.py
git commit -m "feat(courses): add courses app with Course, Module, Lesson, Enrollment, LessonProgress, Announcement models"
```

---

### Task 3: Subdomain Middleware & Portal Routing

**Files:**
- Create: `apps/courses/middleware.py`
- Modify: `config/settings.py` (add middleware, add `PORTAL_SUBDOMAIN` setting)
- Modify: `config/urls.py` (add courses admin + portal URL includes)
- Create: `apps/courses/urls_admin.py` (CRM admin course management URLs)
- Create: `apps/courses/urls_portal.py` (student portal URLs)

**Step 1: Create middleware.py**

Create `apps/courses/middleware.py`:

```python
from django.conf import settings
from django.shortcuts import redirect


class SubdomainMiddleware:
    """
    Detect which subdomain the request is on and set request.portal.
    Redirect student users away from CRM paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # Strip port
        portal_subdomain = getattr(settings, 'PORTAL_SUBDOMAIN', 'courses')

        if host.startswith(f'{portal_subdomain}.'):
            request.portal = 'courses'
        else:
            request.portal = 'crm'

        # Block student users from CRM paths
        if (
            hasattr(request, 'user')
            and request.user.is_authenticated
            and getattr(request.user, 'role', '') == 'student'
            and request.portal == 'crm'
            and not request.path.startswith('/admin/')
        ):
            portal_url = getattr(settings, 'PORTAL_URL', '/')
            return redirect(portal_url)

        response = self.get_response(request)
        return response
```

**Step 2: Add middleware to settings**

In `config/settings.py`, add to `MIDDLEWARE` list after `HtmxMiddleware`:

```python
'apps.courses.middleware.SubdomainMiddleware',
```

Also add these settings at the bottom of the file (before the security section):

```python
# ---------------------------------------------------------------------------
# Course Portal
# ---------------------------------------------------------------------------

PORTAL_SUBDOMAIN = os.getenv('PORTAL_SUBDOMAIN', 'courses')
PORTAL_URL = os.getenv('PORTAL_URL', 'http://courses.localhost:8000')
```

Also add the portal subdomain to `ALLOWED_HOSTS` — it's already dynamic from env, just document in `.env.example`.

**Step 3: Create CRM admin URLs**

Create `apps/courses/urls_admin.py`:

```python
from django.urls import path
from . import views_admin

app_name = 'courses'

urlpatterns = [
    # Dashboard
    path('', views_admin.course_list, name='course_list'),
    path('dashboard/', views_admin.courses_dashboard, name='dashboard'),

    # Course CRUD
    path('create/', views_admin.course_create, name='course_create'),
    path('<int:pk>/edit/', views_admin.course_edit, name='course_edit'),
    path('<int:pk>/delete/', views_admin.course_delete, name='course_delete'),
    path('<int:pk>/publish/', views_admin.course_toggle_publish, name='course_toggle_publish'),

    # Module management
    path('<int:course_pk>/modules/add/', views_admin.module_add, name='module_add'),
    path('modules/<int:pk>/edit/', views_admin.module_edit, name='module_edit'),
    path('modules/<int:pk>/delete/', views_admin.module_delete, name='module_delete'),
    path('<int:course_pk>/modules/reorder/', views_admin.module_reorder, name='module_reorder'),

    # Lesson management
    path('modules/<int:module_pk>/lessons/add/', views_admin.lesson_add, name='lesson_add'),
    path('lessons/<int:pk>/edit/', views_admin.lesson_edit, name='lesson_edit'),
    path('lessons/<int:pk>/delete/', views_admin.lesson_delete, name='lesson_delete'),
    path('modules/<int:module_pk>/lessons/reorder/', views_admin.lesson_reorder, name='lesson_reorder'),

    # Student management
    path('<int:pk>/students/', views_admin.course_students, name='course_students'),
    path('<int:pk>/students/export/', views_admin.course_students_export, name='course_students_export'),
    path('<int:pk>/students/enroll/', views_admin.bulk_enroll, name='bulk_enroll'),

    # Stats
    path('<int:pk>/stats/', views_admin.course_stats, name='course_stats'),

    # Announcements
    path('<int:pk>/announcements/', views_admin.course_announcements, name='course_announcements'),
    path('<int:pk>/announcements/create/', views_admin.announcement_create, name='announcement_create'),
]
```

**Step 4: Create portal URLs**

Create `apps/courses/urls_portal.py`:

```python
from django.urls import path
from . import views_portal

app_name = 'portal'

urlpatterns = [
    # Public pages
    path('', views_portal.catalog, name='catalog'),
    path('signup/', views_portal.student_signup, name='signup'),
    path('login/', views_portal.student_login, name='login'),
    path('logout/', views_portal.student_logout, name='logout'),

    # Authenticated student pages
    path('dashboard/', views_portal.student_dashboard, name='dashboard'),
    path('profile/', views_portal.student_profile, name='profile'),

    # Course pages
    path('course/<slug:slug>/', views_portal.course_detail, name='course_detail'),
    path('course/<slug:slug>/enroll/', views_portal.course_enroll, name='course_enroll'),
    path('course/<slug:slug>/module/<int:module_order>/lesson/<int:lesson_order>/',
         views_portal.lesson_view, name='lesson_view'),

    # HTMX endpoints
    path('lesson/<int:pk>/complete/', views_portal.lesson_mark_complete, name='lesson_complete'),
]
```

**Step 5: Register URLs in root urlconf**

In `config/urls.py`, add:

```python
path('courses/', include('apps.courses.urls_admin')),
```

The portal URLs will be served separately — add conditional routing based on subdomain. Add this block in `config/urls.py`:

```python
# Portal URLs (served on courses subdomain, but registered at root)
# The SubdomainMiddleware + portal_base.html handles the visual separation
path('portal/', include('apps.courses.urls_portal')),
```

Note: For production with actual subdomains, Nginx will route `courses.bigbeachal.com` to the same Django app, and we can use `django-hosts` or a simple URL rewrite. For now, the portal is accessible at `/portal/` for development.

**Step 6: Commit**

```bash
git add apps/courses/middleware.py apps/courses/urls_admin.py apps/courses/urls_portal.py config/urls.py config/settings.py
git commit -m "feat(courses): add subdomain middleware and URL routing for portal and admin"
```

---

### Task 4: Portal Base Template & Student Auth

**Files:**
- Create: `templates/portal/portal_base.html`
- Create: `templates/portal/signup.html`
- Create: `templates/portal/login.html`
- Create: `apps/courses/views_portal.py` (signup, login, logout + catalog stub)
- Create: `apps/courses/forms.py`

**Step 1: Create portal base template**

Create `templates/portal/portal_base.html`:

```html
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}BigBeachAL Academy{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="h-full" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>

<!-- Top Navbar -->
<nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
            <div class="flex items-center space-x-8">
                <a href="{% url 'portal:catalog' %}" class="text-xl font-bold" style="font-family: 'Georgia', serif;">
                    <span style="color: #0ea5e9;">Big</span><span style="color: #1e293b;">Beach</span><span style="color: #d97706;">AL</span>
                    <span class="text-sm font-normal text-gray-400 ml-1">Academy</span>
                </a>
                <a href="{% url 'portal:catalog' %}"
                   class="text-sm font-medium {% if request.path == '/portal/' %}text-blue-600{% else %}text-gray-500 hover:text-gray-700{% endif %}">
                    Courses
                </a>
                {% if user.is_authenticated %}
                <a href="{% url 'portal:dashboard' %}"
                   class="text-sm font-medium {% if '/dashboard/' in request.path %}text-blue-600{% else %}text-gray-500 hover:text-gray-700{% endif %}">
                    My Dashboard
                </a>
                {% endif %}
            </div>
            <div class="flex items-center space-x-4">
                {% if user.is_authenticated %}
                    <span class="text-sm text-gray-600">{{ user.get_full_name|default:user.username }}</span>
                    <a href="{% url 'portal:profile' %}" class="text-sm text-gray-500 hover:text-gray-700">Profile</a>
                    <form method="post" action="{% url 'portal:logout' %}" class="inline">
                        {% csrf_token %}
                        <button type="submit" class="text-sm text-red-500 hover:text-red-700">Logout</button>
                    </form>
                {% else %}
                    <a href="{% url 'portal:login' %}" class="text-sm text-gray-600 hover:text-gray-800">Sign in</a>
                    <a href="{% url 'portal:signup' %}"
                       class="text-sm px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition">
                        Sign up free
                    </a>
                {% endif %}
            </div>
        </div>
    </div>
</nav>

<!-- Messages -->
{% if messages %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
    {% for message in messages %}
    <div class="mb-2 px-4 py-3 rounded-md text-sm
        {% if message.tags == 'success' %}bg-green-50 text-green-800 border border-green-200
        {% elif message.tags == 'error' %}bg-red-50 text-red-800 border border-red-200
        {% elif message.tags == 'warning' %}bg-yellow-50 text-yellow-800 border border-yellow-200
        {% else %}bg-blue-50 text-blue-800 border border-blue-200{% endif %}">
        {{ message }}
    </div>
    {% endfor %}
</div>
{% endif %}

<!-- Page Content -->
<main>
    {% block content %}{% endblock %}
</main>

<!-- Footer -->
<footer class="bg-white border-t border-gray-200 mt-16">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <p class="text-center text-sm text-gray-400">
            &copy; {% now "Y" %} BigBeachAL Academy. All rights reserved.
        </p>
    </div>
</footer>

{% block extra_js %}{% endblock %}
</body>
</html>
```

**Step 2: Create student signup form**

Create `apps/courses/forms.py`:

```python
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

FORM_INPUT_CLASS = (
    'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
)


class StudentSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = FORM_INPUT_CLASS

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CourseForm(forms.Form):
    """Used by CRM admin to create/edit courses."""
    title = forms.CharField(max_length=200)
    slug = forms.SlugField(max_length=100)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    thumbnail = forms.ImageField(required=False)
    unlock_mode = forms.ChoiceField(choices=[
        ('time_drip', 'Time-based drip (weekly release)'),
        ('completion_based', 'Completion-based (unlock on finish)'),
    ])
    drip_interval_days = forms.IntegerField(initial=7, min_value=1, required=False)
    is_free = forms.BooleanField(required=False, initial=True)
    price = forms.DecimalField(max_digits=8, decimal_places=2, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput)):
                field.widget.attrs['class'] = FORM_INPUT_CLASS


class ModuleForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = FORM_INPUT_CLASS


class LessonForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text='Lesson notes (HTML allowed)',
    )
    video_url = forms.URLField(required=False, help_text='YouTube or Vimeo URL')
    pdf_file = forms.FileField(required=False)
    duration_minutes = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = FORM_INPUT_CLASS


class AnnouncementForm(forms.Form):
    title = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    send_email = forms.BooleanField(required=False, label='Also send as email to enrolled students')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = FORM_INPUT_CLASS
```

**Step 3: Create portal views (auth + catalog)**

Create `apps/courses/views_portal.py`:

```python
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import StudentSignupForm
from .models import Course, Module, Lesson, Enrollment, LessonProgress, Announcement


def catalog(request):
    """Public course catalog — list all published courses."""
    courses = Course.objects.filter(is_published=True)

    # If student is logged in, annotate with enrollment status
    enrollments = {}
    if request.user.is_authenticated:
        for e in Enrollment.objects.filter(student=request.user):
            enrollments[e.course_id] = e

    return render(request, 'portal/catalog.html', {
        'courses': courses,
        'enrollments': enrollments,
    })


def student_signup(request):
    """Student registration page."""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        form = StudentSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Welcome! Your account has been created.')
            return redirect('portal:catalog')
    else:
        form = StudentSignupForm()

    return render(request, 'portal/signup.html', {'form': form})


def student_login(request):
    """Student login page."""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.role == 'student':
            login(request, user)
            next_url = request.GET.get('next', 'portal:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'portal/login.html')


@require_POST
def student_logout(request):
    """Log out student."""
    logout(request)
    return redirect('portal:catalog')


@login_required(login_url='/portal/login/')
def student_dashboard(request):
    """Student's enrolled courses with progress."""
    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course')

    # Get recent announcements for enrolled courses
    course_ids = [e.course_id for e in enrollments]
    announcements = Announcement.objects.filter(
        course_id__in=course_ids
    )[:5]

    # Find last incomplete lesson for "continue" link
    continue_lessons = {}
    for enrollment in enrollments:
        completed_ids = set(
            LessonProgress.objects.filter(
                student=request.user,
                lesson__module__course=enrollment.course,
                is_completed=True,
            ).values_list('lesson_id', flat=True)
        )
        lessons = Lesson.objects.filter(
            module__course=enrollment.course
        ).select_related('module').order_by('module__order', 'order')
        for lesson in lessons:
            if lesson.id not in completed_ids:
                continue_lessons[enrollment.course_id] = lesson
                break

    return render(request, 'portal/dashboard.html', {
        'enrollments': enrollments,
        'announcements': announcements,
        'continue_lessons': continue_lessons,
    })


def course_detail(request, slug):
    """Course overview page with module list."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    modules = course.modules.prefetch_related('lessons')

    enrollment = None
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            student=request.user, course=course
        ).first()

    return render(request, 'portal/course_detail.html', {
        'course': course,
        'modules': modules,
        'enrollment': enrollment,
    })


@login_required(login_url='/portal/login/')
@require_POST
def course_enroll(request, slug):
    """Enroll the current student in a course."""
    course = get_object_or_404(Course, slug=slug, is_published=True)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
        defaults={
            'current_module_unlocked': 1,
            'next_unlock_date': (
                timezone.now() + timezone.timedelta(days=course.drip_interval_days)
                if course.unlock_mode == 'time_drip'
                else None
            ),
        },
    )

    if created:
        messages.success(request, f'You are now enrolled in "{course.title}"!')
    else:
        messages.info(request, 'You are already enrolled in this course.')

    return redirect('portal:course_detail', slug=slug)


@login_required(login_url='/portal/login/')
def lesson_view(request, slug, module_order, lesson_order):
    """View a specific lesson — video player + notes."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    module = get_object_or_404(Module, course=course, order=module_order)
    lesson = get_object_or_404(Lesson, module=module, order=lesson_order)

    # Check if module is unlocked
    if not enrollment.is_module_unlocked(module.order):
        messages.warning(request, 'This module is not yet unlocked.')
        return redirect('portal:course_detail', slug=slug)

    # Create or get progress record
    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    # Get all lessons in this module for sidebar navigation
    module_lessons = module.lessons.all()

    # Get completed lesson IDs for checkmarks
    completed_ids = set(
        LessonProgress.objects.filter(
            student=request.user,
            lesson__module=module,
            is_completed=True,
        ).values_list('lesson_id', flat=True)
    )

    # All modules for navigation
    modules = course.modules.prefetch_related('lessons')

    return render(request, 'portal/lesson.html', {
        'course': course,
        'module': module,
        'lesson': lesson,
        'progress': progress,
        'module_lessons': module_lessons,
        'completed_ids': completed_ids,
        'modules': modules,
        'enrollment': enrollment,
    })


@login_required(login_url='/portal/login/')
@require_POST
def lesson_mark_complete(request, pk):
    """HTMX endpoint: mark a lesson as completed."""
    lesson = get_object_or_404(Lesson, pk=pk)
    course = lesson.module.course
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save()

        # For completion-based courses, check if module is fully complete
        if course.unlock_mode == 'completion_based':
            module = lesson.module
            total_lessons = module.lessons.count()
            completed_lessons = LessonProgress.objects.filter(
                student=request.user,
                lesson__module=module,
                is_completed=True,
            ).count()

            if completed_lessons >= total_lessons:
                enrollment.unlock_next_module()

    # Return updated checkmark HTML for HTMX swap
    return JsonResponse({
        'completed': True,
        'progress_percent': enrollment.progress_percent,
    })


@login_required(login_url='/portal/login/')
def student_profile(request):
    """Student profile/settings page."""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        messages.success(request, 'Profile updated.')
        return redirect('portal:profile')

    return render(request, 'portal/profile.html')
```

**Step 4: Create login template**

Create `templates/portal/login.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}Sign In - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="min-h-[80vh] flex items-center justify-center">
    <div class="w-full max-w-md">
        <div class="bg-white rounded-lg shadow-md p-8">
            <div class="text-center mb-8">
                <h1 class="text-2xl font-bold text-gray-900">Welcome back</h1>
                <p class="text-gray-500 mt-1">Sign in to your student account</p>
            </div>

            <form method="post" class="space-y-4">
                {% csrf_token %}
                <div>
                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                    <input type="text" name="username" id="username" required
                           class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                    <input type="password" name="password" id="password" required
                           class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <button type="submit"
                        class="w-full py-2 px-4 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition">
                    Sign in
                </button>
            </form>

            <p class="mt-6 text-center text-sm text-gray-500">
                Don't have an account?
                <a href="{% url 'portal:signup' %}" class="text-blue-600 hover:text-blue-500 font-medium">Sign up free</a>
            </p>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 5: Create signup template**

Create `templates/portal/signup.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}Sign Up - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="min-h-[80vh] flex items-center justify-center">
    <div class="w-full max-w-md">
        <div class="bg-white rounded-lg shadow-md p-8">
            <div class="text-center mb-8">
                <h1 class="text-2xl font-bold text-gray-900">Create your account</h1>
                <p class="text-gray-500 mt-1">Start learning with BigBeachAL Academy</p>
            </div>

            {% if form.errors %}
            <div class="mb-4 px-4 py-3 rounded-md bg-red-50 text-red-800 border border-red-200 text-sm">
                <ul class="list-disc list-inside">
                    {% for field in form %}
                        {% for error in field.errors %}
                        <li>{{ field.label }}: {{ error }}</li>
                        {% endfor %}
                    {% endfor %}
                    {% for error in form.non_field_errors %}
                    <li>{{ error }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}

            <form method="post" class="space-y-4">
                {% csrf_token %}
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label for="id_first_name" class="block text-sm font-medium text-gray-700 mb-1">First name</label>
                        {{ form.first_name }}
                    </div>
                    <div>
                        <label for="id_last_name" class="block text-sm font-medium text-gray-700 mb-1">Last name</label>
                        {{ form.last_name }}
                    </div>
                </div>
                <div>
                    <label for="id_email" class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    {{ form.email }}
                </div>
                <div>
                    <label for="id_username" class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                    {{ form.username }}
                </div>
                <div>
                    <label for="id_password1" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                    {{ form.password1 }}
                </div>
                <div>
                    <label for="id_password2" class="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
                    {{ form.password2 }}
                </div>
                <button type="submit"
                        class="w-full py-2 px-4 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition">
                    Create account
                </button>
            </form>

            <p class="mt-6 text-center text-sm text-gray-500">
                Already have an account?
                <a href="{% url 'portal:login' %}" class="text-blue-600 hover:text-blue-500 font-medium">Sign in</a>
            </p>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 6: Commit**

```bash
git add templates/portal/ apps/courses/views_portal.py apps/courses/forms.py
git commit -m "feat(courses): add student portal auth (signup, login, logout) with portal base template"
```

---

### Task 5: Student Portal Templates (Catalog, Dashboard, Course Detail, Lesson View)

**Files:**
- Create: `templates/portal/catalog.html`
- Create: `templates/portal/dashboard.html`
- Create: `templates/portal/course_detail.html`
- Create: `templates/portal/lesson.html`
- Create: `templates/portal/profile.html`

**Step 1: Create catalog template**

Create `templates/portal/catalog.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}Courses - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="text-center mb-12">
        <h1 class="text-3xl font-bold text-gray-900">Available Courses</h1>
        <p class="mt-2 text-gray-500">Build your real estate skills with our training programs</p>
    </div>

    {% if courses %}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {% for course in courses %}
        <a href="{% url 'portal:course_detail' slug=course.slug %}"
           class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition group">
            {% if course.thumbnail %}
            <img src="{{ course.thumbnail.url }}" alt="{{ course.title }}" class="w-full h-48 object-cover">
            {% else %}
            <div class="w-full h-48 bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <svg class="w-16 h-16 text-white/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                          d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                </svg>
            </div>
            {% endif %}
            <div class="p-6">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-medium px-2 py-1 rounded-full
                        {% if course.is_free %}bg-green-100 text-green-700{% else %}bg-blue-100 text-blue-700{% endif %}">
                        {% if course.is_free %}Free{% else %}${{ course.price }}{% endif %}
                    </span>
                    <span class="text-xs text-gray-400">{{ course.total_lessons }} lessons</span>
                </div>
                <h3 class="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition">{{ course.title }}</h3>
                <p class="mt-2 text-sm text-gray-500 line-clamp-2">{{ course.description|truncatewords:25 }}</p>

                {% if course.id in enrollments %}
                <div class="mt-4">
                    <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>{{ enrollments|dictsort:"course_id" }}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full" style="width: {{ enrollments.progress_percent }}%"></div>
                    </div>
                </div>
                {% endif %}
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-16 text-gray-400">
        <p class="text-lg">No courses available yet. Check back soon!</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 2: Create dashboard template**

Create `templates/portal/dashboard.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}My Dashboard - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <h1 class="text-2xl font-bold text-gray-900 mb-8">My Dashboard</h1>

    {% if announcements %}
    <div class="mb-8">
        <h2 class="text-lg font-semibold text-gray-700 mb-3">Recent Announcements</h2>
        {% for ann in announcements %}
        <div class="bg-blue-50 border border-blue-200 rounded-md p-4 mb-2">
            <p class="text-sm font-medium text-blue-800">{{ ann.title }}</p>
            <p class="text-xs text-blue-600 mt-1">{{ ann.course.title }} &middot; {{ ann.created_at|timesince }} ago</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <h2 class="text-lg font-semibold text-gray-700 mb-4">My Courses</h2>

    {% if enrollments %}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {% for enrollment in enrollments %}
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {% if enrollment.course.thumbnail %}
            <img src="{{ enrollment.course.thumbnail.url }}" alt="{{ enrollment.course.title }}" class="w-full h-40 object-cover">
            {% else %}
            <div class="w-full h-40 bg-gradient-to-br from-blue-500 to-indigo-600"></div>
            {% endif %}
            <div class="p-5">
                <h3 class="font-semibold text-gray-900">{{ enrollment.course.title }}</h3>
                <div class="mt-3">
                    <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>{{ enrollment.progress_percent }}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: {{ enrollment.progress_percent }}%"></div>
                    </div>
                </div>
                <div class="mt-4 flex items-center justify-between">
                    {% if enrollment.course.id in continue_lessons %}
                    {% with lesson=continue_lessons|dictsort:"course_id" %}
                    <a href="{% url 'portal:course_detail' slug=enrollment.course.slug %}"
                       class="text-sm text-blue-600 hover:text-blue-800 font-medium">Continue learning &rarr;</a>
                    {% endwith %}
                    {% else %}
                    <a href="{% url 'portal:course_detail' slug=enrollment.course.slug %}"
                       class="text-sm text-blue-600 hover:text-blue-800 font-medium">View course</a>
                    {% endif %}
                    <span class="text-xs text-gray-400">Enrolled {{ enrollment.enrolled_at|timesince }} ago</span>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-12 bg-white rounded-lg border border-gray-200">
        <p class="text-gray-500 mb-4">You haven't enrolled in any courses yet.</p>
        <a href="{% url 'portal:catalog' %}" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition">Browse courses</a>
    </div>
    {% endif %}
</div>
{% endblock %}
```

**Step 3: Create course detail template**

Create `templates/portal/course_detail.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}{{ course.title }} - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <!-- Hero -->
    <div class="mb-8">
        {% if course.thumbnail %}
        <img src="{{ course.thumbnail.url }}" alt="{{ course.title }}" class="w-full h-64 object-cover rounded-lg mb-6">
        {% endif %}
        <div class="flex items-center justify-between">
            <div>
                <h1 class="text-3xl font-bold text-gray-900">{{ course.title }}</h1>
                <p class="mt-1 text-sm text-gray-500">
                    By {{ course.instructor.get_full_name|default:course.instructor.username }}
                    &middot; {{ course.total_modules }} modules &middot; {{ course.total_lessons }} lessons
                </p>
            </div>
            <span class="text-sm font-medium px-3 py-1 rounded-full
                {% if course.is_free %}bg-green-100 text-green-700{% else %}bg-blue-100 text-blue-700{% endif %}">
                {% if course.is_free %}Free{% else %}${{ course.price }}{% endif %}
            </span>
        </div>
        {% if course.description %}
        <p class="mt-4 text-gray-600 leading-relaxed">{{ course.description }}</p>
        {% endif %}
    </div>

    <!-- Enroll / Progress -->
    {% if enrollment %}
    <div class="bg-white border border-gray-200 rounded-lg p-4 mb-8">
        <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-700">Your progress</span>
            <span class="text-sm text-gray-500">{{ enrollment.progress_percent }}% complete</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-3">
            <div class="bg-blue-600 h-3 rounded-full transition-all" style="width: {{ enrollment.progress_percent }}%"></div>
        </div>
    </div>
    {% else %}
    <form method="post" action="{% url 'portal:course_enroll' slug=course.slug %}" class="mb-8">
        {% csrf_token %}
        <button type="submit"
                class="w-full py-3 px-6 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition text-lg">
            Enroll Now {% if not course.is_free %}&mdash; ${{ course.price }}{% endif %}
        </button>
    </form>
    {% endif %}

    <!-- Module List -->
    <div class="space-y-4">
        {% for module in modules %}
        {% with module_num=forloop.counter %}
        <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div class="px-6 py-4 flex items-center justify-between
                {% if enrollment and enrollment.is_module_unlocked == module_num %}{% else %}{% if enrollment %}bg-gray-50{% endif %}{% endif %}">
                <div class="flex items-center space-x-3">
                    {% if enrollment and module.order <= enrollment.current_module_unlocked %}
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-700 text-sm font-bold">{{ module_num }}</span>
                    {% else %}
                    <span class="flex items-center justify-center w-8 h-8 rounded-full bg-gray-200 text-gray-400 text-sm font-bold">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                        </svg>
                    </span>
                    {% endif %}
                    <div>
                        <h3 class="font-semibold text-gray-900">{{ module.title }}</h3>
                        <p class="text-xs text-gray-500">{{ module.total_lessons }} lessons</p>
                    </div>
                </div>
                {% if enrollment and module.order > enrollment.current_module_unlocked %}
                    {% if course.unlock_mode == 'time_drip' and enrollment.next_unlock_date %}
                    <span class="text-xs text-gray-400">Unlocks {{ enrollment.next_unlock_date|date:"M d" }}</span>
                    {% else %}
                    <span class="text-xs text-gray-400">Complete previous module to unlock</span>
                    {% endif %}
                {% endif %}
            </div>

            {% if not enrollment or module.order <= enrollment.current_module_unlocked %}
            <div class="border-t border-gray-100">
                {% for lesson in module.lessons.all %}
                <a href="{% if enrollment %}{% url 'portal:lesson_view' slug=course.slug module_order=module.order lesson_order=lesson.order %}{% else %}#{% endif %}"
                   class="flex items-center px-6 py-3 hover:bg-gray-50 transition {% if not enrollment %}opacity-50 cursor-default{% endif %}">
                    <svg class="w-5 h-5 mr-3 {% if lesson.id in completed_ids %}text-green-500{% else %}text-gray-300{% endif %}"
                         fill="{% if lesson.id in completed_ids %}currentColor{% else %}none{% endif %}"
                         stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span class="text-sm text-gray-700">{{ lesson.title }}</span>
                    {% if lesson.duration_minutes %}
                    <span class="ml-auto text-xs text-gray-400">{{ lesson.duration_minutes }} min</span>
                    {% endif %}
                </a>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endwith %}
        {% endfor %}
    </div>
</div>
{% endblock %}
```

**Step 4: Create lesson view template**

Create `templates/portal/lesson.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}{{ lesson.title }} - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Breadcrumb -->
    <nav class="text-sm text-gray-500 mb-6">
        <a href="{% url 'portal:course_detail' slug=course.slug %}" class="hover:text-blue-600">{{ course.title }}</a>
        <span class="mx-2">&rarr;</span>
        <span>{{ module.title }}</span>
        <span class="mx-2">&rarr;</span>
        <span class="text-gray-900">{{ lesson.title }}</span>
    </nav>

    <div class="lg:flex lg:space-x-8">
        <!-- Main content -->
        <div class="lg:flex-1">
            <!-- Video -->
            {% if lesson.embed_url %}
            <div class="relative w-full" style="padding-bottom: 56.25%;">
                <iframe src="{{ lesson.embed_url }}"
                        class="absolute inset-0 w-full h-full rounded-lg"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen></iframe>
            </div>
            {% endif %}

            <!-- Lesson title & completion -->
            <div class="mt-6 flex items-center justify-between">
                <h1 class="text-2xl font-bold text-gray-900">{{ lesson.title }}</h1>
                <div id="completion-status">
                    {% if progress.is_completed %}
                    <span class="flex items-center text-sm text-green-600 font-medium">
                        <svg class="w-5 h-5 mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Completed
                    </span>
                    {% else %}
                    <button hx-post="{% url 'portal:lesson_complete' pk=lesson.pk %}"
                            hx-target="#completion-status"
                            hx-swap="innerHTML"
                            class="text-sm px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 transition">
                        Mark complete
                    </button>
                    {% endif %}
                </div>
            </div>

            {% if lesson.duration_minutes %}
            <p class="text-sm text-gray-400 mt-1">{{ lesson.duration_minutes }} minutes</p>
            {% endif %}

            <!-- PDF download -->
            {% if lesson.pdf_file %}
            <div class="mt-4">
                <a href="{{ lesson.pdf_file.url }}"
                   class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
                   download>
                    <svg class="w-5 h-5 mr-2 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    Download PDF
                </a>
            </div>
            {% endif %}

            <!-- Lesson notes -->
            {% if lesson.description %}
            <div class="mt-6 prose prose-sm max-w-none text-gray-700">
                {{ lesson.description|safe }}
            </div>
            {% endif %}
        </div>

        <!-- Sidebar: Module navigation -->
        <div class="lg:w-80 mt-8 lg:mt-0">
            <div class="bg-white border border-gray-200 rounded-lg sticky top-20">
                <div class="px-4 py-3 border-b border-gray-200">
                    <h3 class="text-sm font-semibold text-gray-700">{{ module.title }}</h3>
                </div>
                <div class="divide-y divide-gray-100">
                    {% for l in module_lessons %}
                    <a href="{% url 'portal:lesson_view' slug=course.slug module_order=module.order lesson_order=l.order %}"
                       class="flex items-center px-4 py-3 text-sm hover:bg-gray-50 transition
                           {% if l.id == lesson.id %}bg-blue-50 text-blue-700{% else %}text-gray-600{% endif %}">
                        {% if l.id in completed_ids %}
                        <svg class="w-4 h-4 mr-2 text-green-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        {% elif l.id == lesson.id %}
                        <svg class="w-4 h-4 mr-2 text-blue-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                            <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        {% else %}
                        <span class="w-4 h-4 mr-2 flex-shrink-0 rounded-full border-2 border-gray-300"></span>
                        {% endif %}
                        <span class="truncate">{{ l.title }}</span>
                    </a>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>

{% block extra_js %}
{% if not progress.is_completed %}
<script>
    // Auto-mark lesson complete after 30 seconds
    setTimeout(function() {
        htmx.ajax('POST', '{% url "portal:lesson_complete" pk=lesson.pk %}', {
            target: '#completion-status',
            swap: 'innerHTML'
        });
    }, 30000);
</script>
{% endif %}
{% endblock %}
```

**Step 5: Create profile template**

Create `templates/portal/profile.html`:

```html
{% extends "portal/portal_base.html" %}

{% block title %}Profile - BigBeachAL Academy{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <h1 class="text-2xl font-bold text-gray-900 mb-8">Profile Settings</h1>

    <form method="post" class="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        {% csrf_token %}
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">First name</label>
                <input type="text" name="first_name" value="{{ user.first_name }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Last name</label>
                <input type="text" name="last_name" value="{{ user.last_name }}"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" name="email" value="{{ user.email }}"
                   class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input type="text" value="{{ user.username }}" disabled
                   class="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-gray-500">
        </div>
        <button type="submit"
                class="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition">
            Save changes
        </button>
    </form>
</div>
{% endblock %}
```

**Step 6: Commit**

```bash
git add templates/portal/
git commit -m "feat(courses): add student portal templates (catalog, dashboard, course detail, lesson view, profile)"
```

---

### Task 6: CRM Admin Views for Course Management

**Files:**
- Create: `apps/courses/views_admin.py`
- Create: `templates/courses/course_list.html`
- Create: `templates/courses/course_form.html`
- Create: `templates/courses/course_edit.html`
- Create: `templates/courses/course_students.html`
- Create: `templates/courses/course_stats.html`
- Create: `templates/courses/courses_dashboard.html`
- Create: `templates/courses/announcement_form.html`
- Modify: `templates/base.html` (add Courses nav link)

**Step 1: Create admin views**

Create `apps/courses/views_admin.py`:

```python
import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import CourseForm, ModuleForm, LessonForm, AnnouncementForm
from .models import Course, Module, Lesson, Enrollment, LessonProgress, Announcement

User = get_user_model()


@login_required
def course_list(request):
    """List all courses for the team."""
    courses = Course.objects.filter(team=request.user.team).annotate(
        enrollment_count=Count('enrollments'),
    )
    return render(request, 'courses/course_list.html', {'courses': courses})


@login_required
def courses_dashboard(request):
    """Analytics dashboard for all courses."""
    team = request.user.team
    courses = Course.objects.filter(team=team)

    total_students = Enrollment.objects.filter(course__team=team).values('student').distinct().count()
    active_students = Enrollment.objects.filter(
        course__team=team,
        student__last_login__gte=timezone.now() - timezone.timedelta(days=7),
    ).values('student').distinct().count()

    course_stats = []
    for course in courses:
        enrollments = course.enrollments.all()
        enrollment_count = enrollments.count()
        if enrollment_count > 0:
            total_progress = sum(e.progress_percent for e in enrollments)
            avg_completion = total_progress / enrollment_count
        else:
            avg_completion = 0

        course_stats.append({
            'course': course,
            'enrollment_count': enrollment_count,
            'avg_completion': round(avg_completion),
        })

    return render(request, 'courses/courses_dashboard.html', {
        'total_students': total_students,
        'active_students': active_students,
        'total_courses': courses.count(),
        'published_courses': courses.filter(is_published=True).count(),
        'course_stats': course_stats,
    })


@login_required
def course_create(request):
    """Create a new course."""
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = Course.objects.create(
                title=form.cleaned_data['title'],
                slug=form.cleaned_data['slug'] or slugify(form.cleaned_data['title']),
                description=form.cleaned_data.get('description', ''),
                thumbnail=form.cleaned_data.get('thumbnail'),
                instructor=request.user,
                team=request.user.team,
                unlock_mode=form.cleaned_data['unlock_mode'],
                drip_interval_days=form.cleaned_data.get('drip_interval_days') or 7,
                is_free=form.cleaned_data.get('is_free', True),
                price=form.cleaned_data.get('price'),
            )
            messages.success(request, f'Course "{course.title}" created. Now add modules and lessons.')
            return redirect('courses:course_edit', pk=course.pk)
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {'form': form, 'is_edit': False})


@login_required
def course_edit(request, pk):
    """Edit course details + manage modules & lessons."""
    course = get_object_or_404(Course, pk=pk, team=request.user.team)

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course.title = form.cleaned_data['title']
            course.slug = form.cleaned_data['slug'] or slugify(form.cleaned_data['title'])
            course.description = form.cleaned_data.get('description', '')
            if form.cleaned_data.get('thumbnail'):
                course.thumbnail = form.cleaned_data['thumbnail']
            course.unlock_mode = form.cleaned_data['unlock_mode']
            course.drip_interval_days = form.cleaned_data.get('drip_interval_days') or 7
            course.is_free = form.cleaned_data.get('is_free', True)
            course.price = form.cleaned_data.get('price')
            course.save()
            messages.success(request, 'Course updated.')
            return redirect('courses:course_edit', pk=course.pk)
    else:
        form = CourseForm(initial={
            'title': course.title,
            'slug': course.slug,
            'description': course.description,
            'unlock_mode': course.unlock_mode,
            'drip_interval_days': course.drip_interval_days,
            'is_free': course.is_free,
            'price': course.price,
        })

    modules = course.modules.prefetch_related('lessons')

    return render(request, 'courses/course_edit.html', {
        'form': form,
        'course': course,
        'modules': modules,
        'module_form': ModuleForm(),
        'lesson_form': LessonForm(),
    })


@login_required
@require_POST
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    title = course.title
    course.delete()
    messages.success(request, f'Course "{title}" deleted.')
    return redirect('courses:course_list')


@login_required
@require_POST
def course_toggle_publish(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    course.is_published = not course.is_published
    course.save()
    status = 'published' if course.is_published else 'unpublished'
    messages.success(request, f'Course "{course.title}" is now {status}.')
    return redirect('courses:course_edit', pk=course.pk)


# -- Module Management --

@login_required
@require_POST
def module_add(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, team=request.user.team)
    form = ModuleForm(request.POST)
    if form.is_valid():
        last_order = course.modules.count()
        Module.objects.create(
            course=course,
            title=form.cleaned_data['title'],
            description=form.cleaned_data.get('description', ''),
            order=last_order + 1,
        )
        messages.success(request, 'Module added.')
    return redirect('courses:course_edit', pk=course.pk)


@login_required
@require_POST
def module_edit(request, pk):
    module = get_object_or_404(Module, pk=pk, course__team=request.user.team)
    form = ModuleForm(request.POST)
    if form.is_valid():
        module.title = form.cleaned_data['title']
        module.description = form.cleaned_data.get('description', '')
        module.save()
        messages.success(request, 'Module updated.')
    return redirect('courses:course_edit', pk=module.course.pk)


@login_required
@require_POST
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk, course__team=request.user.team)
    course_pk = module.course.pk
    module.delete()
    messages.success(request, 'Module deleted.')
    return redirect('courses:course_edit', pk=course_pk)


@login_required
@require_POST
def module_reorder(request, course_pk):
    """HTMX: reorder modules via JSON body."""
    course = get_object_or_404(Course, pk=course_pk, team=request.user.team)
    import json
    try:
        order_data = json.loads(request.body)
        for item in order_data:
            Module.objects.filter(pk=item['id'], course=course).update(order=item['order'])
    except (json.JSONDecodeError, KeyError):
        pass
    return JsonResponse({'status': 'ok'})


# -- Lesson Management --

@login_required
@require_POST
def lesson_add(request, module_pk):
    module = get_object_or_404(Module, pk=module_pk, course__team=request.user.team)
    form = LessonForm(request.POST, request.FILES)
    if form.is_valid():
        last_order = module.lessons.count()
        Lesson.objects.create(
            module=module,
            title=form.cleaned_data['title'],
            description=form.cleaned_data.get('description', ''),
            video_url=form.cleaned_data.get('video_url', ''),
            pdf_file=form.cleaned_data.get('pdf_file'),
            duration_minutes=form.cleaned_data.get('duration_minutes'),
            order=last_order + 1,
        )
        messages.success(request, 'Lesson added.')
    return redirect('courses:course_edit', pk=module.course.pk)


@login_required
@require_POST
def lesson_edit(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course__team=request.user.team)
    form = LessonForm(request.POST, request.FILES)
    if form.is_valid():
        lesson.title = form.cleaned_data['title']
        lesson.description = form.cleaned_data.get('description', '')
        lesson.video_url = form.cleaned_data.get('video_url', '')
        if form.cleaned_data.get('pdf_file'):
            lesson.pdf_file = form.cleaned_data['pdf_file']
        lesson.duration_minutes = form.cleaned_data.get('duration_minutes')
        lesson.save()
        messages.success(request, 'Lesson updated.')
    return redirect('courses:course_edit', pk=lesson.module.course.pk)


@login_required
@require_POST
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course__team=request.user.team)
    course_pk = lesson.module.course.pk
    lesson.delete()
    messages.success(request, 'Lesson deleted.')
    return redirect('courses:course_edit', pk=course_pk)


@login_required
@require_POST
def lesson_reorder(request, module_pk):
    """HTMX: reorder lessons via JSON body."""
    module = get_object_or_404(Module, pk=module_pk, course__team=request.user.team)
    import json
    try:
        order_data = json.loads(request.body)
        for item in order_data:
            Lesson.objects.filter(pk=item['id'], module=module).update(order=item['order'])
    except (json.JSONDecodeError, KeyError):
        pass
    return JsonResponse({'status': 'ok'})


# -- Student Management --

@login_required
def course_students(request, pk):
    """List enrolled students with progress."""
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student').order_by('-enrolled_at')

    return render(request, 'courses/course_students.html', {
        'course': course,
        'enrollments': enrollments,
    })


@login_required
def course_students_export(request, pk):
    """Export students as CSV."""
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.slug}-students.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Username', 'Enrolled Date', 'Progress %'])
    for e in enrollments:
        writer.writerow([
            e.student.get_full_name(),
            e.student.email,
            e.student.username,
            e.enrolled_at.strftime('%Y-%m-%d'),
            e.progress_percent,
        ])

    return response


@login_required
@require_POST
def bulk_enroll(request, pk):
    """Enroll students by email (one per line)."""
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    emails = request.POST.get('emails', '').strip().split('\n')
    enrolled = 0
    not_found = []

    for email in emails:
        email = email.strip()
        if not email:
            continue
        try:
            user = User.objects.get(email__iexact=email, role='student')
            _, created = Enrollment.objects.get_or_create(
                student=user, course=course,
                defaults={'current_module_unlocked': 1},
            )
            if created:
                enrolled += 1
        except User.DoesNotExist:
            not_found.append(email)

    msg = f'{enrolled} student(s) enrolled.'
    if not_found:
        msg += f' Not found: {", ".join(not_found)}'
    messages.info(request, msg)
    return redirect('courses:course_students', pk=course.pk)


# -- Stats --

@login_required
def course_stats(request, pk):
    """Course engagement statistics."""
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student')

    total_enrolled = enrollments.count()
    avg_progress = sum(e.progress_percent for e in enrollments) / total_enrolled if total_enrolled else 0

    # Per-module completion
    modules = course.modules.prefetch_related('lessons')
    module_stats = []
    for module in modules:
        lesson_ids = list(module.lessons.values_list('id', flat=True))
        if lesson_ids and total_enrolled:
            completions = LessonProgress.objects.filter(
                lesson_id__in=lesson_ids,
                is_completed=True,
            ).count()
            possible = len(lesson_ids) * total_enrolled
            pct = round((completions / possible) * 100) if possible else 0
        else:
            pct = 0
        module_stats.append({'module': module, 'completion_pct': pct})

    # Most/least watched lessons
    lesson_stats = []
    for module in modules:
        for lesson in module.lessons.all():
            views = LessonProgress.objects.filter(lesson=lesson).count()
            completions = LessonProgress.objects.filter(lesson=lesson, is_completed=True).count()
            lesson_stats.append({
                'lesson': lesson,
                'module': module,
                'views': views,
                'completions': completions,
            })

    lesson_stats.sort(key=lambda x: x['views'], reverse=True)

    return render(request, 'courses/course_stats.html', {
        'course': course,
        'total_enrolled': total_enrolled,
        'avg_progress': round(avg_progress),
        'module_stats': module_stats,
        'lesson_stats': lesson_stats,
    })


# -- Announcements --

@login_required
def course_announcements(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    announcements = course.announcements.all()
    return render(request, 'courses/course_announcements.html', {
        'course': course,
        'announcements': announcements,
        'form': AnnouncementForm(),
    })


@login_required
@require_POST
def announcement_create(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    form = AnnouncementForm(request.POST)
    if form.is_valid():
        announcement = Announcement.objects.create(
            course=course,
            title=form.cleaned_data['title'],
            body=form.cleaned_data['body'],
            created_by=request.user,
            send_email=form.cleaned_data.get('send_email', False),
        )
        if announcement.send_email:
            from .tasks import send_announcement_email
            send_announcement_email.delay(announcement.pk)
        messages.success(request, 'Announcement posted.')
    return redirect('courses:course_announcements', pk=course.pk)
```

**Step 2: Add Courses nav link to base.html**

In `templates/base.html`, add between the Scheduling and Reports nav links:

```html
<a href="/courses/"
   class="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-800 {% if '/courses/' in request.path %}bg-gray-800 text-white{% else %}text-gray-300{% endif %}">
    <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
    Courses
</a>
```

**Step 3: Create CRM admin templates**

These follow the same Tailwind + HTMX patterns as existing CRM templates. Templates for:
- `templates/courses/course_list.html` — table of courses with enrollment counts, publish toggle
- `templates/courses/course_form.html` — create course form
- `templates/courses/course_edit.html` — edit course details + manage modules/lessons inline (accordion-style)
- `templates/courses/course_students.html` — enrolled students table
- `templates/courses/course_stats.html` — engagement metrics
- `templates/courses/courses_dashboard.html` — overall stats cards + per-course table
- `templates/courses/course_announcements.html` — announcement list + create form

Each template extends `base.html` and follows the same structure as `scheduling/event_type_list.html`, `scheduling/booking_list.html`, etc.

**Step 4: Commit**

```bash
git add apps/courses/views_admin.py templates/courses/ templates/base.html
git commit -m "feat(courses): add CRM admin views and templates for course management"
```

---

### Task 7: Celery Task for Time-Based Drip Unlocks

**Files:**
- Create: `apps/courses/tasks.py`
- Modify: `config/settings.py` (add to `CELERY_BEAT_SCHEDULE`)

**Step 1: Create tasks.py**

Create `apps/courses/tasks.py`:

```python
from celery import shared_task
from django.utils import timezone


@shared_task
def process_drip_unlocks():
    """Check all time_drip enrollments and unlock modules where next_unlock_date has passed."""
    from .models import Enrollment

    due_enrollments = Enrollment.objects.filter(
        course__unlock_mode='time_drip',
        next_unlock_date__lte=timezone.now(),
        next_unlock_date__isnull=False,
    ).select_related('course')

    unlocked = 0
    for enrollment in due_enrollments:
        if enrollment.current_module_unlocked < enrollment.course.total_modules:
            enrollment.current_module_unlocked += 1
            enrollment.next_unlock_date = timezone.now() + timezone.timedelta(
                days=enrollment.course.drip_interval_days
            )
            enrollment.save()
            unlocked += 1
        else:
            # All modules already unlocked — clear the next_unlock_date
            enrollment.next_unlock_date = None
            enrollment.save()

    return f'{unlocked} module(s) unlocked'


@shared_task
def send_announcement_email(announcement_pk):
    """Send announcement email to all enrolled students."""
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from .models import Announcement

    announcement = Announcement.objects.select_related('course').get(pk=announcement_pk)
    enrolled_emails = list(
        announcement.course.enrollments.values_list('student__email', flat=True)
    )

    if not enrolled_emails:
        return 'No enrolled students'

    send_mail(
        subject=f'[{announcement.course.title}] {announcement.title}',
        message=announcement.body,
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=enrolled_emails,
        fail_silently=True,
    )

    return f'Sent to {len(enrolled_emails)} student(s)'
```

**Step 2: Add to Celery beat schedule**

In `config/settings.py`, add to `CELERY_BEAT_SCHEDULE`:

```python
'process-course-drip-unlocks': {
    'task': 'apps.courses.tasks.process_drip_unlocks',
    'schedule': crontab(hour=0, minute=30),  # Daily at 12:30 AM
},
```

**Step 3: Commit**

```bash
git add apps/courses/tasks.py config/settings.py
git commit -m "feat(courses): add Celery tasks for drip unlock scheduling and announcement emails"
```

---

### Task 8: Nginx Configuration for Subdomain

**Files:**
- Modify: `nginx/default.conf` (add `courses.bigbeachal.com` server block)
- Modify: `.env.example` (document portal settings)

**Step 1: Add subdomain to Nginx**

Add a new `server` block in Nginx config (or add `courses.bigbeachal.com` to the existing `server_name` directive — since both subdomains route to the same Django app, the simplest approach is):

```nginx
server_name crm.bigbeachal.com courses.bigbeachal.com;
```

Django's `SubdomainMiddleware` handles the routing from there.

**Step 2: Update ALLOWED_HOSTS in .env.example**

```
ALLOWED_HOSTS=crm.bigbeachal.com,courses.bigbeachal.com,localhost
PORTAL_SUBDOMAIN=courses
PORTAL_URL=https://courses.bigbeachal.com
```

**Step 3: Add DNS record**

Add a CNAME or A record for `courses.bigbeachal.com` pointing to the same VPS IP as `crm.bigbeachal.com`.

**Step 4: Commit**

```bash
git add nginx/ .env.example
git commit -m "feat(courses): add Nginx subdomain routing and env config for course portal"
```

---

### Task 9: Integration Testing & Final Wiring

**Step 1: Verify migrations run clean**

Run: `docker-compose exec web python manage.py migrate --check`

**Step 2: Create test data via Django shell**

```python
# Create a test course with modules and lessons
from apps.courses.models import Course, Module, Lesson
from apps.accounts.models import User, Team

team = Team.objects.first()
admin = User.objects.filter(role='admin').first()

course = Course.objects.create(
    title='Real Estate Foundations',
    slug='real-estate-foundations',
    description='Learn the fundamentals of real estate.',
    instructor=admin,
    team=team,
    unlock_mode='completion_based',
    is_published=True,
    is_free=True,
)

m1 = Module.objects.create(course=course, title='Week 1: Getting Started', order=1)
m2 = Module.objects.create(course=course, title='Week 2: Lead Generation', order=2)

Lesson.objects.create(module=m1, title='Welcome Video', video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ', order=1, duration_minutes=5)
Lesson.objects.create(module=m1, title='Setting Up Your CRM', video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ', order=2, duration_minutes=12)
Lesson.objects.create(module=m2, title='Finding Leads Online', video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ', order=1, duration_minutes=15)
```

**Step 3: Manual test checklist**

- [ ] Visit `/portal/` — catalog shows published courses
- [ ] Sign up as student at `/portal/signup/`
- [ ] Verify student cannot access `/` (CRM dashboard)
- [ ] Enroll in course
- [ ] Open lesson, video plays
- [ ] Lesson auto-marks complete after 30 seconds
- [ ] Complete all Module 1 lessons → Module 2 unlocks
- [ ] Visit `/portal/dashboard/` — see progress
- [ ] CRM admin: visit `/courses/` — see course list
- [ ] CRM admin: view students, stats
- [ ] CRM admin: post announcement

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(courses): complete course platform MVP with portal, admin, drip scheduling"
```

---

## Summary

| Task | Description | Estimated Complexity |
|------|-------------|---------------------|
| 1 | Extend User model (student role) | Small |
| 2 | Create courses app models | Medium |
| 3 | Subdomain middleware + URL routing | Medium |
| 4 | Portal base template + student auth | Medium |
| 5 | Student portal templates | Large |
| 6 | CRM admin views + templates | Large |
| 7 | Celery drip unlock task | Small |
| 8 | Nginx subdomain config | Small |
| 9 | Integration testing | Medium |
