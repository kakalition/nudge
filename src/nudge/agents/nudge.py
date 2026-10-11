"""The nudge-voice agent: rewrites a reminder into the SOUL persona."""

from __future__ import annotations

from pydantic_ai import Agent

from nudge.agents.deps import Deps
from nudge.agents.prompts import NUDGE_INSTRUCTIONS
from nudge.config import Settings, get_settings
from nudge.soul import compose_instructions, load_soul

NUDGE_AGENT_NAME = "nudge"


def build_nudge_agent(settings: Settings | None = None) -> Agent[Deps, str]:
    """Build the small agent that rewrites one reminder in Nudge's voice."""
    settings = settings or get_settings()
    return Agent(
        name=NUDGE_AGENT_NAME,
        deps_type=Deps,
        output_type=str,
        instructions=compose_instructions(load_soul(settings), NUDGE_INSTRUCTIONS),
    )


__all__ = ["NUDGE_AGENT_NAME", "build_nudge_agent"]
