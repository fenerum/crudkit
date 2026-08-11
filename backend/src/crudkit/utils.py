import uuid

from django.apps import apps
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.deconstruct import deconstructible


def get_model_types():
    app_models = apps.get_models()
    return {mdl.TYPE_ID: mdl for mdl in app_models if getattr(mdl, "TYPE_ID", False)}


def get_system_user():
    return User.objects.get_or_create(username="system")[0]


def get_ai_bot_user():
    """The dedicated user account used as the author for AI-bot-sent messages.

    Kept distinct from `get_system_user()` so we can reliably tell bot-authored
    messages apart from visitor messages (which currently fall back to "system").
    """
    return User.objects.get_or_create(
        username="ai_bot",
        defaults={"first_name": "AI", "last_name": "Assistant"},
    )[0]


def resolve_variable_value(request, value):
    """
    Resolves string variables to their actual values.

    Currently supported variables:
    - ${user}: Replaced with the current user's primary key

    Args:
        request: The request object containing the current user
        value: The value to check for variables

    Returns:
        The resolved value if it contains a variable, otherwise the original value
    """
    if value == "${user}":
        return request.user.pk
    return value


@deconstructible
class UploadPathGenerator:
    def __init__(self, name, with_date=True, overwrite_filename=True):
        self.name = name
        self.with_date = with_date
        self.overwrite_filename = overwrite_filename

    def __call__(self, instance, filename):
        segments = [self.name]
        if self.with_date:
            date = timezone.now()
            segments.append(f"{date.year}-{date.month}")
        if self.overwrite_filename:
            extension = filename.split(".")[-1]
            segments.append(f"{uuid.uuid4().hex}.{extension}")
        else:
            segments.append(filename)
        return "/".join(segments)
