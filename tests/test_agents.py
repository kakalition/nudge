from __future__ import annotations

from agentkit import build_deps
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from nudge.agents.orchestrator import orchestrator_agent
from nudge.agents.reminder import reminder_agent
from nudge.services import reminders as reminder_svc


def _tool_names(agent) -> set[str]:
    return set(agent._function_toolset.tools.keys())


def _has_tool_return(messages: list[ModelMessage]) -> bool:
    return any(
        isinstance(part, ToolReturnPart)
        for message in messages
        for part in getattr(message, "parts", [])
    )


def test_orchestrator_registers_reminder_specialist():
    assert "handle_reminders" in _tool_names(orchestrator_agent)


async def test_orchestrator_persona_comes_from_soul(runtime, repos, settings):
    from nudge.soul import load_soul

    captured: dict[str, object] = {}

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["instructions"] = info.instructions
        return ModelResponse(parts=[TextPart("ok")])

    deps = build_deps(runtime, repos, model=FunctionModel(model_fn))
    await orchestrator_agent.run("hi", deps=deps, model=deps.model)

    text = str(captured["instructions"])
    assert load_soul(settings)[:20] in text  # persona is read from SOUL every run
    assert "You are Nudge" not in text  # no hardcoded identity


def test_reminder_agent_tools():
    assert _tool_names(reminder_agent) >= {
        "add_reminder",
        "list_reminders",
        "cancel_reminder",
        "pause_reminder",
        "resume_reminder",
    }


async def test_reminder_tool_schedules_job(runtime, repos, settings):
    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if _has_tool_return(messages):
            return ModelResponse(parts=[TextPart("scheduled")])
        return ModelResponse(
            parts=[ToolCallPart("add_reminder", {"text": "walk the dog", "cron": "0 7 * * *"})]
        )

    deps = build_deps(runtime, repos, model=FunctionModel(model_fn))
    result = await reminder_agent.run(
        "remind me to walk the dog every morning at 7", deps=deps, model=deps.model
    )

    assert result.output == "scheduled"
    rows = reminder_svc.list_reminders(settings=settings)
    assert [record.name for record in rows] == ["walk-the-dog"]
    assert rows[0].schedule == "0 7 * * *"
    assert rows[0].text == "walk the dog"


async def test_add_reminder_without_time_reports_error(runtime, repos, settings):
    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if _has_tool_return(messages):
            return ModelResponse(parts=[TextPart("I need a time for that.")])
        return ModelResponse(parts=[ToolCallPart("add_reminder", {"text": "call mom"})])

    deps = build_deps(runtime, repos, model=FunctionModel(model_fn))
    result = await reminder_agent.run("remind me to call mom", deps=deps, model=deps.model)

    assert result.output == "I need a time for that."
    assert reminder_svc.list_reminders(settings=settings) == []


async def test_orchestrator_still_replies_when_specialist_fails(runtime, repos, monkeypatch):
    from nudge.agents import orchestrator as orch

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("specialist down")

    monkeypatch.setattr(orch.reminder_agent, "run", boom)

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if _has_tool_return(messages):
            return ModelResponse(parts=[TextPart("handled")])
        return ModelResponse(
            parts=[ToolCallPart("handle_reminders", {"request": "remind me in 5 minutes"})]
        )

    deps = build_deps(runtime, repos, model=FunctionModel(model_fn))
    result = await orch.orchestrator_agent.run(
        "remind me in 5 minutes", deps=deps, model=deps.model
    )
    assert result.output == "handled"
