from __future__ import annotations

from typer.testing import CliRunner

from nudge.cli import app
from nudge.config import get_settings


def _prepare(tmp_path, monkeypatch) -> CliRunner:
    monkeypatch.setenv("AGENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("WEBUI_ENABLED", "false")
    monkeypatch.setenv("OBSERVABILITY", "off")
    get_settings.cache_clear()
    return CliRunner()


def test_add_list_inbox_remove(tmp_path, monkeypatch):
    runner = _prepare(tmp_path, monkeypatch)

    added = runner.invoke(app, ["add", "call mom", "--at", "2030-01-01T09:00"])
    assert added.exit_code == 0, added.output
    assert "registered" in added.output

    listed = runner.invoke(app, ["list"])
    assert listed.exit_code == 0
    assert "call-mom" in listed.output

    inbox = runner.invoke(app, ["inbox"])
    assert inbox.exit_code == 0
    assert "outbox empty" in inbox.output

    removed = runner.invoke(app, ["remove", "call-mom"])
    assert removed.exit_code == 0
    assert "removed" in removed.output

    get_settings.cache_clear()


def test_add_requires_exactly_one_timing(tmp_path, monkeypatch):
    runner = _prepare(tmp_path, monkeypatch)
    result = runner.invoke(app, ["add", "oops"])
    assert result.exit_code == 1
    assert "cron" in result.output
    get_settings.cache_clear()


def test_add_disabled_then_enable(tmp_path, monkeypatch):
    runner = _prepare(tmp_path, monkeypatch)

    added = runner.invoke(app, ["add", "stretch", "--cron", "0 12 * * *", "--disabled"])
    assert added.exit_code == 0
    assert "off" in added.output

    enabled = runner.invoke(app, ["enable", "stretch"])
    assert enabled.exit_code == 0
    assert "enabled stretch" in enabled.output

    get_settings.cache_clear()


def test_soul_command(tmp_path, monkeypatch):
    runner = _prepare(tmp_path, monkeypatch)
    result = runner.invoke(app, ["soul"])
    assert result.exit_code == 0
    assert "SOUL.md" in result.output
    assert "reminder companion" in result.output
    get_settings.cache_clear()


def test_up_with_nothing_enabled(tmp_path, monkeypatch):
    runner = _prepare(tmp_path, monkeypatch)
    result = runner.invoke(app, ["up", "--no-a2a", "--no-mcp"])
    assert result.exit_code == 0
    assert "nothing to run" in result.output
    get_settings.cache_clear()


def test_mcp_server_builds(settings, runtime):
    """Regress the NameError when FastMCP resolved the tool return annotations."""
    from nudge.cli import _build_mcp_server

    server = _build_mcp_server(settings, runtime)
    assert server is not None
