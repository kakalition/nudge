from __future__ import annotations

from nudge.gateways import telegram_bot as tb


async def test_run_bot_disables_signal_handling(monkeypatch, settings):
    """run_all() runs services on worker threads, so aiogram must not grab signals."""
    recorded: dict[str, object] = {}

    class _FakeBot:
        def __init__(self, token: str) -> None:
            self.token = token

        async def delete_webhook(self, **kwargs: object) -> None:
            return None

    class _FakeDispatcher:
        def message(self, *args: object, **kwargs: object):
            return lambda fn: fn

        def callback_query(self, *args: object, **kwargs: object):
            return lambda fn: fn

        async def start_polling(self, bot: object, **kwargs: object) -> None:
            recorded.update(kwargs)

    monkeypatch.setattr(tb, "Bot", _FakeBot)
    monkeypatch.setattr(tb, "Dispatcher", _FakeDispatcher)
    settings.telegram_bot_token = "1:abc"

    await tb._run_bot(settings)

    assert recorded.get("handle_signals") is False
