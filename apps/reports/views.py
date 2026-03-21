from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.campaigns.models import Campaign, CampaignEnrollment
from apps.contacts.models import Contact, ContactActivity
from apps.pipeline.models import Deal, Pipeline, PipelineStage
from apps.tasks.models import Task


class ReportIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/report_index.html'


@login_required
def lead_source_report(request):
    team = request.user.team
    days = int(request.GET.get('days', 30))

    start_date = timezone.now() - timedelta(days=days)
    contacts = Contact.objects.filter(team=team, created_at__gte=start_date)
    total = contacts.count()

    source_data = (
        contacts
        .values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    source_labels = []
    source_counts = []
    source_rows = []
    for item in source_data:
        label = dict(Contact.SOURCE_CHOICES).get(item['source'], item['source'])
        percentage = (item['count'] / total * 100) if total > 0 else 0
        source_labels.append(label)
        source_counts.append(item['count'])
        source_rows.append({
            'source': label,
            'count': item['count'],
            'percentage': round(percentage, 1),
        })

    context = {
        'source_rows': source_rows,
        'source_labels_json': source_labels,
        'source_counts_json': source_counts,
        'total': total,
        'days': days,
    }
    return render(request, 'reports/lead_source.html', context)


@login_required
def conversion_report(request):
    team = request.user.team
    pipeline_id = request.GET.get('pipeline')

    pipelines = Pipeline.objects.filter(team=team)
    if pipeline_id:
        selected_pipeline = pipelines.filter(pk=pipeline_id).first()
    else:
        selected_pipeline = pipelines.first()

    stages = []
    stage_labels = []
    stage_counts = []
    if selected_pipeline:
        pipeline_stages = PipelineStage.objects.filter(
            pipeline=selected_pipeline
        ).order_by('order')

        for stage in pipeline_stages:
            count = Deal.objects.filter(stage=stage).count()
            stages.append({
                'name': stage.name,
                'color': stage.color,
                'count': count,
            })
            stage_labels.append(stage.name)
            stage_counts.append(count)

    # Calculate conversion rates between stages
    for i in range(1, len(stages)):
        prev_count = stages[i - 1]['count']
        if prev_count > 0:
            stages[i]['conversion_rate'] = round(
                stages[i]['count'] / prev_count * 100, 1
            )
        else:
            stages[i]['conversion_rate'] = 0

    context = {
        'pipelines': pipelines,
        'selected_pipeline': selected_pipeline,
        'stages': stages,
        'stage_labels_json': stage_labels,
        'stage_counts_json': stage_counts,
    }
    return render(request, 'reports/conversion.html', context)


@login_required
def agent_activity_report(request):
    team = request.user.team
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    agents = User.objects.filter(team=team)
    agent_data = []

    for agent in agents:
        contacts_assigned = Contact.objects.filter(
            assigned_to=agent, created_at__gte=start_date
        ).count()
        emails_sent = ContactActivity.objects.filter(
            contact__assigned_to=agent,
            activity_type='email_sent',
            created_at__gte=start_date,
        ).count()
        tasks_completed = Task.objects.filter(
            assigned_to=agent,
            status='completed',
            completed_at__gte=start_date,
        ).count()
        deals_closed = Deal.objects.filter(
            assigned_to=agent,
            closed_at__gte=start_date,
            won=True,
        ).count()
        deal_value = Deal.objects.filter(
            assigned_to=agent,
            closed_at__gte=start_date,
            won=True,
        ).aggregate(total=Sum('value'))['total'] or 0

        agent_data.append({
            'name': agent.get_full_name() or agent.username,
            'contacts_assigned': contacts_assigned,
            'emails_sent': emails_sent,
            'tasks_completed': tasks_completed,
            'deals_closed': deals_closed,
            'deal_value': deal_value,
        })

    context = {
        'agent_data': agent_data,
        'days': days,
    }
    return render(request, 'reports/agent_activity.html', context)


@login_required
def campaign_performance_report(request):
    team = request.user.team
    campaigns = Campaign.objects.filter(team=team).order_by('-created_at')

    campaign_data = []
    for campaign in campaigns:
        enrollments = CampaignEnrollment.objects.filter(campaign=campaign)
        total_enrolled = enrollments.count()
        active_count = enrollments.filter(
            is_active=True, completed_at__isnull=True
        ).count()
        paused_count = enrollments.filter(
            is_active=False, completed_at__isnull=True
        ).count()
        completed_count = enrollments.filter(completed_at__isnull=False).count()

        emails_sent = ContactActivity.objects.filter(
            activity_type='email_sent',
            metadata__campaign_id=campaign.pk,
        ).count()
        video_views = ContactActivity.objects.filter(
            activity_type='video_viewed',
            metadata__campaign_id=campaign.pk,
        ).count()

        campaign_data.append({
            'name': campaign.name,
            'is_active': campaign.is_active,
            'total_enrolled': total_enrolled,
            'active': active_count,
            'paused': paused_count,
            'completed': completed_count,
            'emails_sent': emails_sent,
            'video_views': video_views,
        })

    context = {
        'campaign_data': campaign_data,
    }
    return render(request, 'reports/campaign_performance.html', context)
