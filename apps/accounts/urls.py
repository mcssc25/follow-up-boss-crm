from django.urls import path

from . import views
from . import views_gmail
from . import views_settings

app_name = 'accounts'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('accounts/login/', views.CRMLoginView.as_view(), name='login'),
    path('accounts/logout/', views.CRMLogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),
    path('accounts/gmail/connect/', views_gmail.gmail_connect, name='gmail_connect'),
    path('accounts/gmail/callback/', views_gmail.gmail_callback, name='gmail_callback'),
    path('accounts/gmail/disconnect/', views_gmail.gmail_disconnect, name='gmail_disconnect'),
    # Settings
    path('settings/', views_settings.settings_index, name='settings_index'),
    path('settings/team/', views_settings.team_settings, name='settings_team'),
    path('settings/pipelines/', views_settings.pipeline_settings, name='settings_pipelines'),
    path('settings/gmail/', views_settings.gmail_settings, name='settings_gmail'),
    path('settings/api-keys/', views_settings.api_key_settings, name='settings_api_keys'),
    path('settings/lead-routing/', views_settings.lead_routing_settings, name='settings_lead_routing'),
    path('settings/integration/', views_settings.integration_guide, name='settings_integration'),
]
