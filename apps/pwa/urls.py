from django.urls import path

from . import views

app_name = 'pwa'

urlpatterns = [
    path('offline/', views.offline_view, name='offline'),
    path('vapid-key/', views.vapid_public_key, name='vapid_key'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/', views.unsubscribe, name='unsubscribe'),
]
