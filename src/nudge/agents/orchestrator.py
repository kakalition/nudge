"""Nudge's orchestrator: routes reminder requests to the reminder specialist.

The delegation is defensive: whatever the specialist does (or fails to do), the
orchestrator gets a string back and produces a reply, so a user is never left
without an answer.
"""

from __future__ import annotations

from agentkit.config import AgentSettings, model_settings, usage_limits
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from nudge.agents.deps import Deps
from nudge.agents.prompts import ORCHESTRATOR
from nudge.agents.reminder import reminder_agent
from nudge.soul import compose_instructions, load_soul

# Bound the specialist so a looping model fails fast (into the graceful reply
# below) instead of stalling a whole chat turn.
_DEFAULT_REQUEST_LIMIT = 6

# Instructions are composed per run from the live SOUL, so editing SOUL.md
# changes the agent's name/voice without a restart.
orchestrator_agent: Agent[Deps, str] = Agent(
    name="nudge",
    deps_type=Deps,
    output_type=str,
    instructions=lambda ctx: compose_instructions(load_soul(ctx.deps.settings), ORCHESTRATOR),
)


def _specialist_limits(settings: AgentSettings) -> UsageLimits:
    return usage_limits(settings) or UsageLimits(request_limit=_DEFAULT_REQUEST_LIMIT)


@orchestrator_agent.tool
async def handle_reminders(ctx: RunContext[Deps], request: str) -> str:
    """Set, list, cancel, pause or resume the owner's reminders.

    Args:
        request: The owner's reminder request, in their own words.
    """
    try:
        result = await reminder_agent.run(
            request,
            deps=ctx.deps,
            usage=ctx.usage,
            model=ctx.deps.model,
            model_settings=model_settings(ctx.deps.settings),
            usage_limits=_specialist_limits(ctx.deps.settings),
        )
        reply = (result.output or "").strip()
        return reply or "Done."
    except Exception:  # never leave the owner without a reply
        return (
            "Sorry — I couldn't finish that reminder just now. Please try again, "
            "or add it directly with `nudge add \"…\" --at \"<when>\"`."
        )


__all__ = ["orchestrator_agent"]
