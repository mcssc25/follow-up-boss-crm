import csv
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import CourseForm, ModuleForm, LessonForm, AnnouncementForm
from .models import Course, Module, Lesson, Enrollment, LessonProgress, Announcement

User = get_user_model()


@login_required
def course_list(request):
    from django.db.models import Count
    courses = Course.objects.filter(team=request.user.team).annotate(
        enrollment_count=Count('enrollments'),
    )
    return render(request, 'courses/course_list.html', {'courses': courses})


@login_required
def courses_dashboard(request):
    team = request.user.team
    courses = Course.objects.filter(team=team)
    total_students = Enrollment.objects.filter(course__team=team).values('student').distinct().count()
    active_students = Enrollment.objects.filter(
        course__team=team,
        student__last_login__gte=timezone.now() - timezone.timedelta(days=7),
    ).values('student').distinct().count()

    course_stats = []
    for course in courses:
        enrollments = course.enrollments.all()
        enrollment_count = enrollments.count()
        if enrollment_count > 0:
            total_progress = sum(e.progress_percent for e in enrollments)
            avg_completion = total_progress / enrollment_count
        else:
            avg_completion = 0
        course_stats.append({
            'course': course,
            'enrollment_count': enrollment_count,
            'avg_completion': round(avg_completion),
        })

    return render(request, 'courses/courses_dashboard.html', {
        'total_students': total_students,
        'active_students': active_students,
        'total_courses': courses.count(),
        'published_courses': courses.filter(is_published=True).count(),
        'course_stats': course_stats,
    })


@login_required
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = Course.objects.create(
                title=form.cleaned_data['title'],
                slug=form.cleaned_data['slug'] or slugify(form.cleaned_data['title']),
                description=form.cleaned_data.get('description', ''),
                thumbnail=form.cleaned_data.get('thumbnail'),
                instructor=request.user,
                team=request.user.team,
                unlock_mode=form.cleaned_data['unlock_mode'],
                drip_interval_days=form.cleaned_data.get('drip_interval_days') or 7,
                is_free=form.cleaned_data.get('is_free', True),
                price=form.cleaned_data.get('price'),
            )
            messages.success(request, f'Course "{course.title}" created. Now add modules and lessons.')
            return redirect('courses:course_edit', pk=course.pk)
    else:
        form = CourseForm()
    return render(request, 'courses/course_form.html', {'form': form, 'is_edit': False})


@login_required
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course.title = form.cleaned_data['title']
            course.slug = form.cleaned_data['slug'] or slugify(form.cleaned_data['title'])
            course.description = form.cleaned_data.get('description', '')
            if form.cleaned_data.get('thumbnail'):
                course.thumbnail = form.cleaned_data['thumbnail']
            course.unlock_mode = form.cleaned_data['unlock_mode']
            course.drip_interval_days = form.cleaned_data.get('drip_interval_days') or 7
            course.is_free = form.cleaned_data.get('is_free', True)
            course.price = form.cleaned_data.get('price')
            course.save()
            messages.success(request, 'Course updated.')
            return redirect('courses:course_edit', pk=course.pk)
    else:
        form = CourseForm(initial={
            'title': course.title, 'slug': course.slug, 'description': course.description,
            'unlock_mode': course.unlock_mode, 'drip_interval_days': course.drip_interval_days,
            'is_free': course.is_free, 'price': course.price,
        })
    modules = course.modules.prefetch_related('lessons')
    return render(request, 'courses/course_edit.html', {
        'form': form, 'course': course, 'modules': modules,
        'module_form': ModuleForm(), 'lesson_form': LessonForm(),
    })


@login_required
@require_POST
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    title = course.title
    course.delete()
    messages.success(request, f'Course "{title}" deleted.')
    return redirect('courses:course_list')


@login_required
@require_POST
def course_toggle_publish(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    course.is_published = not course.is_published
    course.save()
    status = 'published' if course.is_published else 'unpublished'
    messages.success(request, f'Course "{course.title}" is now {status}.')
    return redirect('courses:course_edit', pk=course.pk)


@login_required
@require_POST
def module_add(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, team=request.user.team)
    form = ModuleForm(request.POST)
    if form.is_valid():
        last_order = course.modules.count()
        Module.objects.create(
            course=course, title=form.cleaned_data['title'],
            description=form.cleaned_data.get('description', ''), order=last_order + 1,
        )
        messages.success(request, 'Module added.')
    return redirect('courses:course_edit', pk=course.pk)


@login_required
@require_POST
def module_edit(request, pk):
    module = get_object_or_404(Module, pk=pk, course__team=request.user.team)
    form = ModuleForm(request.POST)
    if form.is_valid():
        module.title = form.cleaned_data['title']
        module.description = form.cleaned_data.get('description', '')
        module.save()
        messages.success(request, 'Module updated.')
    return redirect('courses:course_edit', pk=module.course.pk)


@login_required
@require_POST
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk, course__team=request.user.team)
    course_pk = module.course.pk
    module.delete()
    messages.success(request, 'Module deleted.')
    return redirect('courses:course_edit', pk=course_pk)


