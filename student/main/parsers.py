# parsers.py - ИСПРАВЛЕННЫЙ ПАРСЕР
import requests
import logging
from datetime import datetime, time
from django.utils import timezone
from .models import RealSchedule

logger = logging.getLogger(__name__)


class ISUScheduleParser:
    BASE_URL = "https://api.schedule-uust.arpakit.com/api"

    @staticmethod
    def get_group_schedule(group_name):
        """Получить расписание для группы из API"""
        try:
            logger.info(f"Запрос расписания для группы: {group_name}")

            # Пробуем разные варианты эндпоинтов
            endpoints = [
                f"{ISUScheduleParser.BASE_URL}/schedule/group/{group_name}",
                f"{ISUScheduleParser.BASE_URL}/schedule/{group_name}",
                f"{ISUScheduleParser.BASE_URL}/group/{group_name}/schedule"
            ]

            response_data = None
            for endpoint in endpoints:
                try:
                    logger.info(f"Пробуем эндпоинт: {endpoint}")
                    response = requests.get(endpoint, timeout=10)

                    if response.status_code == 200:
                        response_data = response.json()
                        logger.info(f"Успешно получены данные с {endpoint}")
                        break
                    else:
                        logger.warning(f"Эндпоинт {endpoint} вернул статус {response.status_code}")

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Ошибка для эндпоинта {endpoint}: {e}")
                    continue

            if response_data is not None:
                logger.info(f"Успешно получено расписание для {group_name}")
                return response_data, True
            else:
                logger.error(f"Все эндпоинты не сработали для группы {group_name}")
                return "Не удалось получить расписание ни с одного эндпоинта", False

        except Exception as e:
            logger.error(f"Неожиданная ошибка для {group_name}: {e}")
            return f"Ошибка обработки данных: {e}", False

    @staticmethod
    def parse_time(time_str):
        """Парсим время из формата API"""
        try:
            if not time_str or time_str.strip() == '':
                return time(8, 0)

            # Убираем возможные пробелы и парсим время
            time_str = time_str.strip()
            return datetime.strptime(time_str, '%H:%M').time()

        except ValueError:
            logger.warning(f"Неверный формат времени: {time_str}")
            return time(8, 0)

    @staticmethod
    def update_schedule_for_group(group_name):
        """Обновить расписание для конкретной группы"""
        try:
            logger.info(f"Начало обновления расписания для группы: {group_name}")

            # Получаем данные из API
            data, success = ISUScheduleParser.get_group_schedule(group_name)

            if not success:
                logger.error(f"Не удалось получить расписание для {group_name}: {data}")
                return False, data

            # Если данных нет или пустой список
            if not data:
                logger.warning(f"Пустой ответ от API для группы {group_name}")
                return False, "Расписание для этой группы не найдено"

            # Очищаем старое расписание для этой группы
            deleted_count, _ = RealSchedule.objects.filter(group=group_name).delete()
            logger.info(f"Удалено {deleted_count} старых записей для {group_name}")

            created_count = 0

            # Обрабатываем полученные данные
            # Предполагаем, что данные приходят в формате списка дней с уроками
            for day_data in data:
                try:
                    day_name = day_data.get('day', '')
                    lessons = day_data.get('lessons', [])

                    if not lessons:
                        continue

                    for lesson in lessons:
                        # Парсим время (предполагаем формат "HH:MM-HH:MM")
                        time_str = lesson.get('time', '')
                        time_parts = time_str.split('-') if time_str else []

                        time_start = ISUScheduleParser.parse_time(time_parts[0]) if len(time_parts) > 0 else time(8, 0)
                        time_end = ISUScheduleParser.parse_time(time_parts[1]) if len(time_parts) > 1 else time(9, 30)

                        # Получаем остальные данные
                        subject = lesson.get('subject', 'Без названия')
                        lesson_type = lesson.get('type', lesson.get('lesson_type', ''))
                        teacher = lesson.get('teacher', '')
                        room = lesson.get('room', '')
                        week_type = lesson.get('week_type', '')

                        # Создаем запись расписания
                        schedule_item = RealSchedule(
                            group=group_name,
                            day=day_name,
                            time_start=time_start,
                            time_end=time_end,
                            subject=subject,
                            lesson_type=lesson_type,
                            teacher=teacher,
                            room=room,
                            week_type=week_type
                        )
                        schedule_item.save()
                        created_count += 1

                except Exception as e:
                    logger.error(f"Ошибка обработки дня {day_name} для {group_name}: {e}")
                    continue

            logger.info(f"Успешно обновлено расписание для {group_name}: {created_count} занятий")

            if created_count == 0:
                return False, "Не удалось распарсить ни одного занятия из полученных данных"

            return True, f"Расписание обновлено. Добавлено {created_count} занятий"

        except Exception as e:
            logger.error(f"Критическая ошибка обновления расписания для {group_name}: {e}")
            return False, f"Ошибка обновления расписания: {str(e)}"

    @staticmethod
    def get_available_groups():
        """Получить список доступных групп"""
        try:
            endpoints = [
                f"{ISUScheduleParser.BASE_URL}/groups",
                f"{ISUScheduleParser.BASE_URL}/schedule/groups"
            ]

            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        groups = response.json()
                        logger.info(f"Получено {len(groups)} доступных групп с {endpoint}")
                        return groups, True
                except:
                    continue

            return [], False

        except Exception as e:
            logger.error(f"Ошибка получения списка групп: {e}")
            return [], False

    @staticmethod
    def test_api_connection():
        """Тестирование подключения к API"""
        try:
            test_endpoints = [
                "/groups",
                "/schedule/group/ИС-21",  # тестовая группа
                "/schedule/groups"
            ]

            results = {}
            for endpoint in test_endpoints:
                try:
                    response = requests.get(f"{ISUScheduleParser.BASE_URL}{endpoint}", timeout=10)
                    results[endpoint] = {
                        'status_code': response.status_code,
                        'success': response.status_code == 200
                    }
                except Exception as e:
                    results[endpoint] = {
                        'status_code': 'error',
                        'success': False,
                        'error': str(e)
                    }

            return results

        except Exception as e:
            return {'error': str(e)}
