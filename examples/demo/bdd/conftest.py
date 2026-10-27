import os
import pkgutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from bdd.world import PASSWORD, USERNAME, Api, World, sign_in

DEMO = Path(__file__).resolve().parent.parent
# Distinct from the TypeScript suite's 8765, so both can run side by side.
DEFAULT_PORT = "8766"

# Every module in steps/ is loaded, so a new journey only needs a new file.
pytest_plugins = [f"bdd.steps.{m.name}" for m in pkgutil.iter_modules([str(Path(__file__).parent / "steps")])]


def pytest_bdd_apply_tag(tag, function):
    if ":" in tag:
        # A coverage tag (@page:..., @layout:...), read by test_coverage.py, not a pytest marker.
        return function
    return None


def _wait_until_serving(url: str, server: subprocess.Popen, log: Path, seconds: int = 120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"The demo server exited:\n{log.read_text()}")
        try:
            urllib.request.urlopen(url)
            return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"The demo server did not answer {url}:\n{log.read_text()}")


@pytest.fixture(scope="session")
def base_url(pytestconfig, tmp_path_factory):
    """The demo serving the built SPA: `--base-url`/E2E_BASE_URL if given (CI),
    else booted here on a throwaway, freshly seeded SQLite database."""
    given = pytestconfig.getoption("--base-url") or os.environ.get("E2E_BASE_URL")
    if given:
        yield given.rstrip("/")
        return

    workdir = tmp_path_factory.mktemp("demo")
    # pydantic-ai's offline test model: enables the assistant without an API key.
    env = {**os.environ, "DEMO_DB_PATH": str(workdir / "db.sqlite3"), "DEMO_AI_MODEL": "test"}
    manage = [sys.executable, "manage.py"]
    for command in (["migrate", "--noinput"], ["seed"]):
        subprocess.run(manage + command, cwd=DEMO, env=env, check=True, stdout=subprocess.DEVNULL)

    url = f"http://127.0.0.1:{os.environ.get('E2E_PORT', DEFAULT_PORT)}"
    log = workdir / "server.log"
    with log.open("w") as output:
        server = subprocess.Popen(
            manage + ["runserver", url.removeprefix("http://"), "--noreload"],
            cwd=DEMO,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_serving(f"{url}/login", server, log)
            yield url
        finally:
            server.terminate()
            server.wait(timeout=10)


@pytest.fixture(scope="session")
def signed_in_state(browser, base_url, tmp_path_factory):
    """Sign in once through the login page; every scenario starts from this state."""
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    sign_in(page, USERNAME, PASSWORD)
    page.wait_for_url(f"{base_url}/")
    path = tmp_path_factory.mktemp("auth") / "admin.json"
    context.storage_state(path=path)
    context.close()
    return path


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, signed_in_state):
    return {**browser_context_args, "storage_state": signed_in_state}


@pytest.fixture(scope="session")
def api(playwright, base_url):
    request = playwright.request.new_context(base_url=base_url)
    yield Api(request)
    request.dispose()


@pytest.fixture
def world(page, api):
    return World(page=page, api=api)
