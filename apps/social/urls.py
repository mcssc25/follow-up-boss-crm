from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),

    # Keyword triggers (authenticated)
    path('triggers/', views.TriggerListView.as_view(), name='trigger_list'),
    path('triggers/new/', views.TriggerCreateView.as_view(), name='trigger_create'),
    path('triggers/<int:pk>/edit/', views.TriggerUpdateView.as_view(), name='trigger_update'),
    path('triggers/<int:pk>/delete/', views.TriggerDeleteView.as_view(), name='trigger_delete'),

    # Message log
    path('messages/', views.MessageLogView.as_view(), name='message_log'),

    # Social accounts
    path('accounts/', views.social_accounts, name='accounts'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('accounts/<int:pk>/disconnect/', views.disconnect_account, name='disconnect_account'),
]
