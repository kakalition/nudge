"""Structured tool/agent I/O models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReminderRecord(BaseModel):
    """One scheduled reminder (backed by a ``scheduled_jobs`` row, ``task="nudge"``)."""

    name: str
    text: str = ""
    kind: str = "cron"  # cron | once
    schedule: str = ""
    target: str = "local"  # local | telegram | both
    enabled: bool = True
    last_run: str | None = None
    run_count: int = 0


class NudgeReceipt(BaseModel):
    """The result of delivering one nudge."""

    name: str = ""
    text: str = ""
    target: str = "local"
    delivered: list[str] = Field(default_factory=list)  # e.g. ["outbox", "telegram"]
