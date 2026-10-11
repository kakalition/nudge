from __future__ import annotations

from pathlib import Path

from nudge.config import Settings


def test_explicit_agent_home(tmp_path):
    settings = Settings(agent_home=tmp_path)
    assert settings.home == tmp_path
    assert settings.db_path == tmp_path / "nudge.db"


def test_blank_agent_home_falls_back_to_workspace(tmp_path):
    """A blank AGENT_HOME= in .env must not resolve to the current directory."""
    settings = Settings(agent_home="", workspace_root=tmp_path)
    assert settings.home == tmp_path / "nudge"
    assert settings.home != Path(".")


def test_blank_workspace_root_falls_back_to_default(tmp_path):
    settings = Settings(workspace_root="", agent_home=None)
    assert settings.home == Path("~/.agentkit/nudge").expanduser()
