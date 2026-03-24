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

    # CRM admin views
    path('scheduling/', views.EventTypeListView.as_view(), name='event_type_list'),
    path('scheduling/create/', views.event_type_create, name='event_type_create'),
    path('scheduling/<int:pk>/edit/', views.event_type_edit, name='event_type_edit'),
    path('scheduling/<int:pk>/delete/', views.event_type_delete, name='event_type_delete'),

    # Booking management
    path('scheduling/bookings/', views.BookingListView.as_view(), name='booking_list'),
    path('scheduling/bookings/<int:pk>/complete/', views.booking_mark_completed, name='booking_complete'),
    path('scheduling/bookings/<int:pk>/no-show/', views.booking_mark_noshow, name='booking_noshow'),
    path('scheduling/bookings/<int:pk>/cancel/', views.booking_admin_cancel, name='booking_admin_cancel'),
]
