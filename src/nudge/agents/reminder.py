"""Reminder specialist: schedule, list, and manage reminders via tools."""

from __future__ import annotations

from pydantic_ai import Agent, ModelRetry, RunContext

from nudge.agents.deps import Deps
from nudge.agents.prompts import REMINDER
from nudge.agents.schemas import ReminderRecord
from nudge.services import reminders as svc

reminder_agent: Agent[Deps, str] = Agent(
    name="reminder", deps_type=Deps, output_type=str, instructions=REMINDER
)


@reminder_agent.tool
async def add_reminder(
    ctx: RunContext[Deps],
    text: str,
    cron: str | None = None,
    at: str | None = None,
    name: str | None = None,
    target: str | None = None,
) -> ReminderRecord:
    """Schedule a reminder.

    Args:
        text: What to be reminded about, in the owner's words.
        cron: A cron expression (e.g. "0 8 * * 1") for a recurring reminder.
        at: An ISO datetime or a phrase (e.g. "tomorrow 09:00") for a one-off.
        name: Optional reminder name (defaults to a slug of the text).
        target: Delivery target: local, telegram, or both.
    """
    try:
        return svc.add_reminder(
            text=text,
            cron=cron,
            at=at,
            name=name,
            target=target,
            settings=ctx.deps.settings,
        )
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc


@reminder_agent.tool
async def list_reminders(ctx: RunContext[Deps]) -> list[ReminderRecord]:
    """List the owner's reminders."""
    return svc.list_reminders(settings=ctx.deps.settings)


@reminder_agent.tool
async def cancel_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Remove a reminder by name."""
    removed = svc.remove_reminder(name, settings=ctx.deps.settings)
    return f"removed {name}" if removed else f"no reminder named {name}"


@reminder_agent.tool
async def pause_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Disable a reminder (keep its definition)."""
    changed = svc.set_enabled(name, False, settings=ctx.deps.settings)
    return f"paused {name}" if changed else f"no reminder named {name}"


@reminder_agent.tool
async def resume_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Re-enable a paused reminder."""
    changed = svc.set_enabled(name, True, settings=ctx.deps.settings)
    return f"resumed {name}" if changed else f"no reminder named {name}"
