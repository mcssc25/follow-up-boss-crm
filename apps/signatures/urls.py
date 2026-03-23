from django.urls import path
from apps.signatures import views

app_name = 'signatures'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='list'),
    path('create/', views.DocumentCreateView.as_view(), name='create'),
    path('<int:pk>/prepare/', views.DocumentPrepareView.as_view(), name='prepare'),
    path('<int:pk>/signers/add/', views.add_signer, name='add_signer'),
    path('<int:pk>/signers/<int:signer_pk>/delete/', views.delete_signer, name='delete_signer'),
    path('<int:pk>/fields/save/', views.save_fields, name='save_fields'),
]
