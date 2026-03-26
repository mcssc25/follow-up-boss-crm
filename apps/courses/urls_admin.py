from django.urls import path
from . import views_admin

app_name = 'courses'

urlpatterns = [
    path('', views_admin.course_list, name='course_list'),
    path('dashboard/', views_admin.courses_dashboard, name='dashboard'),
    path('create/', views_admin.course_create, name='course_create'),
    path('<int:pk>/edit/', views_admin.course_edit, name='course_edit'),
    path('<int:pk>/delete/', views_admin.course_delete, name='course_delete'),
    path('<int:pk>/publish/', views_admin.course_toggle_publish, name='course_toggle_publish'),
    path('<int:course_pk>/modules/add/', views_admin.module_add, name='module_add'),
    path('modules/<int:pk>/edit/', views_admin.module_edit, name='module_edit'),
    path('modules/<int:pk>/delete/', views_admin.module_delete, name='module_delete'),
    path('<int:course_pk>/modules/reorder/', views_admin.module_reorder, name='module_reorder'),
    path('modules/<int:module_pk>/lessons/add/', views_admin.lesson_add, name='lesson_add'),
    path('lessons/<int:pk>/edit/', views_admin.lesson_edit, name='lesson_edit'),
    path('lessons/<int:pk>/delete/', views_admin.lesson_delete, name='lesson_delete'),
    path('modules/<int:module_pk>/lessons/reorder/', views_admin.lesson_reorder, name='lesson_reorder'),
    path('<int:pk>/students/', views_admin.course_students, name='course_students'),
    path('<int:pk>/students/export/', views_admin.course_students_export, name='course_students_export'),
    path('<int:pk>/students/enroll/', views_admin.bulk_enroll, name='bulk_enroll'),
    path('<int:pk>/stats/', views_admin.course_stats, name='course_stats'),
    path('<int:pk>/announcements/', views_admin.course_announcements, name='course_announcements'),
    path('<int:pk>/announcements/create/', views_admin.announcement_create, name='announcement_create'),
]
