from django.contrib import admin

from apps.pipeline.models import Deal, Pipeline, PipelineStage


class PipelineStageInline(admin.TabularInline):
    model = PipelineStage
    extra = 1


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'created_at')
    list_filter = ('team',)
    inlines = [PipelineStageInline]


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipeline', 'order', 'color')
    list_filter = ('pipeline',)


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('title', 'contact', 'pipeline', 'stage', 'value', 'assigned_to', 'created_at')
    list_filter = ('pipeline', 'stage', 'won')
    search_fields = ('title', 'contact__first_name', 'contact__last_name')
    raw_id_fields = ('contact',)
