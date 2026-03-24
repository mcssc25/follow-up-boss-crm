from django.contrib import admin
from .models import EventType, Availability, Booking


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 0


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'duration_minutes', 'owner', 'is_active']
    list_filter = ['is_active', 'owner']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [AvailabilityInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'event_type', 'status', 'start_time', 'phone_number']
    list_filter = ['status', 'event_type']
    readonly_fields = ['cancel_token', 'google_event_id']