@login_required
@require_POST
def module_reorder(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, team=request.user.team)
    try:
        order_data = json.loads(request.body)
        for item in order_data:
            Module.objects.filter(pk=item['id'], course=course).update(order=item['order'])
    except (json.JSONDecodeError, KeyError):
        pass
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def lesson_add(request, module_pk):
    module = get_object_or_404(Module, pk=module_pk, course__team=request.user.team)
    form = LessonForm(request.POST, request.FILES)
    if form.is_valid():
        last_order = module.lessons.count()
        Lesson.objects.create(
            module=module, title=form.cleaned_data['title'],
            description=form.cleaned_data.get('description', ''),
            video_url=form.cleaned_data.get('video_url', ''),
            pdf_file=form.cleaned_data.get('pdf_file'),
            duration_minutes=form.cleaned_data.get('duration_minutes'),
            order=last_order + 1,
        )
        messages.success(request, 'Lesson added.')
    return redirect('courses:course_edit', pk=module.course.pk)


@login_required
@require_POST
def lesson_edit(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course__team=request.user.team)
    form = LessonForm(request.POST, request.FILES)
    if form.is_valid():
        lesson.title = form.cleaned_data['title']
        lesson.description = form.cleaned_data.get('description', '')
        lesson.video_url = form.cleaned_data.get('video_url', '')
        if form.cleaned_data.get('pdf_file'):
            lesson.pdf_file = form.cleaned_data['pdf_file']
        lesson.duration_minutes = form.cleaned_data.get('duration_minutes')
        lesson.save()
        messages.success(request, 'Lesson updated.')
    return redirect('courses:course_edit', pk=lesson.module.course.pk)


@login_required
@require_POST
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course__team=request.user.team)
    course_pk = lesson.module.course.pk
    lesson.delete()
    messages.success(request, 'Lesson deleted.')
    return redirect('courses:course_edit', pk=course_pk)


@login_required
@require_POST
def lesson_reorder(request, module_pk):
    module = get_object_or_404(Module, pk=module_pk, course__team=request.user.team)
    try:
        order_data = json.loads(request.body)
        for item in order_data:
            Lesson.objects.filter(pk=item['id'], module=module).update(order=item['order'])
    except (json.JSONDecodeError, KeyError):
        pass
    return JsonResponse({'status': 'ok'})


@login_required
def course_students(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student').order_by('-enrolled_at')
    return render(request, 'courses/course_students.html', {
        'course': course, 'enrollments': enrollments,
    })


@login_required
def course_students_export(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.slug}-students.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Username', 'Enrolled Date', 'Progress %'])
    for e in enrollments:
        writer.writerow([
            e.student.get_full_name(), e.student.email, e.student.username,
            e.enrolled_at.strftime('%Y-%m-%d'), e.progress_percent,
        ])
    return response


@login_required
@require_POST
def bulk_enroll(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    emails = request.POST.get('emails', '').strip().split('\n')
    enrolled = 0
    not_found = []
    for email in emails:
        email = email.strip()
        if not email:
            continue
        try:
            user = User.objects.get(email__iexact=email, role='student')
            _, created = Enrollment.objects.get_or_create(
                student=user, course=course, defaults={'current_module_unlocked': 1},
            )
            if created:
                enrolled += 1
        except User.DoesNotExist:
            not_found.append(email)
    msg = f'{enrolled} student(s) enrolled.'
    if not_found:
        msg += f' Not found: {", ".join(not_found)}'
    messages.info(request, msg)
    return redirect('courses:course_students', pk=course.pk)


@login_required
def course_stats(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    enrollments = course.enrollments.select_related('student')
    total_enrolled = enrollments.count()
    avg_progress = sum(e.progress_percent for e in enrollments) / total_enrolled if total_enrolled else 0

    modules = course.modules.prefetch_related('lessons')
    module_stats = []
    for module in modules:
        lesson_ids = list(module.lessons.values_list('id', flat=True))
        if lesson_ids and total_enrolled:
            completions = LessonProgress.objects.filter(lesson_id__in=lesson_ids, is_completed=True).count()
            possible = len(lesson_ids) * total_enrolled
            pct = round((completions / possible) * 100) if possible else 0
        else:
            pct = 0
        module_stats.append({'module': module, 'completion_pct': pct})

    lesson_stats = []
    for module in modules:
        for lesson in module.lessons.all():
            views = LessonProgress.objects.filter(lesson=lesson).count()
            completions = LessonProgress.objects.filter(lesson=lesson, is_completed=True).count()
            lesson_stats.append({'lesson': lesson, 'module': module, 'views': views, 'completions': completions})
    lesson_stats.sort(key=lambda x: x['views'], reverse=True)

    return render(request, 'courses/course_stats.html', {
        'course': course, 'total_enrolled': total_enrolled,
        'avg_progress': round(avg_progress), 'module_stats': module_stats, 'lesson_stats': lesson_stats,
    })


@login_required
def course_announcements(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    announcements = course.announcements.all()
    return render(request, 'courses/course_announcements.html', {
        'course': course, 'announcements': announcements, 'form': AnnouncementForm(),
    })


@login_required
@require_POST
def announcement_create(request, pk):
    course = get_object_or_404(Course, pk=pk, team=request.user.team)
    form = AnnouncementForm(request.POST)
    if form.is_valid():
        announcement = Announcement.objects.create(
            course=course, title=form.cleaned_data['title'],
            body=form.cleaned_data['body'], created_by=request.user,
            send_email=form.cleaned_data.get('send_email', False),
        )
        if announcement.send_email:
            from .tasks import send_announcement_email
            send_announcement_email.delay(announcement.pk)
        messages.success(request, 'Announcement posted.')
    return redirect('courses:course_announcements', pk=course.pk)
