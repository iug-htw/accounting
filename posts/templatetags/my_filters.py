from django import template
import locale
from decimal import Decimal
from django.utils import translation

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """ Holt einen Wert aus einem Dictionary anhand eines Keys """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def abs_value(value):
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value
    
@register.filter
def zip(a, b):
    return zip(a, b)

@register.filter
def index(sequence, position):
    return sequence[int(position)]

@register.filter
def german_format(value):
    try:
        return "{:,.2f}".format(abs(float(value))).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return value

@register.filter
def localized_format(value):
    try:
        lang = translation.get_language()
        number = abs(float(value))
        if lang == 'de':
            return "{:,.2f}".format(number).replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return "{:,.2f}".format(number)
    except (ValueError, TypeError):
        return value

@register.filter
def mul(value, arg):
    """Multipliziert den Wert mit dem Argument."""
    try:
        return Decimal(value) * Decimal(arg)
    except (ValueError, TypeError):
        return value  # Falls es nicht klappt, gib den Originalwert zurück
    
@register.filter
def get_konto(dictionary, key):
    try:
        return dictionary.get(int(key), str(key))
    except (ValueError, TypeError, AttributeError):
        return str(key)