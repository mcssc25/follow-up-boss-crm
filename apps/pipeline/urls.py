from django.urls import path

from apps.pipeline import views

app_name = 'pipeline'

urlpatterns = [
    path('', views.PipelineListView.as_view(), name='list'),
    path('<int:pk>/', views.PipelineBoardView.as_view(), name='board'),
    path('deal/create/', views.DealCreateView.as_view(), name='deal_create'),
    path('deal/<int:pk>/edit/', views.DealUpdateView.as_view(), name='deal_edit'),
    path('deal/<int:pk>/move/', views.move_deal, name='deal_move'),
]
