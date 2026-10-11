from __future__ import annotations

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from nudge.agents.nudge import build_nudge_agent
from nudge.services import nudges as svc
from nudge.services.nudges import NUDGE_FALLBACK, OUTBOX_CONVERSATION


def _model(text: str) -> FunctionModel:
    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(text)])

    return FunctionModel(model_fn)


def test_nudge_agent_composes_soul_instructions(settings):
    from nudge.soul import load_soul

    agent = build_nudge_agent(settings)
    instructions = str(agent._instructions)
    assert load_soul(settings).splitlines()[0] in instructions  # persona from SOUL
    assert "vary phrasing" in instructions  # plus the nudge brief


def test_compose_nudge_uses_model(settings):
    message = svc.compose_nudge(
        settings, "call mom", name="call-mom", model=_model("Time to call mom.")
    )
    assert message == "Time to call mom."


def test_compose_nudge_falls_back_on_model_error(settings):
    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("no model")

    message = svc.compose_nudge(settings, "call mom", name="call-mom", model=FunctionModel(boom))
    assert message == NUDGE_FALLBACK.format(text="call mom")


def test_deliver_nudge_writes_outbox_and_audit(runtime, repos):
    receipt = svc.deliver_nudge(runtime, name="call-mom", text="Time to call mom.", target="local")

    assert receipt.delivered == ["outbox"]
    conversation = repos.conversations.get(OUTBOX_CONVERSATION)
    assert conversation is not None
    assert conversation.channel == "nudge"
    assert len(repos.messages.list(OUTBOX_CONVERSATION)) == 1
    assert repos.audit.entries()[-1].action == "nudge.delivered"
    assert svc.read_outbox(settings=runtime.settings) == ["Time to call mom."]


def test_deliver_nudge_skips_telegram_without_token(runtime, monkeypatch):
    monkeypatch.setattr(svc, "Bot", object())  # any send attempt would fail loudly
    receipt = svc.deliver_nudge(runtime, name="call-mom", text="hello", target="both")
    assert receipt.delivered == ["outbox"]


def test_deliver_nudge_pushes_telegram_when_configured(settings, runtime, monkeypatch):
    settings.telegram_bot_token = "123:abc"
    settings.telegram_allowed_chat_ids = [5]

    sent: list[tuple[int, str]] = []

    class _FakeSession:
        async def close(self) -> None:
            return None

    class _FakeBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = _FakeSession()

    async def fake_send(bot, chat_id, text, **kwargs):
        sent.append((chat_id, text))

    monkeypatch.setattr(svc, "Bot", _FakeBot)
    monkeypatch.setattr(svc, "send_markdown", fake_send)

    receipt = svc.deliver_nudge(runtime, name="call-mom", text="hello", target="telegram")
    assert receipt.delivered == ["outbox", "telegram"]
    assert sent == [(5, "hello")]
