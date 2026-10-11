from __future__ import annotations

import pytest
from agentkit import build_runtime, scheduler
from agentkit.runtime import Runtime, repositories

from nudge.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(owner_id="owner", agent_home=tmp_path)


@pytest.fixture
def runtime(settings: Settings) -> Runtime:
    return build_runtime(settings)


@pytest.fixture
def repos(runtime: Runtime):
    with repositories(runtime) as opened:
        yield opened


@pytest.fixture(autouse=True)
def _scheduler_home(runtime: Runtime):
    """Point the module-global scheduler runtime at this test's temp home."""
    scheduler.configure(runtime.settings)
    yield
    scheduler._runtime = None


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Keep the developer's real .env (token, web UI) out of the test run.

    Env vars take precedence over the ``.env`` file in pydantic-settings, so a
    real ``TELEGRAM_BOT_TOKEN`` can never make a test start a live bot.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    monkeypatch.setenv("OBSERVABILITY", "off")
    monkeypatch.setenv("WEBUI_ENABLED", "false")
    yield
