"""The coverage guard: every public surface of CrudKit has a feature.

The inventory below is computed from the code, so a new endpoint, tool,
action, command, record type, socket, field class or system check fails this
test until a feature is tagged with it. Tags that name something which no
longer exists fail it too. See README.md, "Coverage tags".
"""

import inspect
import re
from pathlib import Path

from django.apps import apps
from django.core.management import get_commands
from django.db import models
from django.urls import URLPattern, URLResolver, get_resolver
from pytest_bdd.feature import get_features

import crudkit.fields
import crudkit.models
from crudkit.utils import get_model_types
from crudkit_api import routing as api_routing
from crudkit_api.views import GenericViewSet
from crudkit_assistant import routing as assistant_routing
from crudkit_assistant.agent import assistant_agent
from crudkit_frontend import urls as frontend_urls
from crudkit_mcp.tools import get_tools

FEATURES = Path(__file__).parent / "features"
SRC = Path(crudkit.__file__).parent.parent
CRUDKIT_APPS = ("crudkit", "crudkit_api", "crudkit_assistant", "crudkit_frontend", "crudkit_mcp")
# Routes that belong to Django or DRF, not to CrudKit.
FOREIGN_ROUTES = {"api-root", "login", "logout"}
STANDARD_ACTIONS = ["list", "create", "retrieve", "update", "partial_update", "destroy"]


def _url_names(patterns, namespace=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.app_name != "admin":
                yield from _url_names(pattern.url_patterns, pattern.namespace or namespace)
        elif isinstance(pattern, URLPattern) and pattern.name and not namespace:
            yield pattern.name


def _endpoints():
    record_routes = {f"records.{name}" for name in STANDARD_ACTIONS}
    record_routes |= {f"records.{action.url_path}" for action in GenericViewSet.get_extra_actions()}
    # Per-type routes ("customer-list") are the generic record routes above.
    basenames = {model.__name__.lower() for model in get_model_types().values()}
    other = {
        name
        for name in _url_names(get_resolver().url_patterns + frontend_urls.urlpatterns)
        if name not in FOREIGN_ROUTES and name.split("-")[0] not in basenames
    }
    return {f"endpoint:{name}" for name in record_routes | other}


def _crudkit_models():
    return [
        model
        for name in CRUDKIT_APPS
        if apps.is_installed(name)
        for model in apps.get_app_config(name.split(".")[-1]).get_models()
    ]


def _actions():
    return {
        f"action:{model.TYPE_ID}.{name}"
        for model in _crudkit_models()
        for name, member in inspect.getmembers(model, callable)
        if getattr(member, "_crm_action", False)
    }


def _fields():
    field_classes = set()
    for module in (crudkit.fields, crudkit.models):
        for name, member in vars(module).items():
            if inspect.isclass(member) and issubclass(member, models.Field) and member.__module__ == module.__name__:
                field_classes.add(f"field:{name}")
    return field_classes


def _websockets():
    """`ws/assistant/(?P<type_id>[A-Z]{3})/(?P<pk>\\d+)/$` -> `websocket:ws/assistant/<type_id>/<pk>/`"""
    routes = api_routing.websocket_urlpatterns + assistant_routing.websocket_urlpatterns
    return {"websocket:" + re.sub(r"\(\?P<(\w+)>[^)]*\)", r"<\1>", str(route.pattern)).rstrip("$") for route in routes}


def _checks():
    ids = set()
    for path in SRC.glob("crudkit*/checks.py"):
        ids |= {f"check:{check_id}" for check_id in re.findall(r'id="([\w.]+)"', path.read_text())}
    return ids


def inventory() -> set[str]:
    return (
        _endpoints()
        | {f"mcp-tool:{name}" for name in get_tools(user=None, scopes=["read", "propose", "write"])}
        | {f"assistant-tool:{name}" for name in assistant_agent._function_toolset.tools}
        | _actions()
        | {f"command:{name}" for name, app in get_commands().items() if app in CRUDKIT_APPS}
        | {f"type:{model.TYPE_ID}" for model in _crudkit_models() if getattr(model, "TYPE_ID", None)}
        | _websockets()
        | _fields()
        | _checks()
    )


def tagged() -> set[str]:
    tags = set()
    for feature in get_features([str(FEATURES)]):
        tags |= feature.tags
        for scenario in feature.scenarios.values():
            tags |= scenario.tags
    return {tag for tag in tags if ":" in tag}


def test_every_public_surface_has_a_feature():
    missing = sorted(inventory() - tagged())
    assert not missing, "No feature is tagged with:\n  @" + "\n  @".join(missing)


def test_every_coverage_tag_names_something_that_exists():
    stale = sorted(tagged() - inventory())
    assert not stale, "These tags name nothing in the code (renamed or removed?):\n  @" + "\n  @".join(stale)
