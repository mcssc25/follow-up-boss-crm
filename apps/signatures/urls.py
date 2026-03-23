from django.urls import path
from apps.signatures import views

app_name = 'signatures'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='list'),
    path('create/', views.DocumentCreateView.as_view(), name='create'),
]
