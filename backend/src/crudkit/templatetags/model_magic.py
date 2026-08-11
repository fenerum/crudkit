import re

from django import template

register = template.Library()


@register.filter
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter
def verbose_name_plural(obj):
    return obj._meta.verbose_name_plural


@register.filter
def fk_field_name(obj):
    """
    Converts the name of the model-class to snake-case and suffixes the name with '_id'.
    Used for prefilling fk-fields for inline links.
    E.g. "FeatureRequest" -> "feature_request_id".
    """
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return f"{pattern.sub('_', obj.__class__.__name__).lower()}_id"
