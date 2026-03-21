from django.urls import path

from apps.tasks import views

app_name = 'tasks'

urlpatterns = [
    path('', views.TaskListView.as_view(), name='list'),
    path('create/', views.TaskCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.TaskUpdateView.as_view(), name='edit'),
    path('<int:pk>/complete/', views.task_complete, name='complete'),
    path('<int:pk>/delete/', views.task_delete, name='delete'),
]
