from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.models import User
from apps.tasks.forms import TaskForm
from apps.tasks.models import Task
from apps.tasks.tasks import create_task_notifications


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'tasks/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 25

    def get_queryset(self):
        qs = Task.objects.filter(team=self.request.user.team).select_related(
            'assigned_to', 'contact',
        )

        filter_type = self.request.GET.get('filter', '')
        now = timezone.now()

        if filter_type == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            qs = qs.filter(due_date__gte=start, due_date__lt=end, status='pending')
        elif filter_type == 'overdue':
            qs = qs.filter(due_date__lt=now, status='pending')
        elif filter_type == 'upcoming':
            qs = qs.filter(due_date__gte=now, status='pending')
        elif filter_type == 'completed':
            qs = qs.filter(status='completed')
        else:
            # Default: show pending tasks
            pass

        agent = self.request.GET.get('agent', '').strip()
        if agent:
            qs = qs.filter(assigned_to_id=agent)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_filter'] = self.request.GET.get('filter', '')
        ctx['selected_agent'] = self.request.GET.get('agent', '')
        ctx['agents'] = User.objects.filter(team=self.request.user.team)
        return ctx


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.user.team
        response = super().form_valid(form)
        create_task_notifications.delay(self.object.pk)
        messages.success(self.request, 'Task created successfully.')
        return response

    def get_success_url(self):
        return '/tasks/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Add Task'
        return ctx


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'

    def get_queryset(self):
        return Task.objects.filter(team=self.request.user.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['team'] = self.request.user.team
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Task updated successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/tasks/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = 'Edit Task'
        return ctx


@login_required
def task_complete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    task = get_object_or_404(Task, pk=pk, team=request.user.team)
    task.complete()
    messages.success(request, f'Task "{task.title}" marked as completed.')
    return redirect('tasks:list')


@login_required
def task_delete(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    task = get_object_or_404(Task, pk=pk, team=request.user.team)
    task.delete()
    messages.success(request, 'Task deleted.')
    return redirect('tasks:list')
