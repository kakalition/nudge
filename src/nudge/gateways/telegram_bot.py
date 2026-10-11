"""aiogram v3 Telegram front-end (long-polling).

Chats are allowlisted via ``TELEGRAM_ALLOWED_CHAT_IDS``; each chat maps to a
conversation id ``tg:<chat_id>``. Bulk/destructive tool calls are approved with
inline buttons. :func:`notify_owner` is reused for proactive nudge delivery.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from agentkit.config import AgentSettings, build_model
from agentkit.gateways.telegram import (  # noqa: F401  (re-exported for convenience)
    ApprovalBroker,
    react_seen,
    send_markdown,
)
from agentkit.gateways.telegram import is_allowed as _is_allowed_ids
from agentkit.runtime import Runtime, build_deps, build_runtime, repositories
from agentkit.session import ChatRunner
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message

from nudge.config import Settings

DEFAULT_GREETING = "Nudge ready. Tell me what to remind you about, and when."


def is_allowed(settings: AgentSettings, chat_id: int) -> bool:
    """Allow-list check bound to Nudge settings."""
    return _is_allowed_ids(settings.telegram_allowed_chat_ids, chat_id)


async def notify_owner(text: str, *, settings: Settings, bot: Bot | None = None) -> bool:
    """Push a message to every allowlisted chat; used for proactive nudges."""
    chat_ids = list(settings.telegram_allowed_chat_ids)
    if not settings.telegram_bot_token or not chat_ids:
        return False
    bot = bot or Bot(settings.telegram_bot_token)
    sent = False
    with contextlib.suppress(Exception):
        for chat_id in chat_ids:
            await send_markdown(bot, chat_id, text)
            sent = True
    return sent


async def handle_message(
    *,
    runtime: Runtime,
    broker: ApprovalBroker,
    bot: Bot,
    chat_id: int,
    text: str,
    model: Any = None,
) -> None:
    """Run one chat turn and deliver the reply."""
    from nudge.agents.orchestrator import orchestrator_agent

    conversation_id = f"tg:{chat_id}"
    with repositories(runtime) as repos:
        deps = build_deps(
            runtime,
            repos,
            model=model or build_model(runtime.settings),
            approve=lambda requests: broker.ask(bot, chat_id, requests),
        )
        runner = ChatRunner(deps, agent=orchestrator_agent, conversation_id=conversation_id)
        try:
            result = await runner.send(text)
        except Exception as exc:  # pragma: no cover - defensive
            await bot.send_message(chat_id, f"Something went wrong: {type(exc).__name__}")
            return
    await send_markdown(bot, chat_id, result.output)


def register_handlers(dp: Dispatcher, runtime: Runtime, broker: ApprovalBroker) -> None:
    settings = runtime.settings

    @dp.message(F.text)
    async def _on_text(message: Message) -> None:
        chat_id = message.chat.id
        if not is_allowed(settings, chat_id):
            await message.answer("This bot is private.")
            return
        await react_seen(message)
        if message.text and message.text.strip().startswith("/start"):
            await message.answer(DEFAULT_GREETING)
            return
        if message.bot is None:
            return
        await handle_message(
            runtime=runtime,
            broker=broker,
            bot=message.bot,
            chat_id=chat_id,
            text=message.text or "",
        )

    @dp.callback_query(F.data.startswith("approve:"))
    async def _on_approve(callback: CallbackQuery) -> None:
        call_id = (callback.data or "").split(":", 1)[-1]
        broker.resolve(call_id, True)
        await callback.answer("Approved")
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)

    @dp.callback_query(F.data.startswith("deny:"))
    async def _on_deny(callback: CallbackQuery) -> None:
        call_id = (callback.data or "").split(":", 1)[-1]
        broker.resolve(call_id, False)
        await callback.answer("Denied")
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)


async def _run_bot(settings: Settings) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    runtime = build_runtime(settings)
    broker = ApprovalBroker()
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    register_handlers(dp, runtime, broker)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def run_bot(settings: Settings) -> None:
    asyncio.run(_run_bot(settings))
