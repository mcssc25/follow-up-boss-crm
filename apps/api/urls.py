from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('leads/', views.capture_lead, name='capture_lead'),
]
