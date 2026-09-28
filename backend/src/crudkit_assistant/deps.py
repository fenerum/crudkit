from dataclasses import dataclass, field

from crudkit_assistant.screen import Screen


@dataclass
class AssistantDeps:
    """Per-conversation dependencies injected into every tool call."""

    user_id: int
    session_key: str  # ties proposals to one conversation
    screen: Screen = field(default_factory=Screen)
    # Where proposals come from: the sidebar ("assistant") or a background
    # agent ("agent", with the agent's name as client and its instructions).
    source: str = "assistant"
    client: str = ""
    agent_instructions: str = ""
    # Proposal tools persist nothing; the runner still reports what they would file.
    dry_run: bool = False

    # Kept for per-model `assistant_tools` written against the old
    # one-record-per-socket deps.
    @property
    def object_type_id(self) -> str:
        return self.screen.record_id[:3]

    @property
    def object_pk(self) -> int | None:
        return int(self.screen.record_id[3:]) if self.screen.record_id else None
