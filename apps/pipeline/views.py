import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, ListView, DetailView, UpdateView

from apps.contacts.models import ContactActivity
from apps.pipeline.forms import DealForm
from apps.pipeline.models import Deal, Pipeline, PipelineStage


class PipelineListView(LoginRequiredMixin, ListView):
    model = Pipeline
    template_name = 'pipeline/pipeline_list.html'
    context_object_name = 'pipelines'

    def get_queryset(self):
        return Pipeline.objects.filter(
            team=self.request.user.team
        ).prefetch_related('stages', 'deals')


class PipelineBoardView(LoginRequiredMixin, DetailView):
    model = Pipeline
    template_name = 'pipeline/board.html'
    context_object_name = 'pipeline'

    def get_queryset(self):
        return Pipeline.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pipeline = self.object
        stages = pipeline.stages.prefetch_related(
            'deals', 'deals__contact', 'deals__assigned_to'
        ).all()
        ctx['stages'] = stages
        return ctx


@login_required
def move_deal(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    deal = get_object_or_404(
        Deal,
        pk=pk,
        pipeline__team=request.user.team,
    )

    try:
        data = json.loads(request.body)
        stage_id = data.get('stage_id')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not stage_id:
        return JsonResponse({'error': 'stage_id is required'}, status=400)

    new_stage = get_object_or_404(
        PipelineStage,
        pk=stage_id,
        pipeline=deal.pipeline,
    )

    old_stage_name = deal.stage.name
    deal.stage = new_stage
    deal.save(update_fields=['stage', 'updated_at'])

    # Log stage change activity on the contact
    ContactActivity.objects.create(
        contact=deal.contact,
        activity_type='stage_changed',
        description=f'Deal "{deal}" moved from {old_stage_name} to {new_stage.name}',
        metadata={
            'deal_id': deal.pk,
            'old_stage': old_stage_name,
            'new_stage': new_stage.name,
        },
    )

    return JsonResponse({'success': True})


class DealCreateView(LoginRequiredMixin, CreateView):
    model = Deal
    form_class = DealForm
    template_name = 'pipeline/deal_form.html'

    def get_pipeline(self):
        pipeline_id = self.request.GET.get('pipeline') or self.request.POST.get('pipeline')
        if pipeline_id:
            return get_object_or_404(
                Pipeline, pk=pipeline_id, team=self.request.user.team
            )
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        kwargs['pipeline'] = self.get_pipeline()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Deal created successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.pipeline.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Create Deal'
        ctx['pipeline'] = self.get_pipeline()
        return ctx


class DealUpdateView(LoginRequiredMixin, UpdateView):
    model = Deal
    form_class = DealForm
    template_name = 'pipeline/deal_form.html'

    def get_queryset(self):
        return Deal.objects.filter(pipeline__team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        kwargs['pipeline'] = self.object.pipeline
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Deal updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.pipeline.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Edit Deal'
        ctx['pipeline'] = self.object.pipeline
        return ctx
