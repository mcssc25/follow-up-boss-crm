"""
URL configuration for CRM project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.pwa.views import service_worker_view

urlpatterns = [
    path('sw.js', service_worker_view, name='service_worker'),
    path('admin/', admin.site.urls),

    # Project apps (our custom views first, so they take priority over allauth)
    path('', include('apps.accounts.urls')),

    # Django allauth (for Google OAuth social login only)
    path('accounts/', include('allauth.urls')),
    path('contacts/', include('apps.contacts.urls')),
    path('pipeline/', include('apps.pipeline.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('reports/', include('apps.reports.urls')),
    path('api/', include('apps.api.urls')),
    path('signatures/', include('apps.signatures.urls')),
    path('', include('apps.scheduling.urls')),
    path('courses/', include('apps.courses.urls_admin')),
    path('portal/', include('apps.courses.urls_portal')),
    path('pwa/', include('apps.pwa.urls')),
    path('videos/', include('apps.videos.urls')),
    path('v/', include('apps.videos.urls_public')),
    path('t/', include('apps.email_tracker.urls')),
    path('social/', include('apps.social.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
