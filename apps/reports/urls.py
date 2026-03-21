from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportIndexView.as_view(), name='index'),
    path('lead-sources/', views.lead_source_report, name='lead_sources'),
    path('conversion/', views.conversion_report, name='conversion'),
    path('agent-activity/', views.agent_activity_report, name='agent_activity'),
    path('campaign-performance/', views.campaign_performance_report, name='campaign_performance'),
]
