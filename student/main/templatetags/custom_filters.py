# templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def list_attr(queryset, attr_name):
    """Получить список атрибутов из queryset"""
    return [getattr(obj, attr_name) for obj in queryset if getattr(obj, attr_name) is not None]

@register.filter
def avg(values):
    """Вычислить среднее значение"""
    if not values:
        return None
    return sum(values) / len(values)