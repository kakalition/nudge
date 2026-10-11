"""Reminder specialist: schedule, list, and manage reminders via tools.

Tools return short, plain confirmations and never raise for a bad request — they
return an explanatory line instead. That keeps a single agent turn from looping
(which would surface as ``UnexpectedModelBehavior`` with no reply to the user).
"""

from __future__ import annotations

from pydantic_ai import Agent, RunContext

from nudge.agents.deps import Deps
from nudge.agents.prompts import REMINDER
from nudge.agents.schemas import ReminderRecord
from nudge.services import reminders as svc

reminder_agent: Agent[Deps, str] = Agent(
    name="reminder", deps_type=Deps, output_type=str, instructions=REMINDER, retries=2
)


def _describe(record: ReminderRecord) -> str:
    state = "on" if record.enabled else "off"
    return (
        f"'{record.name}' [{record.kind}/{state}] {record.schedule} "
        f"-> {record.target}: {record.text}"
    )


@reminder_agent.tool
async def add_reminder(
    ctx: RunContext[Deps],
    text: str,
    cron: str | None = None,
    at: str | None = None,
    name: str | None = None,
    target: str | None = None,
) -> str:
    """Schedule a reminder.

    Args:
        text: What to be reminded about, in the owner's words.
        cron: A cron expression (e.g. "0 8 * * 1") for a recurring reminder.
        at: When for a one-off — an ISO datetime or a phrase, e.g. "tomorrow 09:00",
            "in 5 minutes", "5 mins from now". Pass the owner's wording through
            verbatim; the tool resolves it (no clock needed).
        name: Optional reminder name (defaults to a slug of the text).
        target: Delivery target: local, telegram, or both.
    """
    if not cron and not at:
        return "ERROR: a time is required — pass 'cron' (repeat) or 'at' (one-off, e.g. 'in 2 minutes')."
    try:
        record = svc.add_reminder(
            text=text,
            cron=cron,
            at=at,
            name=name,
            target=target,
            settings=ctx.deps.settings,
        )
    except ValueError as exc:
        return f"ERROR: {exc}"
    return f"Scheduled {_describe(record)}."


@reminder_agent.tool
async def list_reminders(ctx: RunContext[Deps]) -> str:
    """List the owner's reminders."""
    rows = svc.list_reminders(settings=ctx.deps.settings)
    if not rows:
        return "No reminders."
    return "\n".join(f"- {_describe(record)}" for record in rows)


@reminder_agent.tool
async def cancel_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Remove a reminder by name."""
    removed = svc.remove_reminder(name, settings=ctx.deps.settings)
    return f"Removed '{name}'." if removed else f"No reminder named '{name}'."


@reminder_agent.tool
async def pause_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Disable a reminder (keep its definition)."""
    changed = svc.set_enabled(name, False, settings=ctx.deps.settings)
    return f"Paused '{name}'." if changed else f"No reminder named '{name}'."


@reminder_agent.tool
async def resume_reminder(ctx: RunContext[Deps], name: str) -> str:
    """Re-enable a paused reminder."""
    changed = svc.set_enabled(name, True, settings=ctx.deps.settings)
    return f"Resumed '{name}'." if changed else f"No reminder named '{name}'."
