# Task Attachments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-file attachment support to CRM tasks with inline HTMX management from the task list.

**Architecture:** New `TaskAttachment` model (FK to Task) with FileField. Task create/edit forms get a multi-file input. Task list rows get a paperclip icon that opens an HTMX panel for viewing, uploading, and deleting attachments.

**Tech Stack:** Django 5.1, HTMX (already installed), Tailwind CSS, FileSystemStorage

---

### Task 1: TaskAttachment Model

**Files:**
- Modify: `apps/tasks/models.py`

**Step 1: Add TaskAttachment model**

Add below the existing `Task` model in `apps/tasks/models.py`:

```python
from django.core.exceptions import ValidationError


def validate_file_size(value):
    limit = 50 * 1024 * 1024  # 50MB
    if value.size > limit:
        raise ValidationError('File size must be under 50 MB.')


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(
        upload_to='task_attachments/',
        validators=[validate_file_size],
    )
    filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.filename

    @property
    def size_display(self):
        size = self.file.size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
```

**Step 2: Create and run migration**

```bash
python manage.py makemigrations tasks
python manage.py migrate
```

**Step 3: Commit**

```bash
git add apps/tasks/models.py apps/tasks/migrations/
git commit -m "feat: add TaskAttachment model"
```

---

### Task 2: Register TaskAttachment in Admin

**Files:**
- Modify: `apps/tasks/admin.py`

**Step 1: Add inline admin**

Replace the contents of `apps/tasks/admin.py`:

```python
from django.contrib import admin

from apps.tasks.models import Task, TaskAttachment


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    readonly_fields = ['filename', 'uploaded_by', 'created_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'assigned_to', 'due_date', 'status', 'priority', 'team']
    list_filter = ['status', 'priority', 'team']
    search_fields = ['title', 'description']
    raw_id_fields = ['assigned_to', 'contact']
    inlines = [TaskAttachmentInline]
```

**Step 2: Commit**

```bash
git add apps/tasks/admin.py
git commit -m "feat: add TaskAttachment admin inline"
```

---

### Task 3: Add File Input to Task Create/Edit Form

**Files:**
- Modify: `templates/tasks/task_form.html`
- Modify: `apps/tasks/views.py`

**Step 1: Add `enctype` and file input to the form template**

In `templates/tasks/task_form.html`, change the `<form>` tag on line 11 to include `enctype`:

```html
<form method="post" enctype="multipart/form-data" class="space-y-6">
```

