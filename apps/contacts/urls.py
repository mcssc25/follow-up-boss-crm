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

    # Smart Lists
    path('smart-lists/', views.SmartListListView.as_view(), name='smart_list_list'),
    path('smart-lists/create/', views.SmartListCreateView.as_view(), name='smart_list_create'),
    path('smart-lists/<int:pk>/', views.SmartListDetailView.as_view(), name='smart_list_detail'),
    path('smart-lists/<int:pk>/edit/', views.SmartListUpdateView.as_view(), name='smart_list_edit'),
    path('smart-lists/<int:pk>/delete/', views.SmartListDeleteView.as_view(), name='smart_list_delete'),
]
