"""Nudge's orchestrator: routes reminder requests to the reminder specialist."""

from __future__ import annotations

from agentkit.orchestrator import Orchestrator

from nudge.agents.deps import Deps
from nudge.agents.prompts import ORCHESTRATOR
from nudge.agents.reminder import reminder_agent
from nudge.soul import compose_instructions, load_soul

_orchestrator = Orchestrator(
    name="nudge",
    instructions=compose_instructions(load_soul(), ORCHESTRATOR),
    deps_type=Deps,
)
_orchestrator.add_specialist(
    reminder_agent,
    tool_name="handle_reminders",
    description="Set, list, cancel, pause or resume the owner's reminders.",
)

orchestrator_agent = _orchestrator.agent


__all__ = ["orchestrator_agent"]
