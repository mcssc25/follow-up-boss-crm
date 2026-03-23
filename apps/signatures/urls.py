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
    path('<int:pk>/send/', views.send_document, name='send'),
    path('<int:pk>/', views.DocumentDetailView.as_view(), name='detail'),
    path('<int:pk>/download/', views.download_signed, name='download'),
    path('verify/', views.verify_document, name='verify'),
    # Public signing views (no login required)
    path('sign/<uuid:token>/', views.sign_document, name='sign'),
    path('sign/<uuid:token>/submit/', views.submit_signing, name='submit_signing'),
    path('sign/<uuid:token>/decline/', views.decline_signing, name='decline'),
]
