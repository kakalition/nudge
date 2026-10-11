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