Add a file input section before the button bar (before line 62's `<div class="flex items-center justify-end`):

```html
            <!-- Attachments -->
            <div>
                <label class="block text-sm font-medium text-gray-700">Attachments</label>
                <input type="file" name="attachments" multiple
                       class="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                       accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx,.csv,.txt">
                <p class="mt-1 text-xs text-gray-500">Max 50 MB per file. PDF, images, Word, Excel, CSV, TXT.</p>
            </div>

            {% if form.instance.pk and form.instance.attachments.exists %}
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Current Attachments</label>
                <ul class="space-y-1">
                    {% for att in form.instance.attachments.all %}
                    <li class="flex items-center justify-between text-sm text-gray-600 bg-gray-50 rounded px-3 py-2">
                        <a href="{{ att.file.url }}" target="_blank" class="text-indigo-600 hover:text-indigo-900 truncate">
                            {{ att.filename }}
                        </a>
                        <span class="text-xs text-gray-400 ml-2">{{ att.size_display }}</span>
                    </li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
```

**Step 2: Handle file uploads in TaskCreateView and TaskUpdateView**

In `apps/tasks/views.py`, add the import at the top:

```python
from apps.tasks.models import Task, TaskAttachment
```

Update `TaskCreateView.form_valid` (line 73-78) to save attachments:

```python
    def form_valid(self, form):
        form.instance.team = self.request.user.team
        response = super().form_valid(form)
        # Save attachments
        for f in self.request.FILES.getlist('attachments'):
            TaskAttachment.objects.create(
                task=self.object,
                file=f,
                filename=f.name,
                uploaded_by=self.request.user,
            )
        create_task_notifications.delay(self.object.pk)
        messages.success(self.request, 'Task created successfully.')
        return response
```

Update `TaskUpdateView.form_valid` (line 102-104) to save attachments:

```python
    def form_valid(self, form):
        response = super().form_valid(form)
        for f in self.request.FILES.getlist('attachments'):
            TaskAttachment.objects.create(
                task=self.object,
                file=f,
                filename=f.name,
                uploaded_by=self.request.user,
            )
        messages.success(self.request, 'Task updated successfully.')
        return response
```

**Step 3: Commit**

```bash
git add templates/tasks/task_form.html apps/tasks/views.py
git commit -m "feat: add file upload to task create/edit forms"
```

---

### Task 4: HTMX Attachment Views (list, upload, delete)

**Files:**
- Modify: `apps/tasks/views.py`
- Modify: `apps/tasks/urls.py`
- Create: `templates/tasks/_attachments.html`

**Step 1: Add three new views to `apps/tasks/views.py`**

Add these function-based views at the bottom of the file:

```python
@login_required
def task_attachments(request, pk):
    """HTMX partial: render attachment list for a task."""
    task = get_object_or_404(Task, pk=pk, team=request.user.team)
    attachments = task.attachments.all()
    return render(request, 'tasks/_attachments.html', {
        'task': task,
        'attachments': attachments,
    })


@login_required
def task_attachment_upload(request, pk):
    """HTMX: upload files to a task."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    task = get_object_or_404(Task, pk=pk, team=request.user.team)
    for f in request.FILES.getlist('attachments'):
        if f.size > 50 * 1024 * 1024:
            continue  # skip oversized files
        TaskAttachment.objects.create(
            task=task,
            file=f,
            filename=f.name,
            uploaded_by=request.user,
        )
    attachments = task.attachments.all()
    return render(request, 'tasks/_attachments.html', {
        'task': task,
        'attachments': attachments,
    })


@login_required
def task_attachment_delete(request, pk, att_pk):
    """HTMX: delete an attachment."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    task = get_object_or_404(Task, pk=pk, team=request.user.team)
    attachment = get_object_or_404(TaskAttachment, pk=att_pk, task=task)
    attachment.file.delete()
    attachment.delete()
    attachments = task.attachments.all()
    return render(request, 'tasks/_attachments.html', {
        'task': task,
        'attachments': attachments,
    })
```

Also add the missing import at the top of the file:

```python
from django.shortcuts import get_object_or_404, redirect, render
```

**Step 2: Add URL routes in `apps/tasks/urls.py`**

Add these three paths to the urlpatterns list:

```python
    path('<int:pk>/attachments/', views.task_attachments, name='attachments'),
    path('<int:pk>/attachments/upload/', views.task_attachment_upload, name='attachment_upload'),
    path('<int:pk>/attachments/<int:att_pk>/delete/', views.task_attachment_delete, name='attachment_delete'),
```

**Step 3: Create the `_attachments.html` partial**

Create `templates/tasks/_attachments.html`:

```html
<div id="attachments-{{ task.pk }}" class="px-6 py-4 bg-gray-50 border-t border-gray-200">
    <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-medium text-gray-700">Attachments</h4>
        <form hx-post="{% url 'tasks:attachment_upload' task.pk %}"
              hx-target="#attachments-{{ task.pk }}"
              hx-swap="outerHTML"
              hx-encoding="multipart/form-data"
              class="flex items-center gap-2">
            {% csrf_token %}
            <input type="file" name="attachments" multiple
                   class="text-xs text-gray-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100">
            <button type="submit"
                    class="px-3 py-1 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700">
                Upload
            </button>
        </form>
    </div>

    {% if attachments %}
    <ul class="space-y-1">
        {% for att in attachments %}
        <li class="flex items-center justify-between text-sm bg-white rounded px-3 py-2 shadow-sm">
            <div class="flex items-center gap-2 min-w-0">
                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
                </svg>
                <a href="{{ att.file.url }}" target="_blank"
                   class="text-indigo-600 hover:text-indigo-900 truncate">
                    {{ att.filename }}
                </a>
                <span class="text-xs text-gray-400 flex-shrink-0">{{ att.size_display }}</span>
            </div>
            <button hx-post="{% url 'tasks:attachment_delete' task.pk att.pk %}"
                    hx-target="#attachments-{{ task.pk }}"
                    hx-swap="outerHTML"
                    hx-confirm="Delete {{ att.filename }}?"
                    class="text-red-500 hover:text-red-700 ml-2 flex-shrink-0">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p class="text-xs text-gray-400">No attachments yet.</p>
    {% endif %}
</div>
```

**Step 4: Commit**

```bash
git add apps/tasks/views.py apps/tasks/urls.py templates/tasks/_attachments.html
git commit -m "feat: add HTMX attachment views (list, upload, delete)"
```

---

### Task 5: Add Paperclip Icon and HTMX Panel to Task List

**Files:**
- Modify: `templates/tasks/task_list.html`
- Modify: `apps/tasks/views.py` (annotate queryset with attachment count)

**Step 1: Annotate queryset with attachment count**

In `apps/tasks/views.py`, add import at the top:

```python
from django.db.models import Count
```

In `TaskListView.get_queryset` (line 28), add `.annotate()`:

```python
        qs = Task.objects.filter(team=self.request.user.team).select_related(
            'assigned_to', 'contact',
        ).annotate(attachment_count=Count('attachments'))
```

**Step 2: Add paperclip icon to task list rows**

In `templates/tasks/task_list.html`, in the Actions `<td>` (line 106), add a paperclip button before the existing actions. Replace the Actions `<td>` contents (lines 106-123) with:

```html
                    <td class="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                        <!-- Attachments toggle -->
                        <button hx-get="{% url 'tasks:attachments' task.pk %}"
                                hx-target="#att-row-{{ task.pk }}"
                                hx-swap="innerHTML"
                                class="text-gray-400 hover:text-gray-600 relative"
                                title="Attachments">
                            <svg class="w-5 h-5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
                            </svg>
                            {% if task.attachment_count %}
                            <span class="absolute -top-1 -right-2 bg-indigo-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                                {{ task.attachment_count }}
                            </span>
                            {% endif %}
                        </button>
                        {% if task.status == 'pending' %}
                        <form method="post" action="{% url 'tasks:complete' task.pk %}" class="inline">
                            {% csrf_token %}
                            <button type="submit"
                                    class="text-green-600 hover:text-green-900 font-medium"
                                    title="Mark Complete">
                                <svg class="w-5 h-5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                            </button>
                        </form>
                        {% endif %}
                        <a href="{% url 'tasks:edit' task.pk %}" class="text-indigo-600 hover:text-indigo-900">Edit</a>
                        <form method="post" action="{% url 'tasks:delete' task.pk %}" class="inline"
                              onsubmit="return confirm('Delete this task?')">
                            {% csrf_token %}
                            <button type="submit" class="text-red-600 hover:text-red-900">Delete</button>
                        </form>
                    </td>
```

After each `</tr>` in the task loop (after line 124), add an expandable attachment row:

```html
                <tr id="att-row-{{ task.pk }}">
                    <!-- HTMX attachment panel loads here -->
                </tr>
```

So the full row block becomes:

```html
                {% for task in tasks %}
                <tr class="{% if task.is_overdue %}bg-red-50{% endif %}">
                    ...existing cells...
                </tr>
                <tr id="att-row-{{ task.pk }}">
                </tr>
                {% endfor %}
```

**Step 3: Commit**

```bash
git add templates/tasks/task_list.html apps/tasks/views.py
git commit -m "feat: add paperclip icon and HTMX attachment panel to task list"
```

---

### Task 6: Manual Smoke Test

**Step 1: Run the dev server**

```bash
python manage.py runserver
```

**Step 2: Test the following flows:**

1. **Create task with attachment:** Go to `/tasks/create/`, fill in the form, attach a file, submit. Verify the task is created and the attachment is saved.
2. **Edit task with attachment:** Edit the task, verify existing attachments are shown, add another file, submit.
3. **Task list paperclip icon:** On the task list, verify the paperclip icon shows with a count badge. Click it to expand the attachment panel.
4. **Upload from task list:** In the expanded panel, upload a file using the inline form. Verify it appears in the list.
5. **Delete attachment:** Click the X on an attachment, confirm deletion, verify it disappears.
6. **Download attachment:** Click an attachment filename, verify it opens/downloads in a new tab.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: task attachments - complete implementation"
```
