from django.urls import path
from . import views_portal

app_name = 'portal'

urlpatterns = [
    path('', views_portal.catalog, name='catalog'),
    path('signup/', views_portal.student_signup, name='signup'),
    path('login/', views_portal.student_login, name='login'),
    path('logout/', views_portal.student_logout, name='logout'),
    path('dashboard/', views_portal.student_dashboard, name='dashboard'),
    path('profile/', views_portal.student_profile, name='profile'),
    path('course/<slug:slug>/', views_portal.course_detail, name='course_detail'),
    path('course/<slug:slug>/enroll/', views_portal.course_enroll, name='course_enroll'),
    path('course/<slug:slug>/module/<int:module_order>/lesson/<int:lesson_order>/',
         views_portal.lesson_view, name='lesson_view'),
    path('lesson/<int:pk>/complete/', views_portal.lesson_mark_complete, name='lesson_complete'),
]
