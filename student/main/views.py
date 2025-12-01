from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Avg
from .forms import CustomLoginForm, CustomUserCreationForm, ProfileUpdateForm
from .models import Course, Grade, StudentProfile, RealSchedule
from .parsers import ISUScheduleParser
from django.template.defaulttags import register
from django.template.defaulttags import register
import logging

logger = logging.getLogger(__name__)

def home(request):
    """Главная страница"""
    # Если пользователь авторизован, перенаправляем в кабинет
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Иначе показываем главную страницу
    return render(request, 'main/home.html')

def user_login(request):
    """Страница входа"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.first_name}!')
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = CustomLoginForm()

    return render(request, 'main/login.html', {'form': form})


def user_register(request):
    """Страница регистрации с автоматической загрузкой расписания"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Автоматический вход после регистрации
            login(request, user)
            messages.success(request, f'Аккаунт создан! Добро пожаловать, {user.first_name}!')

            # Создаем тестовые данные для нового пользователя
            create_sample_data(user)

            # АВТОМАТИЧЕСКАЯ ЗАГРУЗКА РАСПИСАНИЯ
            try:
                profile = user.studentprofile
                group = profile.group
                if group:
                    logger.info(f"Автоматическая загрузка расписания для новой группы: {group}")
                    success, message = ISUScheduleParser.update_schedule_for_group(group)
                    if success:
                        messages.info(request, f"✅ Расписание для группы {group} успешно загружено")
                        logger.info(f"Расписание для {group} загружено успешно")
                    else:
                        messages.warning(request, f"⚠️ Расписание временно недоступно: {message}")
                        logger.warning(f"Не удалось загрузить расписание для {group}: {message}")
            except Exception as e:
                logger.error(f"Ошибка автоматической загрузки расписания: {e}")
                messages.warning(request, "⚠️ Не удалось загрузить расписание. Вы можете обновить его позже в разделе расписания.")

            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()

    return render(request, 'main/register.html', {'form': form})


