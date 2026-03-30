from django.urls import path
from . import views

app_name = 'videos'

urlpatterns = [
    path('', views.VideoListView.as_view(), name='list'),
    path('upload/', views.video_upload, name='upload'),
    path('record/', views.video_record, name='record'),
    path('record/save/', views.video_record_save, name='record_save'),
    path('<int:pk>/', views.VideoDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.video_edit, name='edit'),
    path('<int:pk>/delete/', views.video_delete, name='delete'),
    path('<int:pk>/snippet/', views.video_snippet, name='snippet'),
    path('<int:pk>/push-to-youtube/', views.video_push_to_youtube, name='push_to_youtube'),
]
