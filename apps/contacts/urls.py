from django.urls import path

from apps.contacts import views

app_name = 'contacts'

urlpatterns = [
    path('', views.ContactListView.as_view(), name='list'),
    path('create/', views.ContactCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ContactDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ContactUpdateView.as_view(), name='edit'),
    path('<int:pk>/note/', views.add_note, name='add_note'),
    path('<int:pk>/log-activity/', views.log_activity, name='log_activity'),
    path('bulk-action/', views.bulk_action, name='bulk_action'),
]
