from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LoginForm, ProfileForm, RegisterForm


class CRMLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class CRMLogoutView(LogoutView):
    next_page = '/accounts/login/'


def register_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Account created successfully.')
            return redirect('/')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def dashboard_view(request):
    from apps.campaigns.models import Campaign
    from apps.contacts.models import Contact, ContactActivity
    from apps.pipeline.models import Deal, Pipeline, PipelineStage
    from apps.tasks.models import Task

    team = request.user.team
    today = timezone.now().date()

    # Pipeline summary: deals per stage for the default (first) pipeline
    pipeline_summary = []
    default_pipeline = Pipeline.objects.filter(team=team).first()
    if default_pipeline:
        stages = PipelineStage.objects.filter(pipeline=default_pipeline).order_by('order')
        for stage in stages:
            deal_count = Deal.objects.filter(stage=stage, won__isnull=True).count()
            pipeline_summary.append({
                'name': stage.name,
                'color': stage.color,
                'count': deal_count,
            })

    context = {
        'total_contacts': Contact.objects.filter(team=team).count(),
        'active_deals': Deal.objects.filter(pipeline__team=team, won__isnull=True).count(),
        'total_deal_value': Deal.objects.filter(
            pipeline__team=team, won__isnull=True
        ).aggregate(total=Sum('value'))['total'] or 0,
        'tasks_today': Task.objects.filter(
            assigned_to=request.user, status='pending', due_date__date=today
        ),
        'overdue_tasks': Task.objects.filter(
            assigned_to=request.user, status='pending', due_date__lt=timezone.now()
        ).exclude(due_date__date=today).count(),
        'active_campaigns': Campaign.objects.filter(team=team, is_active=True).count(),
        'recent_leads': Contact.objects.filter(team=team).order_by('-created_at')[:5],
        'recent_activity': ContactActivity.objects.filter(
            contact__team=team
        ).select_related('contact').order_by('-created_at')[:10],
        'pipeline_summary': pipeline_summary,
        'default_pipeline': default_pipeline,
    }
    return render(request, 'dashboard.html', context)
