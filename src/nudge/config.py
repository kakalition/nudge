"""Nudge settings — agentkit's AgentSettings plus reminder options."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from agentkit.config import AgentSettings


class Settings(AgentSettings):
    agent_name: str = "nudge"

    # Where a nudge is delivered when no target is given: local | telegram | both
    default_target: str = "local"

    # Nudge's own protocol ports (agentkit's defaults are shared across agents).
    a2a_card_name: str = "Nudge"
    a2a_public_url: str = "http://127.0.0.1:9200"
    a2a_port: int = 9200
    mcp_port: int = 8960

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
