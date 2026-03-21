from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('accounts/login/', views.CRMLoginView.as_view(), name='login'),
    path('accounts/logout/', views.CRMLogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/profile/', views.profile_view, name='profile'),
]
