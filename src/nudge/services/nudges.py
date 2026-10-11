"""Nudge composition and delivery.

A reminder fires through the durable scheduler, which calls :func:`nudge_task`.
The task composes one short message with the nudge-voice agent (SOUL + model),
writes it to the durable local outbox, optionally pushes it to Telegram, and
audits the delivery. The outbox write always happens first, so a channel failure
never loses a reminder; a model failure falls back to a fixed template.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Any

from agentkit import scheduler
from agentkit.config import AgentSettings, build_model
from agentkit.gateways.telegram import send_markdown
from agentkit.runtime import Runtime, repositories
from agentkit.session import deserialize_messages, serialize_message
from aiogram import Bot
from pydantic_ai.messages import ModelResponse, TextPart

from nudge.agents.nudge import build_nudge_agent
from nudge.agents.schemas import NudgeReceipt
from nudge.config import Settings, get_settings
from nudge.services import reminders as reminders_svc

OUTBOX_CONVERSATION = "nudge:outbox"
OUTBOX_CHANNEL = "nudge"
NUDGE_FALLBACK = "Reminder: {text}"


def compose_prompt(text: str, *, name: str = "", now: datetime | None = None) -> str:
    """The message handed to the nudge-voice agent for one reminder."""
    now = now or datetime.now()
    lines = [f"Reminder to deliver: {text.strip()}"]
    if name:
        lines.append(f"(label: {name})")
    lines.append(f"(local time: {now.strftime('%A %Y-%m-%d %H:%M')})")
    return "\n".join(lines)


def _audit(settings: Settings, action: str, *, target: str = "", detail: dict | None = None) -> None:
    with contextlib.suppress(Exception):  # auditing must never break delivery
        runtime = scheduler.ensure_configured(settings)
        with repositories(runtime) as repos:
            repos.audit.append(action, target=target, detail=detail or {})


def compose_nudge(
    settings: Settings | None = None,
    text: str = "",
    *,
    name: str = "",
    now: datetime | None = None,
    model: Any = None,
) -> str:
    """Rewrite one reminder in Nudge's voice; fall back to a template on error."""
    settings = settings or get_settings()
    try:
        agent = build_nudge_agent(settings)
        run_model = model or build_model(settings)
        result = asyncio.run(
            agent.run(compose_prompt(text, name=name, now=now), model=run_model)
        )
        output = (result.output or "").strip()
        if not output:
            raise ValueError("model returned an empty nudge")
        return output
    except Exception as exc:
        _audit(
            settings,
            "nudge.compose_failed",
            target=name or "nudge",
            detail={"error": type(exc).__name__},
        )
        return NUDGE_FALLBACK.format(text=(text or name or "reminder").strip())


def _send_telegram(settings: AgentSettings, text: str) -> bool:
    token = settings.telegram_bot_token
    if not token:
        return False
    chat_ids = list(settings.telegram_allowed_chat_ids)

    async def _go() -> None:
        bot = Bot(token)
        try:
            for chat_id in chat_ids:
                await send_markdown(bot, chat_id, text)
        finally:
            with contextlib.suppress(Exception):
                await bot.session.close()

    try:
        asyncio.run(_go())
        return True
    except Exception:  # pragma: no cover - delivery failures are non-fatal
        return False


def deliver_nudge(
    runtime: Runtime, *, name: str = "", text: str = "", target: str = "local"
) -> NudgeReceipt:
    """Write the nudge to the outbox, then push to Telegram, then audit."""
    settings = runtime.settings
    message = (text or "").strip()

    with repositories(runtime) as repos:
        repos.conversations.get_or_create(OUTBOX_CONVERSATION, channel=OUTBOX_CHANNEL)
        repos.messages.append(
            OUTBOX_CONVERSATION, [serialize_message(ModelResponse(parts=[TextPart(message)]))]
        )
        repos.conversations.touch(OUTBOX_CONVERSATION)

    delivered = ["outbox"]
    if (
        target in {"telegram", "both"}
        and settings.telegram_bot_token
        and settings.telegram_allowed_chat_ids
        and _send_telegram(settings, message)
    ):
        delivered.append("telegram")

    with repositories(runtime) as repos:
        repos.audit.append(
            "nudge.delivered",
            target=name or "nudge",
            detail={"channel": target, "delivered": delivered, "text": message},
        )
    return NudgeReceipt(name=name, text=message, target=target, delivered=delivered)


@scheduler.task("nudge")
def nudge_task(*, text: str = "", target: str = "local", name: str = "", **_: Any) -> None:
    """Durable scheduler task: compose and deliver one reminder."""
    settings = get_settings()
    runtime = scheduler.ensure_configured(settings)
    message = compose_nudge(settings, text or name or "reminder", name=name)
    deliver_nudge(runtime, name=name, text=message, target=target)


def run_reminder_now(name: str, *, settings: Settings | None = None) -> str:
    """Fire one reminder inline (non-durable) and return the delivered nudge."""
    settings = settings or get_settings()
    reminder = reminders_svc.get_reminder(name, settings=settings)
    if reminder is None:
        raise ValueError(f"no reminder named {name!r}")
    runtime = scheduler.ensure_configured(settings)
    message = compose_nudge(settings, reminder.text, name=reminder.name)
    deliver_nudge(runtime, name=reminder.name, text=message, target=reminder.target)
    return message


def preview(text: str, *, settings: Settings | None = None, model: Any = None) -> str:
    """Compose (but do not schedule or deliver) a nudge for ``text``."""
    settings = settings or get_settings()
    return compose_nudge(settings, text, name="preview", model=model)


def read_outbox(*, settings: Settings | None = None, limit: int = 20) -> list[str]:
    """The delivered nudges, newest last (decoded from the outbox conversation)."""
    settings = settings or get_settings()
    runtime = scheduler.ensure_configured(settings)
    with repositories(runtime) as repos:
        payloads = [
            message.payload
            for message in repos.messages.list(OUTBOX_CONVERSATION, limit=limit)
        ]
    texts: list[str] = []
    for message in deserialize_messages(payloads):
        for part in getattr(message, "parts", []):
            if isinstance(part, TextPart):
                texts.append(part.content)
    return texts


__all__ = [
    "NUDGE_FALLBACK",
    "OUTBOX_CHANNEL",
    "OUTBOX_CONVERSATION",
    "compose_nudge",
    "compose_prompt",
    "deliver_nudge",
    "nudge_task",
    "preview",
    "read_outbox",
    "run_reminder_now",
]
