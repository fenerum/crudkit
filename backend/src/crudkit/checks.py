import re
from collections import defaultdict

from django.apps import apps
from django.core.checks import Error, Tags, register

from crudkit.models import BaseCrudKitModel

TYPE_ID_PATTERN = re.compile(r"^[A-Z]{3}$")


@register(Tags.models)
def check_type_ids(app_configs, **kwargs):
    models_by_type_id = defaultdict(list)
    errors = []

    for model in apps.get_models():
        if not issubclass(model, BaseCrudKitModel):
            continue
        type_id = getattr(model, "TYPE_ID", None)
        if not isinstance(type_id, str) or not TYPE_ID_PATTERN.fullmatch(type_id):
            errors.append(
                Error(
                    f"{model._meta.label} must define TYPE_ID as three uppercase letters.",
                    obj=model,
                    id="crudkit.E001",
                )
            )
            continue
        models_by_type_id[type_id].append(model)

    for type_id, models in models_by_type_id.items():
        if len(models) < 2:
            continue
        labels = ", ".join(model._meta.label for model in models)
        errors.append(
            Error(
                f"TYPE_ID {type_id!r} is used by multiple models: {labels}.",
                id="crudkit.E002",
            )
        )

    return errors
