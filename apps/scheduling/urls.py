from django.urls import path
from . import views

app_name = 'scheduling'

urlpatterns = [
    # Public booking pages
    path('schedule/<slug:slug>/', views.public_booking, name='public_booking'),
    path('schedule/<slug:slug>/slots/', views.get_available_slots, name='get_slots'),
    path('schedule/<slug:slug>/book/', views.confirm_booking, name='confirm_booking'),
    path('schedule/<slug:slug>/book/<uuid:token>/', views.confirm_reschedule, name='confirm_reschedule'),

    # Cancel / reschedule (token-based, no login)
    path('booking/cancel/<uuid:token>/', views.cancel_booking, name='cancel_booking'),
    path('booking/reschedule/<uuid:token>/', views.reschedule_booking, name='reschedule_booking'),
]
