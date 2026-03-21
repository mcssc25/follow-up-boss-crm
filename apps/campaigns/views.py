import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.campaigns.forms import CampaignForm, CampaignStepForm
from apps.campaigns.models import Campaign, CampaignEnrollment, CampaignStep
from apps.contacts.models import Contact, ContactActivity


class CampaignListView(LoginRequiredMixin, ListView):
    model = Campaign
    template_name = 'campaigns/campaign_list.html'
    context_object_name = 'campaigns'

    def get_queryset(self):
        return (
            Campaign.objects.filter(team=self.request.user.team)
            .annotate(
                step_count=Count('steps', distinct=True),
                enrollment_count=Count('enrollments', distinct=True),
            )
            .order_by('-created_at')
        )


class CampaignDetailView(LoginRequiredMixin, DetailView):
    model = Campaign
    template_name = 'campaigns/campaign_detail.html'
    context_object_name = 'campaign'

    def get_queryset(self):
        return Campaign.objects.filter(team=self.request.user.team)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campaign = self.object
        ctx['steps'] = campaign.steps.all()

        enrollments = campaign.enrollments.all()
        ctx['active_count'] = enrollments.filter(
            is_active=True, completed_at__isnull=True
        ).count()
        ctx['paused_count'] = enrollments.filter(
            is_active=False, completed_at__isnull=True
        ).count()
        ctx['completed_count'] = enrollments.filter(
            completed_at__isnull=False
        ).count()
        ctx['enrollments'] = enrollments.select_related('contact')[:50]
        return ctx


class CampaignCreateView(LoginRequiredMixin, CreateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Campaign created successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Create Campaign'
        return ctx


class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'

    def get_queryset(self):
        return Campaign.objects.filter(team=self.request.user.team)

    def form_valid(self, form):
        messages.success(self.request, 'Campaign updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Edit Campaign'
        return ctx


@login_required
def toggle_campaign(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    campaign = get_object_or_404(Campaign, pk=pk, team=request.user.team)
    campaign.is_active = not campaign.is_active
    campaign.save(update_fields=['is_active'])

    status = 'activated' if campaign.is_active else 'deactivated'
    messages.success(request, f'Campaign "{campaign.name}" {status}.')
    return redirect('campaigns:detail', pk=campaign.pk)


@login_required
def duplicate_campaign(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    campaign = get_object_or_404(Campaign, pk=pk, team=request.user.team)
    new_campaign = campaign.duplicate()
    messages.success(request, f'Campaign duplicated as "{new_campaign.name}".')
    return redirect('campaigns:detail', pk=new_campaign.pk)


@login_required
def add_step(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, team=request.user.team)

    if request.method == 'POST':
        form = CampaignStepForm(request.POST, request.FILES)
        if form.is_valid():
            step = form.save(commit=False)
            step.campaign = campaign
            step.save()
            messages.success(request, f'Step {step.order} added.')
            return redirect('campaigns:detail', pk=campaign.pk)
    else:
        next_order = (campaign.steps.count()) + 1
        form = CampaignStepForm(initial={'order': next_order, 'delay_days': 0, 'delay_hours': 0})

    return render(request, 'campaigns/step_form.html', {
        'form': form,
        'campaign': campaign,
        'form_title': f'Add Step to "{campaign.name}"',
    })


@login_required
def edit_step(request, pk):
    step = get_object_or_404(
        CampaignStep.objects.select_related('campaign'),
        pk=pk,
        campaign__team=request.user.team,
    )
    campaign = step.campaign

    if request.method == 'POST':
        form = CampaignStepForm(request.POST, request.FILES, instance=step)
        if form.is_valid():
            form.save()
            messages.success(request, f'Step {step.order} updated.')
            return redirect('campaigns:detail', pk=campaign.pk)
    else:
        form = CampaignStepForm(instance=step)

    return render(request, 'campaigns/step_form.html', {
        'form': form,
        'campaign': campaign,
        'step': step,
        'form_title': f'Edit Step {step.order} of "{campaign.name}"',
    })


@login_required
def delete_step(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    step = get_object_or_404(
        CampaignStep.objects.select_related('campaign'),
        pk=pk,
        campaign__team=request.user.team,
    )
    campaign = step.campaign
    step_order = step.order
    step.delete()
    messages.success(request, f'Step {step_order} deleted.')
    return redirect('campaigns:detail', pk=campaign.pk)


@login_required
def enroll_contact(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    contact_id = request.POST.get('contact_id')
    campaign_id = request.POST.get('campaign_id')

    contact = get_object_or_404(Contact, pk=contact_id, team=request.user.team)
    campaign = get_object_or_404(Campaign, pk=campaign_id, team=request.user.team)

    # Check if already enrolled and active
    existing = CampaignEnrollment.objects.filter(
        contact=contact,
        campaign=campaign,
        is_active=True,
        completed_at__isnull=True,
    ).exists()

    if existing:
        messages.warning(request, f'{contact} is already enrolled in "{campaign.name}".')
    else:
        first_step = campaign.steps.first()
        if not first_step:
            messages.error(request, f'Campaign "{campaign.name}" has no steps.')
        else:
            CampaignEnrollment.objects.create(
                contact=contact,
                campaign=campaign,
                current_step=first_step,
                next_send_at=timezone.now(),
            )
            messages.success(
                request, f'{contact} enrolled in "{campaign.name}".'
            )

    # Redirect back to wherever the user came from
    next_url = request.POST.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect('campaigns:detail', pk=campaign.pk)


@login_required
def unenroll_contact(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    enrollment = get_object_or_404(
        CampaignEnrollment.objects.select_related('campaign', 'contact'),
        pk=pk,
        campaign__team=request.user.team,
    )
    enrollment.is_active = False
    enrollment.save(update_fields=['is_active'])
    messages.success(
        request,
        f'{enrollment.contact} unenrolled from "{enrollment.campaign.name}".',
    )

    next_url = request.POST.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect('campaigns:detail', pk=enrollment.campaign.pk)


# ---------------------------------------------------------------------------
# Public video views (no login required — contacts click links in emails)
# ---------------------------------------------------------------------------

def video_player(request, step_id, contact_id):
    """Public page that plays a campaign video and tracks the view."""
    step = get_object_or_404(CampaignStep, id=step_id)
    contact = get_object_or_404(Contact, id=contact_id)

    # Log video view activity
    ContactActivity.objects.create(
        contact=contact,
        activity_type='video_viewed',
        description=f"Watched video: {step.subject}",
        metadata={'step_id': step.id, 'campaign_id': step.campaign.id},
    )

    return render(request, 'campaigns/video_player.html', {
        'step': step,
        'contact': contact,
    })


@csrf_exempt
@require_POST
def video_track(request, step_id, contact_id):
    """Track video watch duration via JS beacon."""
    step = get_object_or_404(CampaignStep, id=step_id)
    contact = get_object_or_404(Contact, id=contact_id)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    duration = data.get('duration', 0)
    percent = data.get('percent', 0)

    # Update the most recent video_viewed activity for this step/contact
    activity = (
        ContactActivity.objects.filter(
            contact=contact,
            activity_type='video_viewed',
            metadata__step_id=step.id,
        )
        .order_by('-id')
        .first()
    )
    if activity:
        activity.metadata['watch_duration'] = duration
        activity.metadata['watch_percent'] = percent
        activity.save(update_fields=['metadata'])

    return JsonResponse({'ok': True})
