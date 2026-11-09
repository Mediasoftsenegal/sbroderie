from django import template
from gestion.utils import format_fcfa as _fmt

register = template.Library()


@register.filter(name="fcfa")
def fcfa(value):
    """Formate un montant : 1250000 -> '1 250 000'."""
    return _fmt(value)


@register.filter(name="get")
def get_item(dictionary, key):
    try:
        return dictionary.get(key)
    except AttributeError:
        return ""


@register.filter(name="initiales")
def initiales(value):
    """Retourne jusqu'à 2 initiales majuscules d'un nom."""
    if not value:
        return "?"
    parts = [p for p in str(value).split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return parts[0][:2].upper() if parts else "?"
