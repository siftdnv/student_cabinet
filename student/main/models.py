# models.py - ОБНОВЛЕННАЯ МОДЕЛЬ
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    group = models.CharField(max_length=20, verbose_name='Группа', blank=True)
    student_id = models.CharField(max_length=20, verbose_name='Студенческий билет', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.group}"

class Course(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название курса')
    code = models.CharField(max_length=20, verbose_name='Код курса')
    teacher = models.CharField(max_length=100, verbose_name='Преподаватель')
    hours = models.IntegerField(verbose_name='Часы')
    description = models.TextField(blank=True, verbose_name='Описание')

    def __str__(self):
        return self.name

class Grade(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    work_type = models.CharField(max_length=50, verbose_name='Тип работы')
    grade = models.IntegerField(verbose_name='Оценка')
    date = models.DateField(verbose_name='Дата')
    comments = models.TextField(blank=True, verbose_name='Комментарии')

    def __str__(self):
        return f"{self.student.username} - {self.course.name} - {self.grade}"

    def get_grade_display(self):
        if self.grade == 5:
            return 'Отлично'
        elif self.grade == 4:
            return 'Хорошо'
        elif self.grade == 3:
            return 'Удовлетворительно'
        else:
            return 'Неудовлетворительно'

class RealSchedule(models.Model):
    """Модель для хранения реального расписания из ИСУ"""
    group = models.CharField(max_length=20, verbose_name='Группа')
    day = models.CharField(max_length=20, verbose_name='День недели')
    time_start = models.TimeField(verbose_name='Время начала')
    time_end = models.TimeField(verbose_name='Время окончания')
    subject = models.CharField(max_length=200, verbose_name='Предмет')
    lesson_type = models.CharField(max_length=50, verbose_name='Тип занятия')
    teacher = models.CharField(max_length=100, verbose_name='Преподаватель', blank=True)
    room = models.CharField(max_length=50, verbose_name='Аудитория', blank=True)
    week_type = models.CharField(max_length=20, verbose_name='Тип недели', blank=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        unique_together = ['group', 'day', 'time_start', 'subject']
        ordering = ['group', 'day', 'time_start']

    def __str__(self):
        return f"{self.group} - {self.day} - {self.subject}"

@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    """Автоматически создаем профиль при создании пользователя"""
    if created:
        StudentProfile.objects.get_or_create(user=instance)


# models.py - ДОБАВЬТЕ ЭТИ МОДЕЛИ
class RecordBook(models.Model):
    """Зачётная книжка студента"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Студент')
    semester = models.IntegerField(verbose_name='Семестр')
    academic_year = models.CharField(max_length=20, verbose_name='Учебный год')

    class Meta:
        unique_together = ['student', 'semester', 'academic_year']
        ordering = ['-academic_year', '-semester']

    def __str__(self):
        return f"{self.student.username} - {self.academic_year} семестр {self.semester}"


class RecordBookEntry(models.Model):
    """Запись в зачётной книжке"""
    record_book = models.ForeignKey(RecordBook, on_delete=models.CASCADE, related_name='entries')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='Дисциплина')
    exam_type = models.CharField(max_length=50, choices=[
        ('экзамен', 'Экзамен'),
        ('зачёт', 'Зачёт'),
        ('дифференцированный зачёт', 'Дифференцированный зачёт'),
        ('курсовая работа', 'Курсовая работа'),
    ], verbose_name='Вид контроля')
    grade = models.IntegerField(verbose_name='Оценка', null=True, blank=True)
    passed = models.BooleanField(verbose_name='Сдано', default=False)
    date = models.DateField(verbose_name='Дата сдачи')
    teacher = models.CharField(max_length=100, verbose_name='Преподаватель')

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.course.name} - {self.exam_type}"

    def get_grade_display(self):
        if self.grade:
            grade_display = {
                5: 'Отлично',
                4: 'Хорошо',
                3: 'Удовлетворительно',
                2: 'Неудовлетворительно'
            }
            return grade_display.get(self.grade, str(self.grade))
        return 'Зачёт' if self.passed else 'Не сдано'