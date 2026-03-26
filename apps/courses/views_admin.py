from django.http import HttpResponse


# Placeholder stubs — full implementation in Task 6

def course_list(request): return HttpResponse('TODO')
def courses_dashboard(request): return HttpResponse('TODO')
def course_create(request): return HttpResponse('TODO')
def course_edit(request, pk): return HttpResponse('TODO')
def course_delete(request, pk): return HttpResponse('TODO')
def course_toggle_publish(request, pk): return HttpResponse('TODO')
def module_add(request, course_pk): return HttpResponse('TODO')
def module_edit(request, pk): return HttpResponse('TODO')
def module_delete(request, pk): return HttpResponse('TODO')
def module_reorder(request, course_pk): return HttpResponse('TODO')
def lesson_add(request, module_pk): return HttpResponse('TODO')
def lesson_edit(request, pk): return HttpResponse('TODO')
def lesson_delete(request, pk): return HttpResponse('TODO')
def lesson_reorder(request, module_pk): return HttpResponse('TODO')
def course_students(request, pk): return HttpResponse('TODO')
def course_students_export(request, pk): return HttpResponse('TODO')
def bulk_enroll(request, pk): return HttpResponse('TODO')
def course_stats(request, pk): return HttpResponse('TODO')
def course_announcements(request, pk): return HttpResponse('TODO')
def announcement_create(request, pk): return HttpResponse('TODO')
