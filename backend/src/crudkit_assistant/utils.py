
from crudkit.utils import get_model_types


def resolve_model(type_id: str):
    """Look up a CrudKit model class by its 3-letter TYPE_ID."""
    return get_model_types().get(type_id)


def get_instance(type_id: str, pk: int):
    """Load a CrudKit instance by TYPE_ID + raw integer pk. Returns None if missing."""
    model = resolve_model(type_id)
    if model is None:
        return None
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        return None


def get_assistant_prompt(instance) -> str:
    """Return the per-model assistant prompt, or empty string if not configured."""
    return getattr(getattr(instance.__class__, "CrudKitSettings", None), "assistant_prompt", "") or ""


def get_assistant_tools(instance) -> list:
    """Return any extra per-model pydantic-ai tool callables."""
    return list(getattr(getattr(instance.__class__, "CrudKitSettings", None), "assistant_tools", []) or [])
