from django.urls import path

from . import views
from . import views_gmail

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
]
