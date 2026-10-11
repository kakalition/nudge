"""Nudge settings — agentkit's AgentSettings plus reminder options."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from agentkit.config import DEFAULT_WORKSPACE_ROOT, AgentSettings
from pydantic import field_validator


class Settings(AgentSettings):
    agent_name: str = "nudge"

    # Where a nudge is delivered when no target is given: local | telegram | both.
    # "both" always writes the local outbox and also pushes to Telegram when a
    # token is configured, so chat users actually receive their reminder.
    default_target: str = "both"

    # Nudge's own protocol ports (agentkit's defaults are shared across agents).
    a2a_card_name: str = "Nudge"
    a2a_public_url: str = "http://127.0.0.1:9200"
    a2a_port: int = 9200
    mcp_port: int = 8960

    @field_validator("agent_home", mode="before")
    @classmethod
    def _blank_agent_home_is_unset(cls, value: object) -> object:
        """Treat a blank ``AGENT_HOME=`` as unset.

        agentkit would otherwise turn ``""`` into ``Path(".")`` and write the
        database into the current directory instead of the agent home.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("workspace_root", mode="before")
    @classmethod
    def _blank_workspace_root_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return Path(DEFAULT_WORKSPACE_ROOT).expanduser()
        return value

    @property
    def db_path(self) -> Path:
        return self.home / "nudge.db"

    @property
    def owner_chat_id(self) -> int | None:
        """The owner chat for proactive delivery (first allowlisted chat, if any)."""
        return self.telegram_allowed_chat_ids[0] if self.telegram_allowed_chat_ids else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
