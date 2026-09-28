"""Who is changing data right now, so every ChangeLog entry can say.

Entry points (the REST API, MCP, the assistant, reverts) wrap their writes in
``audit(source, ...)``. Every ChangeLog entry written inside shares one
``change_set`` UUID, and a whole change set can be reverted in one go.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass

SOURCES = ("ui", "api", "mcp", "assistant", "agent", "revert", "system")


@dataclass
class AuditContext:
    source: str
    change_set: uuid.UUID
    client: str = ""
    user: object = None
    revert_of: uuid.UUID | None = None
    # Set once a ChangeLog entry is written under this context.
    logged: bool = False


_current: ContextVar[AuditContext | None] = ContextVar("crudkit_audit", default=None)


def current() -> AuditContext:
    """The active context, or a one-off system context outside any audit()."""
    return _current.get() or AuditContext(source="system", change_set=uuid.uuid4())


class audit:
    """Attribute the ChangeLog entries written inside to ``source``.

    Nested calls join the outer change set and inherit its client and user
    unless given their own. A class rather than a generator so views can enter
    it in one hook and exit it in another.
    """

    def __init__(self, source, client="", change_set=None, user=None, revert_of=None):
        if source not in SOURCES:
            raise ValueError(f"Unknown audit source {source!r}")
        outer = _current.get()
        self.context = AuditContext(
            source=source,
            change_set=change_set or (outer.change_set if outer else uuid.uuid4()),
            client=client or (outer.client if outer else ""),
            user=user or (outer.user if outer else None),
            revert_of=revert_of or (outer.revert_of if outer else None),
        )
        self._outer = outer

    def __enter__(self) -> AuditContext:
        self._token = _current.set(self.context)
        return self.context

    def __exit__(self, *exc):
        _current.reset(self._token)
        if self._outer and self.context.logged:
            self._outer.logged = True
        return False
