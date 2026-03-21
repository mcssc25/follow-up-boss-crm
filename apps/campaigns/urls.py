from django.urls import path

from apps.campaigns import views

app_name = 'campaigns'

urlpatterns = [
    path('', views.CampaignListView.as_view(), name='list'),
    path('create/', views.CampaignCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CampaignDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CampaignUpdateView.as_view(), name='edit'),
    path('<int:pk>/toggle/', views.toggle_campaign, name='toggle'),
    path('<int:pk>/duplicate/', views.duplicate_campaign, name='duplicate'),
    path('<int:pk>/add-step/', views.add_step, name='add_step'),
    path('step/<int:pk>/edit/', views.edit_step, name='edit_step'),
    path('step/<int:pk>/delete/', views.delete_step, name='delete_step'),
    path('enroll/', views.enroll_contact, name='enroll'),
    path('enrollment/<int:pk>/unenroll/', views.unenroll_contact, name='unenroll'),
]