def user_logout(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('home')

@login_required
@login_required
def dashboard(request):
    """Главная страница кабинета"""
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        # Создаем профиль если его нет
        profile = StudentProfile.objects.create(user=request.user)

    # Получаем последние оценки
    recent_grades = Grade.objects.filter(student=request.user).order_by('-date')[:5]

    # Статистика
    total_grades = Grade.objects.filter(student=request.user).count()
    avg_grade = Grade.objects.filter(student=request.user).aggregate(Avg('grade'))['grade__avg'] or 0
    excellent_grades = Grade.objects.filter(student=request.user, grade=5).count()

    # Текущая дата
    from datetime import datetime
    current_date = datetime.now().strftime("%d.%m.%Y")

    context = {
        'profile': profile,
        'recent_grades': recent_grades,
        'stats': {
            'total_grades': total_grades,
            'avg_grade': round(avg_grade, 1),
            'excellent_grades': excellent_grades,
        },
        'current_date': current_date,  # Добавляем текущую дату
    }
    return render(request, 'main/dashboard.html', context)


@login_required
def courses(request):
    """Страница курсов"""
    courses_list = Course.objects.all()
    return render(request, 'main/courses.html', {'courses': courses_list})


@login_required
def grades(request):
    """Страница успеваемости"""
    grades_list = Grade.objects.filter(student=request.user).order_by('-date')

    subjects = {}
    for grade in grades_list:
        if grade.course.name not in subjects:
            subjects[grade.course.name] = []
        subjects[grade.course.name].append(grade)

    grade_distribution = {
        '5': Grade.objects.filter(student=request.user, grade=5).count(),
        '4': Grade.objects.filter(student=request.user, grade=4).count(),
        '3': Grade.objects.filter(student=request.user, grade=3).count(),
        '2': Grade.objects.filter(student=request.user, grade=2).count(),
    }

    context = {
        'subjects': subjects,
        'grade_distribution': grade_distribution,
        'total_grades': len(grades_list),
    }
    return render(request, 'main/grades.html', context)


@login_required
def schedule(request):
    """УЛУЧШЕННАЯ страница расписания с реальными данными"""
    try:
        profile = request.user.studentprofile
        group = profile.group

        if not group:
            messages.warning(request, '❌ Укажите вашу учебную группу в настройках профиля')
            return redirect('settings')

        # Получаем статус расписания
        schedule_status = ISUScheduleParser.get_schedule_status(group)
        schedule_data_loaded = schedule_status['exists']

        # Получаем расписание для группы пользователя
        schedule_data = RealSchedule.objects.filter(group=group).order_by('day', 'time_start')

        # Если расписания нет, пытаемся загрузить
        if not schedule_data_loaded:
            logger.info(f"Расписание для {group} не найдено, пытаемся загрузить...")
            success, message = ISUScheduleParser.update_schedule_for_group(group)
            if success:
                messages.success(request, f"✅ {message}")
                schedule_data = RealSchedule.objects.filter(group=group).order_by('day', 'time_start')
                schedule_data_loaded = True
                schedule_status = ISUScheduleParser.get_schedule_status(group)
            else:
                messages.warning(request, f"⚠️ {message}")

        # Группируем по дням недели в правильном порядке
        days_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
        days_schedule = {}

        for day in days_order:
            days_schedule[day] = []

        for lesson in schedule_data:
            if lesson.day in days_schedule:
                # Форматируем время для отображения
                lesson.time_start_str = lesson.time_start.strftime('%H:%M')
                lesson.time_end_str = lesson.time_end.strftime('%H:%M')
                days_schedule[lesson.day].append(lesson)

        # Текущая дата и день недели
        today = datetime.now()
        current_day = today.strftime('%A')
        russian_days = {
            'Monday': 'Понедельник',
            'Tuesday': 'Вторник',
            'Wednesday': 'Среда',
            'Thursday': 'Четверг',
            'Friday': 'Пятница',
            'Saturday': 'Суббота',
            'Sunday': 'Воскресенье'
        }
        current_russian_day = russian_days.get(current_day, '')

        # Статистика расписания
        total_lessons = schedule_status['lesson_count']
        days_with_lessons = sum(1 for day in days_schedule.values() if day)

        context = {
            'schedule': days_schedule,
            'group': group,
            'current_day': current_russian_day,
            'current_week': today.isocalendar()[1],
            'days_order': days_order,
            'schedule_data_loaded': schedule_data_loaded,
            'total_lessons': total_lessons,
            'days_with_lessons': days_with_lessons,
            'last_update': schedule_status['last_update']
        }

    except StudentProfile.DoesNotExist:
        messages.error(request, '❌ Профиль студента не найден')
        return redirect('dashboard')
    except Exception as e:
        logger.error(f"Ошибка загрузки расписания: {e}")
        messages.error(request, f'❌ Ошибка загрузки расписания: {e}')
        context = {
            'schedule': {},
            'group': 'Не указана',
            'current_day': '',
            'current_week': datetime.now().isocalendar()[1],
            'days_order': [],
            'schedule_data_loaded': False,
            'total_lessons': 0,
            'days_with_lessons': 0,
            'last_update': None
        }

    return render(request, 'main/schedule.html', context)


@login_required
def update_schedule(request):
    """УЛУЧШЕННОЕ ручное обновление расписания"""
    try:
        profile = request.user.studentprofile
        group = profile.group

        if not group:
            messages.error(request, '❌ Сначала укажите вашу учебную группу в настройках профиля')
            return redirect('settings')

        logger.info(f"Ручное обновление расписания для группы: {group}")

        # Показываем уведомление о начале обновления
        messages.info(request, f'🔄 Обновляем расписание для группы {group}...')

        success, message = ISUScheduleParser.update_schedule_for_group(group)

        if success:
            messages.success(request, f'✅ {message}')
            logger.info(f"Ручное обновление расписания для {group} успешно")
        else:
            messages.error(request, f'❌ {message}')
            logger.error(f"Ручное обновление расписания для {group} failed: {message}")

    except Exception as e:
        logger.error(f"Ошибка ручного обновления расписания: {e}")
        messages.error(request, f'❌ Ошибка обновления: {e}')

    return redirect('schedule')


@login_required
def tasks(request):
    """Страница заданий"""
    tasks_data = {
        'urgent': [
            {'title': 'Курсовой проект', 'course': 'Веб-программирование', 'deadline': '18.12.2024',
             'status': 'Не начато'},
            {'title': 'Лабораторная работа #5', 'course': 'Базы данных', 'deadline': '19.12.2024',
             'status': 'В процессе'},
        ],
        'active': [
            {'title': 'Практическая работа', 'course': 'Python разработка', 'deadline': '22.12.2024',
             'status': 'Не начато'},
        ]
    }

    return render(request, 'main/tasks.html', {'tasks': tasks_data})


@login_required
def record_book(request):
    """Зачетная книжка"""
    return render(request, 'main/record_book.html')


def create_sample_data(user):
    """Создание тестовых данных для нового пользователя"""
    course1, created = Course.objects.get_or_create(
        name='Веб-программирование',
        defaults={'code': 'ИС-401', 'teacher': 'Иванов А.С.', 'hours': 144}
    )
    course2, created = Course.objects.get_or_create(
        name='Базы данных',
        defaults={'code': 'ИС-402', 'teacher': 'Петрова М.В.', 'hours': 120}
    )
    course3, created = Course.objects.get_or_create(
        name='Python разработка',
        defaults={'code': 'ИС-403', 'teacher': 'Сидоров П.К.', 'hours': 108}
    )

    Grade.objects.get_or_create(
        student=user, course=course1,
        work_type='Лабораторная работа #1', grade=5, date='2024-10-15'
    )
    Grade.objects.get_or_create(
        student=user, course=course1,
        work_type='Лабораторная работа #2', grade=5, date='2024-10-22'
    )
    Grade.objects.get_or_create(
        student=user, course=course2,
        work_type='SQL запросы', grade=5, date='2024-10-10'
    )
    Grade.objects.get_or_create(
        student=user, course=course3,
        work_type='Практическая работа', grade=4, date='2024-10-05'
    )

@login_required
def settings(request):
    """Страница настроек"""
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        profile = StudentProfile.objects.create(user=request.user)

    context = {
        'profile': profile,
    }
    return render(request, 'main/settings.html', context)


@login_required
def schedule(request):
    try:
        profile = request.user.studentprofile
        group = profile.group

        schedule_data = RealSchedule.objects.filter(group=group).order_by('day', 'time_start')

        if not schedule_data.exists():
            success, message = ISUScheduleParser.update_schedule_for_group(group)
            if success:
                messages.success(request, message)
                schedule_data = RealSchedule.objects.filter(group=group).order_by('day', 'time_start')
            else:
                messages.warning(request, message)

        days_order = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
        days_schedule = {}

        for day in days_order:
            days_schedule[day] = []

        for lesson in schedule_data:
            if lesson.day in days_schedule:
                days_schedule[lesson.day].append(lesson)

        # Текущая дата и день недели
        today = datetime.now()
        current_day = today.strftime('%A')
        russian_days = {
            'Monday': 'Понедельник',
            'Tuesday': 'Вторник',
            'Wednesday': 'Среда',
            'Thursday': 'Четверг',
            'Friday': 'Пятница',
            'Saturday': 'Суббота',
            'Sunday': 'Воскресенье'
        }
        current_russian_day = russian_days.get(current_day, '')

        context = {
            'schedule': days_schedule,
            'group': group,
            'current_day': current_russian_day,
            'current_week': '8',
            'days_order': days_order
        }

    except StudentProfile.DoesNotExist:
        messages.error(request, 'Профиль студента не найден')
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, f'Ошибка загрузки расписания: {e}')
        context = {
            'schedule': {},
            'group': 'Не указана',
            'current_day': '',
            'current_week': '8',
            'days_order': []
        }

    return render(request, 'main/schedule.html', context)


