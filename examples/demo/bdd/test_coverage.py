"""The coverage guard: every page of the SPA and every saved-view layout has a journey.

The inventory below is read from the code, so a new route in App.tsx or a
new View layout fails this test until a feature is tagged with it. Tags that
name something which no longer exists fail it too. See README.md, "Coverage tags".
"""

import ast
import re
from importlib.util import find_spec
from pathlib import Path

from pytest_bdd.feature import get_features

FEATURES = Path(__file__).parent / "features"
APP = Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.tsx"
CRUDKIT_MODELS = Path(find_spec("crudkit").origin).parent / "models.py"


def page_name(path: str | None) -> str:
    """`None` (the index route) -> `/`, `*` -> `not-found`, `:segment/VIW/:view` -> `/<segment>/VIW/<view>`"""
    if path is None:
        return "/"
    if path == "*":
        return "not-found"
    return "/" + re.sub(r":(\w+)", r"<\1>", path.lstrip("/"))


def _pages():
    routes = re.findall(r'<Route\s+(?:index\b|path="([^"]*)")', APP.read_text())
    return {f"page:{page_name(path or None)}" for path in routes}


def _layouts():
    """The values of `View.ViewLayoutChoices`, read without setting up Django."""
    tree = ast.parse(CRUDKIT_MODELS.read_text())
    classes = (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    choices = next(node for node in classes if node.name == "ViewLayoutChoices")
    return {
        f"layout:{statement.value.value}"
        for statement in choices.body
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant)
    }


def inventory() -> set[str]:
    return _pages() | _layouts()


def tagged() -> set[str]:
    tags = set()
    for feature in get_features([str(FEATURES)]):
        tags |= feature.tags
        for scenario in feature.scenarios.values():
            tags |= scenario.tags
    return {tag for tag in tags if ":" in tag}


def test_every_page_and_layout_has_a_journey():
    missing = sorted(inventory() - tagged())
    assert not missing, "No feature is tagged with:\n  @" + "\n  @".join(missing)


def test_every_coverage_tag_names_something_that_exists():
    stale = sorted(tagged() - inventory())
    assert not stale, "These tags name nothing in the code (renamed or removed?):\n  @" + "\n  @".join(stale)
