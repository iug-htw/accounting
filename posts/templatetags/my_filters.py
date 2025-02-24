from django import template
import locale

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
