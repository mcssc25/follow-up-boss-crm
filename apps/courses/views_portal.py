from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import StudentSignupForm
from .models import Course, Module, Lesson, Enrollment, LessonProgress, Announcement


def catalog(request):
    """Public course catalog — list all published courses."""
    courses = Course.objects.filter(is_published=True)

    # If student is logged in, annotate with enrollment status
    enrollments = {}
    if request.user.is_authenticated:
        for e in Enrollment.objects.filter(student=request.user):
            enrollments[e.course_id] = e

    return render(request, 'portal/catalog.html', {
        'courses': courses,
        'enrollments': enrollments,
    })


def student_signup(request):
    """Student registration page."""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        form = StudentSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Welcome! Your account has been created.')
            return redirect('portal:catalog')
    else:
        form = StudentSignupForm()

    return render(request, 'portal/signup.html', {'form': form})


def student_login(request):
    """Student login page."""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.role == 'student':
            login(request, user)
            next_url = request.GET.get('next', 'portal:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'portal/login.html')


@require_POST
def student_logout(request):
    """Log out student."""
    logout(request)
    return redirect('portal:catalog')


@login_required(login_url='/portal/login/')
def student_dashboard(request):
    """Student's enrolled courses with progress."""
    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course')

    # Get recent announcements for enrolled courses
    course_ids = [e.course_id for e in enrollments]
    announcements = Announcement.objects.filter(
        course_id__in=course_ids
    )[:5]

    # Find last incomplete lesson for "continue" link
    continue_lessons = {}
    for enrollment in enrollments:
        completed_ids = set(
            LessonProgress.objects.filter(
                student=request.user,
                lesson__module__course=enrollment.course,
                is_completed=True,
            ).values_list('lesson_id', flat=True)
        )
        lessons = Lesson.objects.filter(
            module__course=enrollment.course
        ).select_related('module').order_by('module__order', 'order')
        for lesson in lessons:
            if lesson.id not in completed_ids:
                continue_lessons[enrollment.course_id] = lesson
                break

    return render(request, 'portal/dashboard.html', {
        'enrollments': enrollments,
        'announcements': announcements,
        'continue_lessons': continue_lessons,
    })


def course_detail(request, slug):
    """Course overview page with module list."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    modules = course.modules.prefetch_related('lessons')

    enrollment = None
    completed_ids = set()
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(
            student=request.user, course=course
        ).first()
        if enrollment:
            completed_ids = set(
                LessonProgress.objects.filter(
                    student=request.user,
                    lesson__module__course=course,
                    is_completed=True,
                ).values_list('lesson_id', flat=True)
            )

    return render(request, 'portal/course_detail.html', {
        'course': course,
        'modules': modules,
        'enrollment': enrollment,
        'completed_ids': completed_ids,
    })


@login_required(login_url='/portal/login/')
@require_POST
def course_enroll(request, slug):
    """Enroll the current student in a course."""
    course = get_object_or_404(Course, slug=slug, is_published=True)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
        defaults={
            'current_module_unlocked': 1,
            'next_unlock_date': (
                timezone.now() + timezone.timedelta(days=course.drip_interval_days)
                if course.unlock_mode == 'time_drip'
                else None
            ),
        },
    )

    if created:
        messages.success(request, f'You are now enrolled in "{course.title}"!')
    else:
        messages.info(request, 'You are already enrolled in this course.')

    return redirect('portal:course_detail', slug=slug)


@login_required(login_url='/portal/login/')
def lesson_view(request, slug, module_order, lesson_order):
    """View a specific lesson — video player + notes."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    module = get_object_or_404(Module, course=course, order=module_order)
    lesson = get_object_or_404(Lesson, module=module, order=lesson_order)

    # Check if module is unlocked
    if not enrollment.is_module_unlocked(module.order):
        messages.warning(request, 'This module is not yet unlocked.')
        return redirect('portal:course_detail', slug=slug)

    # Create or get progress record
    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    # Get all lessons in this module for sidebar navigation
    module_lessons = module.lessons.all()

    # Get completed lesson IDs for checkmarks
    completed_ids = set(
        LessonProgress.objects.filter(
            student=request.user,
            lesson__module=module,
            is_completed=True,
        ).values_list('lesson_id', flat=True)
    )

    # All modules for navigation
    modules = course.modules.prefetch_related('lessons')

    return render(request, 'portal/lesson.html', {
        'course': course,
        'module': module,
        'lesson': lesson,
        'progress': progress,
        'module_lessons': module_lessons,
        'completed_ids': completed_ids,
        'modules': modules,
        'enrollment': enrollment,
    })


@login_required(login_url='/portal/login/')
@require_POST
def lesson_mark_complete(request, pk):
    """HTMX endpoint: mark a lesson as completed."""
    lesson = get_object_or_404(Lesson, pk=pk)
    course = lesson.module.course
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    progress, _ = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save()

        # For completion-based courses, check if module is fully complete
        if course.unlock_mode == 'completion_based':
            module = lesson.module
            total_lessons = module.lessons.count()
            completed_lessons = LessonProgress.objects.filter(
                student=request.user,
                lesson__module=module,
                is_completed=True,
            ).count()

            if completed_lessons >= total_lessons:
                enrollment.unlock_next_module()

    # Return updated checkmark HTML for HTMX swap
    return JsonResponse({
        'completed': True,
        'progress_percent': enrollment.progress_percent,
    })


@login_required(login_url='/portal/login/')
def student_profile(request):
    """Student profile/settings page."""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        messages.success(request, 'Profile updated.')
        return redirect('portal:profile')

    return render(request, 'portal/profile.html')
