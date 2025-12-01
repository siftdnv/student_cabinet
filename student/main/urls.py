from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Публичные страницы
    path('', views.home, name='home'),
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),

    # Защищенные страницы
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/courses/', views.courses, name='courses'),
    path('dashboard/grades/', views.grades, name='grades'),
    path('dashboard/schedule/', views.schedule, name='schedule'),
    path('dashboard/schedule/update/', views.update_schedule, name='update_schedule'),
    path('dashboard/tasks/', views.tasks, name='tasks'),
    path('dashboard/record-book/', views.record_book, name='record_book'),
    path('dashboard/profile/', views.profile_update, name='profile_update'),
    path('dashboard/settings/', views.settings, name='settings'),  # Новая страница настроек
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)