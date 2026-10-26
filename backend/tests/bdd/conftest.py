import pkgutil
from pathlib import Path

import pytest
from django.core.cache import cache

from tests.bdd.world import World

# Every module in steps/ is loaded, so a new area only needs a new file.
pytest_plugins = [f"tests.bdd.steps.{m.name}" for m in pkgutil.iter_modules([str(Path(__file__).parent / "steps")])]


def pytest_bdd_apply_tag(tag, function):
    if ":" in tag:
        # A coverage tag (@endpoint:..., @mcp-tool:...), read by test_coverage.py, not a pytest marker.
        return function
    if tag == "transactional":
        # Channels consumers and on-commit hooks need real commits.
        return pytest.mark.django_db(transaction=True)(function)
    if tag == "known-bug":
        # Specifies the intended behaviour of an open bug. Strict, so the fix must remove the tag.
        return pytest.mark.xfail(strict=True, reason="known bug: the scenario describes the intended behaviour")(
            function
        )
    return None


@pytest.fixture
def world():
    return World()


@pytest.fixture(autouse=True)
def _fresh_cache():
    # Rate limits, the agent table and other cached state must not leak between scenarios.
    cache.clear()
    yield
    cache.clear()
