from dataclasses import dataclass


@dataclass
class AssistantDeps:
    """Per-conversation dependencies injected into every tool call."""

    user_id: int
    object_type_id: str  # e.g. "OPP"
    object_pk: int       # raw integer pk (not "OPP123")
    session_key: str     # ties proposals to one WS session
