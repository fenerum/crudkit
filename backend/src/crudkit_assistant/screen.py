"""
What the user currently has on screen, as reported by the SPA. The browser
only sends ids; everything is re-read through the user's permissions before
it reaches the model, so a forged screen can't reveal anything.
"""

from dataclasses import dataclass, field

from crudkit.authorization import get_authorized_instance
from crudkit.models import ck_id_regex, parse_ck_id
from crudkit.utils import get_model_types
from crudkit_api import records
from crudkit_assistant.utils import get_assistant_prompt

ROUTES = {"list", "detail", "dashboard", "inbox", "other"}
MAX_IDS = 100
MAX_IDS_IN_PROMPT = 30
MAX_TEXT = 200


@dataclass
class Screen:
    route: str = "other"
    path: str = ""
    type_id: str = ""
    record_id: str = ""
    tab: str = ""
    view_id: str = ""
    q: str = ""
    filters: dict[str, str] = field(default_factory=dict)
    page: int = 1
    visible_ids: list[str] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)


def _text(value) -> str:
    return value[:MAX_TEXT] if isinstance(value, str) else ""


def _ck_id(value) -> str:
    return value if isinstance(value, str) and ck_id_regex.fullmatch(value) else ""


def _ck_ids(values) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values[:MAX_IDS] if _ck_id(value)]


def parse_screen(data) -> Screen:
    """Build a Screen from untrusted client JSON, dropping anything malformed."""
    if not isinstance(data, dict):
        return Screen()
    type_id = _text(data.get("type_id"))
    filters = data.get("filters")
    try:
        page = max(int(data.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    return Screen(
        route=route if (route := data.get("route")) in ROUTES else "other",
        path=_text(data.get("path")),
        type_id=type_id if type_id in get_model_types() else "",
        record_id=_ck_id(data.get("record_id")),
        tab=_text(data.get("tab")),
        view_id=_ck_id(data.get("view_id")),
        q=_text(data.get("q")),
        filters={_text(k): _text(v) for k, v in list(filters.items())[:20]} if isinstance(filters, dict) else {},
        page=page,
        visible_ids=_ck_ids(data.get("visible_ids")),
        selected_ids=_ck_ids(data.get("selected_ids")),
    )


def load_screen_record(user, screen: Screen, action: str = "view"):
    if not screen.record_id:
        return None
    type_id, pk = parse_ck_id(screen.record_id)
    return get_authorized_instance(user, type_id, pk, action)


def screen_model(screen: Screen):
    """The model the screen is about: the open record's, else the list's."""
    type_id = screen.record_id[:3] if screen.record_id else screen.type_id
    return get_model_types().get(type_id)


def _id_list(ids: list[str]) -> str:
    shown = ", ".join(ids[:MAX_IDS_IN_PROMPT])
    return shown + (f" … (+{len(ids) - MAX_IDS_IN_PROMPT} more)" if len(ids) > MAX_IDS_IN_PROMPT else "")


def describe_screen(user, screen: Screen) -> str:
    """The `[Screen]` block prepended to each user turn."""
    lines = []
    model = screen_model(screen)
    record = load_screen_record(user, screen)
    if record is not None:
        tab = f", tab {screen.tab!r}" if screen.tab else ""
        lines.append(f"Open record: {record._meta.verbose_name} {screen.record_id} ({record}){tab}.")
    elif screen.route == "list" and model is not None:
        parts = [f"List of {model._meta.verbose_name_plural} ({model.TYPE_ID})"]
        if screen.view_id:
            try:
                parts.append(f"saved view {records.get_view(user, screen.view_id).name!r} ({screen.view_id})")
            except ValueError:
                pass
        if screen.q:
            parts.append(f"search {screen.q!r}")
        if screen.filters:
            parts.append(f"filters {screen.filters}")
        if screen.page > 1:
            parts.append(f"page {screen.page}")
        lines.append(", ".join(parts) + ".")
    else:
        lines.append(f"Page: {screen.route} ({screen.path or '/'}).")
    if screen.visible_ids:
        lines.append(f"Visible rows ({len(screen.visible_ids)}): {_id_list(screen.visible_ids)}.")
    if screen.selected_ids:
        lines.append(f"Selected rows ({len(screen.selected_ids)}): {_id_list(screen.selected_ids)}.")
    if model is not None and (playbook := get_assistant_prompt(model)):
        lines.append(f"Playbook for {model._meta.verbose_name_plural}:\n{playbook}")
    return "[Screen]\n" + "\n".join(lines)
