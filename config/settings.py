"""
Django settings for CRM project.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from celery.schedules import crontab
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# ---------------------------------------------------------------------------
# Core Settings
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000').rstrip('/')

# Google OAuth (for Gmail API integration)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# ---------------------------------------------------------------------------
# Application Definition
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_filters',
    'django_htmx',
    'widget_tweaks',
]

PROJECT_APPS = [
    'apps.accounts',
    'apps.contacts',
    'apps.pipeline',
    'apps.campaigns',
    'apps.tasks',
    'apps.reports',
    'apps.api',
    'apps.signatures',
    'apps.scheduling',
    'apps.courses',
    'apps.pwa',
    'apps.videos',
    'apps.email_tracker',
    'apps.social',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + PROJECT_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.courses.middleware.SubdomainMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    'DATABASE_URL', 'postgres://crm_user:crm_pass@localhost:5432/crm_db'
)
_db_url = urlparse(DATABASE_URL)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _db_url.path.lstrip('/'),
        'USER': _db_url.username or '',
        'PASSWORD': _db_url.password or '',
        'HOST': _db_url.hostname or 'localhost',
        'PORT': str(_db_url.port or 5432),
        'ATOMIC_REQUESTS': True,
    }
}

# ---------------------------------------------------------------------------
# Cache (Redis)
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# Password Validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Custom User Model
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static Files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# ---------------------------------------------------------------------------
# Media Files (uploads, videos, etc.)
# ---------------------------------------------------------------------------

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# Default Primary Key Field Type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django Sites Framework
# ---------------------------------------------------------------------------

SITE_ID = 1

# ---------------------------------------------------------------------------
# Django Allauth
# ---------------------------------------------------------------------------

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_EMAIL_REQUIRED = False
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'username'
ACCOUNT_EMAIL_VERIFICATION = 'none'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET', ''),
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
    }
}

# ---------------------------------------------------------------------------
# CORS Headers
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^chrome-extension://.*$',
]

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'default'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {
    'process-due-campaign-emails': {
        'task': 'apps.campaigns.tasks.process_due_emails',
        'schedule': 300.0,  # Every 5 minutes
    },
    'send-task-reminders': {
        'task': 'apps.tasks.tasks.send_due_reminders',
        'schedule': 3600.0,  # Every hour
    },
    'send-overdue-digest': {
        'task': 'apps.tasks.tasks.send_overdue_digest',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'process-course-drip-unlocks': {
        'task': 'apps.courses.tasks.process_drip_unlocks',
        'schedule': crontab(hour=0, minute=30),  # Daily at 12:30 AM
    },
    'send-booking-reminders': {
        'task': 'apps.scheduling.tasks.send_booking_reminders',
        'schedule': 900.0,  # Every 15 minutes
    },
    'send-daily-task-reminders': {
        'task': 'apps.tasks.tasks.send_daily_task_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM CT
    },
}

# ---------------------------------------------------------------------------
# Course Portal
# ---------------------------------------------------------------------------

PORTAL_SUBDOMAIN = os.getenv('PORTAL_SUBDOMAIN', 'courses')
PORTAL_URL = os.getenv('PORTAL_URL', 'http://courses.localhost:8000')

# ---------------------------------------------------------------------------
# Security (production hardening — active when DEBUG is False)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # SSL settings — enable these after setting up HTTPS with Certbot
    SESSION_COOKIE_SECURE = os.getenv('USE_SSL', 'False').lower() in ('true', '1', 'yes')
    CSRF_COOKIE_SECURE = os.getenv('USE_SSL', 'False').lower() in ('true', '1', 'yes')
    SECURE_SSL_REDIRECT = os.getenv('USE_SSL', 'False').lower() in ('true', '1', 'yes')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'

# ---------------------------------------------------------------------------
# Push Notifications (Web Push / VAPID)
# ---------------------------------------------------------------------------

VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.getenv('VAPID_ADMIN_EMAIL', 'admin@bigbeachal.com')

# ---------------------------------------------------------------------------
# Email Tracker
# ---------------------------------------------------------------------------

EMAIL_TRACKER_API_KEY = os.getenv('EMAIL_TRACKER_API_KEY', '')

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
