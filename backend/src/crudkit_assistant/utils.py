def _settings(model):
    return getattr(model, "CrudKitSettings", None)


def get_assistant_prompt(model) -> str:
    """The model's (or instance's) `assistant_prompt` playbook, or empty string."""
    return getattr(_settings(model), "assistant_prompt", "") or ""


def get_assistant_tools(model) -> list:
    """Any extra per-model pydantic-ai tool callables."""
    return list(getattr(_settings(model), "assistant_tools", []) or [])
