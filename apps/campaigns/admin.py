from django.contrib import admin

from .models import Campaign, CampaignEnrollment, CampaignStep


class CampaignStepInline(admin.TabularInline):
    model = CampaignStep
    extra = 1
    ordering = ['order']


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active', 'team', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CampaignStepInline]


@admin.register(CampaignStep)
class CampaignStepAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'order', 'subject', 'delay_days', 'delay_hours', 'created_at')
    list_filter = ('campaign',)
    search_fields = ('subject', 'body')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CampaignEnrollment)
class CampaignEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('contact', 'campaign', 'current_step', 'is_active', 'next_send_at', 'enrolled_at')
    list_filter = ('is_active', 'campaign', 'enrolled_at')
    search_fields = ('contact__first_name', 'contact__last_name', 'campaign__name')
    readonly_fields = ('enrolled_at',)
