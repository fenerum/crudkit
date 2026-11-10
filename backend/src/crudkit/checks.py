import re
from collections import defaultdict

from django.apps import apps
from django.core.checks import Error, Tags, register

from crudkit.models import BaseCrudKitModel, FeedEntry, attachment_fields, get_feed_entry
from crudkit.utils import get_model_types

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


@register(Tags.models)
def check_feed_entries(app_configs, **kwargs):
    types = get_model_types()
    return [
        Error(f"{model._meta.label}.CrudKitSettings.feed_entry {problem}.", obj=model, id="crudkit.E003")
        for model in types.values()
        if (entry := get_feed_entry(model)) is not None
        for problem in _feed_entry_problems(model, entry, types)
    ]


def _feed_entry_problems(model, entry, types) -> list[str]:
    if not isinstance(entry, FeedEntry):
        return ["must be a crudkit.models.FeedEntry"]
    problems = []
    field_names = {field.name for field in model._meta.fields}
    if not entry.fields:
        problems.append("lists no fields")
    if unknown := [name for name in entry.fields if name not in field_names]:
        problems.append(f"names unknown fields: {', '.join(unknown)}")
    if entry.action and not getattr(model.__dict__.get(entry.action), "_crm_action", False):
        problems.append(f"names {entry.action!r}, which is not an action of the model")
    if unknown := [type_id for type_id in entry.on if type_id not in types]:
        problems.append(f"goes on unknown record types: {', '.join(unknown)}")
    if entry.attachments and attachment_fields(model, entry) is None:
        problems.append(
            f"names the attachments {entry.attachments!r}, which need a foreign key to the model and a file field"
        )
    return problems
