from django.urls import path

from . import views, api_views

app_name = 'email_tracker'

urlpatterns = [
    # Public tracking endpoints (no auth)
    path('px/<uuid:tracking_id>.png', views.tracking_pixel, name='pixel'),
    path('click/<uuid:tracking_id>/<str:link_hash>', views.click_redirect, name='click'),

    # API endpoints (API key auth)
    path('api/register/', api_views.register_email, name='api_register'),
    path('api/status/', api_views.get_status, name='api_status'),
]
