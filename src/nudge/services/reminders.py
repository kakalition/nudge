"""Reminder operations: a thin wrapper over :mod:`agentkit.scheduler`.

Reminders are ordinary ``scheduled_jobs`` rows with ``task="nudge"`` and
``args={"text": ..., "target": ...}`` — no domain tables — so the stock web UI
Schedules page and the durable tick both work unchanged.
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Any

from agentkit import scheduler
from dateutil import parser as date_parser

from nudge.agents.schemas import ReminderRecord
from nudge.config import Settings, get_settings

NUDGE_TASK = "nudge"

_RELATIVE_DAYS = {"today": 0, "tonight": 0, "tomorrow": 1, "tmr": 1, "yesterday": -1}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _configure(settings: Settings) -> None:
    scheduler.configure(settings)


def slugify(text: str, *, limit: int = 40) -> str:
    slug = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return slug[:limit].strip("-") or "reminder"


def derive_name(text: str, existing: set[str]) -> str:
    """A unique, readable name for a reminder (slug + numeric suffix if taken)."""
    base = slugify(text)
    if base not in existing:
        return base
    suffix = 2
    while f"{base}-{suffix}" in existing:
        suffix += 1
    return f"{base}-{suffix}"


def parse_when(value: str, *, now: datetime | None = None) -> datetime:
    """Resolve an ISO datetime first, then light natural language ("tomorrow 09:00")."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("a datetime is required")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    now = now or datetime.now()
    tokens = raw.split()
    if tokens and tokens[0].lower() in _RELATIVE_DAYS:
        target = (now + timedelta(days=_RELATIVE_DAYS[tokens[0].lower()])).date()
        remainder = " ".join(tokens[1:]).strip(" ,")
        if remainder:
            parsed = date_parser.parse(remainder, default=now)
            return datetime.combine(target, parsed.time()).replace(second=0, microsecond=0)
        return datetime.combine(target, time(9, 0))
    return date_parser.parse(raw, default=now).replace(second=0, microsecond=0)


def _record(job: dict[str, Any], settings: Settings) -> ReminderRecord:
    args = job.get("args") or {}
    return ReminderRecord(
        name=str(job.get("name", "")),
        text=str(args.get("text", "")),
        kind=str(job.get("kind", "cron")),
        schedule=str(job.get("schedule", "")),
        target=str(args.get("target") or settings.default_target),
        enabled=bool(job.get("enabled", True)),
        last_run=job.get("last_run"),
        run_count=int(job.get("run_count", 0) or 0),
    )


def add_reminder(
    *,
    text: str,
    cron: str | None = None,
    at: str | datetime | None = None,
    name: str | None = None,
    target: str | None = None,
    enabled: bool = True,
    settings: Settings | None = None,
) -> ReminderRecord:
    """Add or update a reminder (exactly one of ``cron`` / ``at``)."""
    settings = settings or get_settings()
    if bool(cron) == bool(at):
        raise ValueError("provide exactly one of cron= or at=")
    substance = (text or "").strip()
    if not substance:
        raise ValueError("reminder text is required")

    _configure(settings)
    existing = {job["name"] for job in scheduler.list_jobs()}
    job_name = (name or "").strip() or derive_name(substance, existing)
    job_target = (target or settings.default_target).strip() or "local"
    args = {"text": substance, "target": job_target}

    if cron:
        scheduler.schedule_cron(job_name, cron, NUDGE_TASK, args=args, enabled=enabled)
    else:
        moment = at if isinstance(at, datetime) else parse_when(str(at))
        scheduler.schedule_once(job_name, moment, NUDGE_TASK, args=args)
        if not enabled:
            scheduler.set_enabled(job_name, False)

    record = get_reminder(job_name, settings=settings)
    if record is None:  # pragma: no cover - the upsert above always creates it
        raise RuntimeError(f"reminder {job_name!r} did not persist")
    return record


def list_reminders(*, settings: Settings | None = None) -> list[ReminderRecord]:
    settings = settings or get_settings()
    _configure(settings)
    return [
        _record(job, settings)
        for job in scheduler.list_jobs()
        if job.get("task") == NUDGE_TASK
    ]


def get_reminder(name: str, *, settings: Settings | None = None) -> ReminderRecord | None:
    settings = settings or get_settings()
    _configure(settings)
    for job in scheduler.list_jobs():
        if job.get("name") == name and job.get("task") == NUDGE_TASK:
            return _record(job, settings)
    return None


def remove_reminder(name: str, *, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    _configure(settings)
    return scheduler.remove_job(name)


def set_enabled(name: str, enabled: bool, *, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    _configure(settings)
    return scheduler.set_enabled(name, enabled)


__all__ = [
    "NUDGE_TASK",
    "add_reminder",
    "derive_name",
    "get_reminder",
    "list_reminders",
    "parse_when",
    "remove_reminder",
    "set_enabled",
    "slugify",
]
