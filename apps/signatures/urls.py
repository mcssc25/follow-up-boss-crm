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
    path('<int:pk>/delete/', views.delete_document, name='delete'),
    path('<int:pk>/download/', views.download_signed, name='download'),
    path('<int:pk>/resend/', views.resend_all_signers, name='resend_all'),
    path('<int:pk>/signers/<int:signer_pk>/resend/', views.resend_to_signer, name='resend'),
    path('verify/', views.verify_document, name='verify'),
    # Templates
    path('templates/', views.TemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.TemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/prepare/', views.TemplatePrepareView.as_view(), name='template_prepare'),
    path('templates/<int:pk>/roles/save/', views.template_save_roles, name='template_save_roles'),
    path('templates/<int:pk>/fields/save/', views.template_save_fields, name='template_save_fields'),
    path('templates/<int:pk>/use/', views.use_template, name='use_template'),
    path('templates/<int:pk>/delete/', views.delete_template, name='template_delete'),
    # Public signing views (no login required)
    path('sign/<uuid:token>/', views.sign_document, name='sign'),
    path('sign/<uuid:token>/submit/', views.submit_signing, name='submit_signing'),
    path('sign/<uuid:token>/decline/', views.decline_signing, name='decline'),
]
