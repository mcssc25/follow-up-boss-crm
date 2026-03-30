from django.urls import path
from . import views

app_name = 'videos_public'

urlpatterns = [
    path('<uuid:uuid>/', views.video_landing, name='landing'),
    path('<uuid:uuid>/track/', views.video_track, name='track'),
]
