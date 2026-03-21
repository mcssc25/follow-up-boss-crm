"""
URL configuration for CRM project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Django allauth
    path('accounts/', include('allauth.urls')),

    # Project apps
    path('', include('apps.accounts.urls')),
    path('contacts/', include('apps.contacts.urls')),
    path('pipeline/', include('apps.pipeline.urls')),
    path('campaigns/', include('apps.campaigns.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('reports/', include('apps.reports.urls')),
    path('api/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
