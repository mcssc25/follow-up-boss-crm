import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404, redirect, render

from apps.api.models import APIKey
from apps.pipeline.models import Pipeline, PipelineStage

from .models import Team, User


def admin_required(view_func):
    """Decorator that checks user is authenticated and has admin role."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('accounts:settings_index')
        return view_func(request, *args, **kwargs)

    wrapper.__name__ = view_func.__name__
    wrapper.__doc__ = view_func.__doc__
    return wrapper


@login_required
def settings_index(request):
    """Settings hub with links to all settings sections."""
    return render(request, 'settings/index.html')


@admin_required
def team_settings(request):
    """Manage team members: invite, change roles, deactivate."""
    team = request.user.team
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('accounts:settings_index')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'invite':
            email = request.POST.get('email', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            role = request.POST.get('role', 'agent')

            if not email:
                messages.error(request, 'Email is required.')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'A user with that email already exists.')
            else:
                temp_password = secrets.token_urlsafe(12)
                User.objects.create(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    team=team,
                    password=make_password(temp_password),
                )
                messages.success(
                    request,
                    f'User {email} invited with temporary password: {temp_password}',
                )

        elif action == 'change_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            if user_id and new_role in ('admin', 'agent'):
                member = get_object_or_404(User, pk=user_id, team=team)
                member.role = new_role
                member.save(update_fields=['role'])
                messages.success(request, f'Role updated for {member}.')

        elif action == 'deactivate':
            user_id = request.POST.get('user_id')
            member = get_object_or_404(User, pk=user_id, team=team)
            if member == request.user:
                messages.error(request, 'You cannot deactivate yourself.')
            else:
                member.is_active = False
                member.save(update_fields=['is_active'])
                messages.success(request, f'{member} has been deactivated.')

        elif action == 'activate':
            user_id = request.POST.get('user_id')
            member = get_object_or_404(User, pk=user_id, team=team)
            member.is_active = True
            member.save(update_fields=['is_active'])
            messages.success(request, f'{member} has been reactivated.')

        return redirect('accounts:settings_team')

    members = User.objects.filter(team=team).order_by('-is_active', 'first_name')
    return render(request, 'settings/team.html', {'members': members})


@admin_required
def pipeline_settings(request):
    """Manage pipelines and stages."""
    team = request.user.team
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('accounts:settings_index')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_pipeline':
            name = request.POST.get('name', '').strip()
            if name:
                Pipeline.objects.create(name=name, team=team)
                messages.success(request, f'Pipeline "{name}" created.')

        elif action == 'add_stage':
            pipeline_id = request.POST.get('pipeline_id')
            stage_name = request.POST.get('stage_name', '').strip()
            color = request.POST.get('color', '#6366f1')
            pipeline = get_object_or_404(Pipeline, pk=pipeline_id, team=team)
            if stage_name:
                max_order = (
                    pipeline.stages.order_by('-order').values_list(
                        'order', flat=True
                    ).first()
                    or 0
                )
                PipelineStage.objects.create(
                    pipeline=pipeline,
                    name=stage_name,
                    order=max_order + 1,
                    color=color,
                )
                messages.success(request, f'Stage "{stage_name}" added.')

        elif action == 'remove_stage':
            stage_id = request.POST.get('stage_id')
            stage = get_object_or_404(
                PipelineStage, pk=stage_id, pipeline__team=team
            )
            stage_name = stage.name
            stage.delete()
            messages.success(request, f'Stage "{stage_name}" removed.')

        elif action == 'reorder_stages':
            pipeline_id = request.POST.get('pipeline_id')
            stage_ids = request.POST.getlist('stage_order')
            pipeline = get_object_or_404(Pipeline, pk=pipeline_id, team=team)
            for idx, stage_id in enumerate(stage_ids):
                PipelineStage.objects.filter(
                    pk=stage_id, pipeline=pipeline
                ).update(order=idx)
            messages.success(request, 'Stages reordered.')

        return redirect('accounts:settings_pipelines')

    pipelines = Pipeline.objects.filter(team=team).prefetch_related('stages')
    return render(request, 'settings/pipelines.html', {'pipelines': pipelines})


@login_required
def gmail_settings(request):
    """Show Gmail connection status for team members."""
    team = request.user.team
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('accounts:settings_index')

    members = User.objects.filter(team=team, is_active=True).order_by('first_name')
    return render(request, 'settings/gmail.html', {'members': members})


@admin_required
def api_key_settings(request):
    """Manage API keys for the team."""
    team = request.user.team
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('accounts:settings_index')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'generate':
            name = request.POST.get('name', '').strip() or 'Unnamed Key'
            key = APIKey.objects.create(team=team, name=name)
            messages.success(
                request,
                f'API key "{name}" created. Key: {key.key}',
            )

        elif action == 'revoke':
            key_id = request.POST.get('key_id')
            api_key = get_object_or_404(APIKey, pk=key_id, team=team)
            api_key.is_active = False
            api_key.save(update_fields=['is_active'])
            messages.success(request, f'API key "{api_key.name}" revoked.')

        return redirect('accounts:settings_api_keys')

    api_keys = APIKey.objects.filter(team=team).order_by('-is_active', '-created_at')
    return render(request, 'settings/api_keys.html', {'api_keys': api_keys})


@admin_required
def lead_routing_settings(request):
    """Configure lead routing method for the team."""
    team = request.user.team
    if not team:
        messages.error(request, 'You are not part of a team.')
        return redirect('accounts:settings_index')

    if request.method == 'POST':
        method = request.POST.get('method', 'round_robin')
        config = {'method': method}
        if method == 'manual':
            agent_id = request.POST.get('agent_id')
            if agent_id:
                config['agent_id'] = int(agent_id)
        team.lead_routing_config = config
        team.save(update_fields=['lead_routing_config'])
        messages.success(request, 'Lead routing configuration updated.')
        return redirect('accounts:settings_lead_routing')

    agents = User.objects.filter(team=team, is_active=True).order_by(
        'first_name'
    )
    return render(
        request,
        'settings/lead_routing.html',
        {
            'config': team.lead_routing_config,
            'agents': agents,
        },
    )


@login_required
def integration_guide(request):
    """Show integration guide with API docs and code snippets."""
    team = request.user.team
    api_key = None
    if team:
        api_key = APIKey.objects.filter(team=team, is_active=True).first()

    return render(
        request,
        'settings/integration_guide.html',
        {'api_key': api_key},
    )