@login_required
def update_schedule(request):
    """Ручное обновление расписания"""
    try:
        profile = request.user.studentprofile
        group = profile.group

        success, message = ISUScheduleParser.update_schedule_for_group(group)

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

    except Exception as e:
        messages.error(request, f'Ошибка обновления: {e}')

    return redirect('schedule')


def create_sample_data(user):
    """Создание тестовых данных для нового пользователя"""
    # Создаем курсы на основе реального расписания
    courses_data = [
        {'name': 'Алгебра и геометрия', 'teacher': 'Белова Анна Сергеевна'},
        {'name': 'Основы информационных технологий', 'teacher': 'Сметанина Ольга Николаевна'},
        {'name': 'Программно-аппаратные комплексы', 'teacher': 'Костюкова Анастасия Петровна'},
        {'name': 'Математический анализ', 'teacher': 'Кужаев Арсен Фанилевич'},
        {'name': 'Иностранный язык', 'teacher': ''},
        {'name': 'Физическая культура и спорт', 'teacher': ''},
    ]

    for course_data in courses_data:
        course, created = Course.objects.get_or_create(
            name=course_data['name'],
            defaults={
                'code': f"АВТО-{course_data['name'][:8]}",
                'teacher': course_data['teacher'],
                'hours': 36,
                'description': f'Автоматически созданный курс'
            }
        )

    # Создаем тестовые оценки
    course1 = Course.objects.get(name='Алгебра и геометрия')
    course2 = Course.objects.get(name='Основы информационных технологий')
    course3 = Course.objects.get(name='Программно-аппаратные комплексы')

    Grade.objects.get_or_create(
        student=user, course=course1,
        work_type='Лабораторная работа #1', grade=5, date='2024-10-15'
    )
    Grade.objects.get_or_create(
        student=user, course=course1,
        work_type='Лабораторная работа #2', grade=5, date='2024-10-22'
    )
    Grade.objects.get_or_create(
        student=user, course=course2,
        work_type='SQL запросы', grade=5, date='2024-10-10'
    )
    Grade.objects.get_or_create(
        student=user, course=course3,
        work_type='Практическая работа', grade=4, date='2024-10-05'
    )

    # Обновляем расписание для группы пользователя
    try:
        group = user.studentprofile.group
        ISUScheduleParser.update_schedule_for_group(group)
    except:
        pass  # Игнорируем ошибки при создании тестовых данных

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@login_required
def profile_update(request):
    """Редактирование профиля с загрузкой фото"""
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        profile = StudentProfile.objects.create(user=request.user)

    if request.method == 'POST':
        print("=== DEBUG PROFILE UPDATE ===")
        print("POST data:", request.POST)
        print("FILES:", request.FILES)
        print("Current avatar:", profile.avatar)

        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            profile = form.save()
            print("Profile saved successfully")
            print("New avatar:", profile.avatar)
            print("Avatar URL:", profile.avatar.url if profile.avatar else "No avatar")
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('dashboard')
        else:
            print("Form errors:", form.errors)
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, 'main/profile_update.html', {'form': form, 'profile': profile})


# views.py - ДОБАВЬТЕ ЭТУ ФУНКЦИЮ
@login_required
def debug_schedule_api(request):
    """Отладочная страница для тестирования API"""
    from .parsers import ISUScheduleParser

    context = {}

    # Тестируем подключение к API
    if 'test_api' in request.GET:
        context['api_test'] = ISUScheduleParser.test_api_connection()

    # Тестируем конкретную группу
    if 'test_group' in request.GET:
        group_name = request.GET.get('test_group', 'ИС-21')
        data, success = ISUScheduleParser.get_group_schedule(group_name)
        context['group_test'] = {
            'group': group_name,
            'success': success,
            'data': data if success else data,  # data содержит сообщение об ошибке если success=False
            'raw_data': str(data)[:1000] + '...' if success and data else str(data)
        }

    # Обновляем расписание для теста
    if 'update_group' in request.GET:
        group_name = request.GET.get('update_group', 'ИС-21')
        success, message = ISUScheduleParser.update_schedule_for_group(group_name)
        context['update_result'] = {
            'group': group_name,
            'success': success,
            'message': message
        }

    # Показываем существующие группы в базе
    context['existing_groups'] = RealSchedule.objects.values_list('group', flat=True).distinct()
    context['user_group'] = request.user.studentprofile.group if hasattr(request.user, 'studentprofile') else None

    return render(request, 'main/debug_schedule.html', context)


# views.py - ДОБАВЬТЕ ЭТУ ФУНКЦИЮ
# views.py - ОБНОВЛЕННАЯ ФУНКЦИЯ record_book
@login_required
def record_book(request):
    """Страница зачётной книжки"""
    try:
        # Получаем все семестры студента
        record_books = RecordBook.objects.filter(student=request.user).prefetch_related('entries')

        # Если нет данных, создаем демо-данные
        if not record_books.exists():
            record_books = create_sample_record_book_data(request.user)

        # Вычисляем статистику в Python
        total_subjects = 0
        passed_subjects = 0
        grade_sum = 0
        grade_count = 0
        excellent_count = 0

        # Собираем статистику по всем семестрам
        semester_stats = []
        for record_book in record_books:
            entries = record_book.entries.all()
            semester_total = len(entries)
            semester_passed = sum(1 for e in entries if e.passed)
            semester_grades = [e.grade for e in entries if e.grade is not None]
            semester_avg = sum(semester_grades) / len(semester_grades) if semester_grades else 0

            total_subjects += semester_total
            passed_subjects += semester_passed
            grade_sum += sum(semester_grades)
            grade_count += len(semester_grades)
            excellent_count += sum(1 for e in entries if e.grade == 5)

            semester_stats.append({
                'record_book': record_book,
                'total': semester_total,
                'passed': semester_passed,
                'avg_grade': round(semester_avg, 1),
                'entries': entries
            })

        avg_grade = round(grade_sum / grade_count, 1) if grade_count > 0 else 0
        completion_percentage = int((passed_subjects / total_subjects * 100)) if total_subjects > 0 else 0

        context = {
            'semester_stats': semester_stats,
            'total_subjects': total_subjects,
            'passed_subjects': passed_subjects,
            'avg_grade': avg_grade,
            'excellent_count': excellent_count,
            'completion_percentage': completion_percentage
        }

    except Exception as e:
        logger.error(f"Ошибка загрузки зачётной книжки: {e}")
        messages.error(request, f'Ошибка загрузки зачётной книжки: {e}')
        context = {
            'semester_stats': [],
            'total_subjects': 0,
            'passed_subjects': 0,
            'avg_grade': 0,
            'excellent_count': 0,
            'completion_percentage': 0
        }

    return render(request, 'main/record_book.html', context)