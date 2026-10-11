"""Typer CLI for Nudge."""

from __future__ import annotations

import asyncio

import typer
from agentkit import build_deps, build_model, build_runtime, repositories
from agentkit.session import ChatRunner

from nudge import __version__
from nudge.config import Settings, get_settings

# Importing the service registers the durable "nudge" scheduler task before any
# init_scheduler / web UI path can list or create jobs.
from nudge.services import nudges as nudge_svc  # noqa: F401  (registers the task)
from nudge.services import reminders as reminder_svc

app = typer.Typer(
    add_completion=False,
    help="Nudge — a general reminder agent (cron + one-off, SOUL-voiced nudges).",
    no_args_is_help=True,
)


def _runtime():
    return build_runtime(get_settings())


def _enable_observability() -> None:
    from agentkit.observability import setup_observability

    setup_observability(get_settings())


@app.command()
def version() -> None:
    """Print the Nudge version."""
    typer.echo(f"nudge {__version__}")


@app.command()
def add(
    text: str = typer.Argument(..., help="What to be reminded about."),
    cron: str | None = typer.Option(None, "--cron", help="Cron expression, e.g. '0 8 * * 1'."),
    at: str | None = typer.Option(
        None, "--at", help="One-off datetime or phrase, e.g. 'tomorrow 09:00'."
    ),
    name: str | None = typer.Option(None, help="Reminder name (default: a slug of the text)."),
    target: str | None = typer.Option(None, "--target", help="local | telegram | both."),
    disabled: bool = typer.Option(False, "--disabled", help="Create the reminder paused."),
) -> None:
    """Add a recurring (--cron) or one-off (--at) reminder."""
    try:
        record = reminder_svc.add_reminder(
            text=text,
            cron=cron,
            at=at,
            name=name,
            target=target,
            enabled=not disabled,
            settings=get_settings(),
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    state = "on" if record.enabled else "off"
    typer.echo(
        f"reminder '{record.name}' registered ({record.kind}/{state}: {record.schedule}); "
        "run 'nudge worker' or 'nudge up' to fire it"
    )


@app.command("list")
def list_command() -> None:
    """List the reminders."""
    rows = reminder_svc.list_reminders(settings=get_settings())
    if not rows:
        typer.echo("no reminders")
        return
    for record in rows:
        state = "on" if record.enabled else "off"
        typer.echo(f"{record.name} [{record.kind}/{state}] {record.schedule} -> {record.target}  {record.text}")


@app.command()
def remove(name: str = typer.Argument(..., help="Reminder name.")) -> None:
    """Remove a reminder."""
    removed = reminder_svc.remove_reminder(name, settings=get_settings())
    typer.echo("removed" if removed else "not found")


@app.command()
def enable(name: str = typer.Argument(..., help="Reminder name.")) -> None:
    """Enable a reminder."""
    _set_enabled(name, True)


@app.command()
def disable(name: str = typer.Argument(..., help="Reminder name.")) -> None:
    """Disable a reminder (keep its definition)."""
    _set_enabled(name, False)


def _set_enabled(name: str, enabled: bool) -> None:
    changed = reminder_svc.set_enabled(name, enabled, settings=get_settings())
    if changed:
        typer.echo(("enabled " if enabled else "disabled ") + name)
    else:
        typer.echo(f"no reminder named {name}")


@app.command()
def inbox(limit: int = typer.Option(20, "--limit", help="How many recent nudges to show.")) -> None:
    """Read the delivered nudges from the durable outbox."""
    messages = nudge_svc.read_outbox(settings=get_settings(), limit=limit)
    if not messages:
        typer.echo("outbox empty")
        return
    for message in messages:
        typer.echo(message)


@app.command()
def preview(text: str = typer.Argument(..., help="Reminder text to rewrite.")) -> None:
    """Rewrite a reminder in Nudge's voice without scheduling it (uses the model)."""
    _enable_observability()
    typer.echo(nudge_svc.preview(text, settings=get_settings()))


@app.command()
def fire(name: str = typer.Argument(..., help="Reminder name.")) -> None:
    """Deliver a reminder now (non-durable) and print the nudge."""
    _enable_observability()
    try:
        message = nudge_svc.run_reminder_now(name, settings=get_settings())
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(message)


@app.command()
def soul(
    init: bool = typer.Option(False, "--init", help="Write a default SOUL.md if missing."),
) -> None:
    """Show the active SOUL.md persona (or scaffold one with --init)."""
    from nudge.soul import ensure_soul, load_soul, resolve_soul_path

    settings = get_settings()
    if init:
        typer.echo(f"wrote {ensure_soul(settings)}")
        return
    typer.echo(f"# {resolve_soul_path(settings)}")
    typer.echo(load_soul(settings))


@app.command()
def chat(conv: str = typer.Option("cli:default", help="Conversation id.")) -> None:
    """Interactive chat with Nudge."""
    _enable_observability()
    asyncio.run(_chat(conv))


async def _chat(conv: str) -> None:
    from nudge.agents.orchestrator import orchestrator_agent

    runtime = _runtime()
    typer.echo(f"Nudge ({conv}). Type 'exit' to quit.")
    while True:
        try:
            text = await asyncio.to_thread(input, "you> ")
        except (EOFError, KeyboardInterrupt):
            break
        text = text.strip()
        if text in {"exit", "quit", ":q"}:
            break
        if not text:
            continue
        with repositories(runtime) as repos:
            deps = build_deps(runtime, repos, model=build_model(runtime.settings))
            runner = ChatRunner(deps, agent=orchestrator_agent, conversation_id=conv)
            result = await runner.send(text)
        typer.echo(f"nudge> {result.output}")


@app.command()
def worker() -> None:
    """Run the durable worker (DBOS queues + the scheduler tick)."""
    import time

    from agentkit import durability, scheduler

    _enable_observability()
    settings = get_settings()
    durability.init(settings)
    scheduler.init_scheduler(settings)
    typer.echo("Nudge worker running (durable queues + schedules). Ctrl-C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:  # pragma: no cover
        typer.echo("worker stopped")


@app.command()
def up(
    a2a: bool = typer.Option(True, "--a2a/--no-a2a", help="Run the A2A server."),
    mcp: bool = typer.Option(True, "--mcp/--no-mcp", help="Run the MCP HTTP server."),
    bot: bool = typer.Option(True, "--bot/--no-bot", help="Run the Telegram bot (if configured)."),
) -> None:
    """Run the whole stack in one process (worker + A2A + MCP + bot + web UI).

    The DBOS worker (queues + the every-minute scheduler tick) starts
    automatically, so cron/one-off reminders fire while this runs.
    """
    from agentkit import durability, scheduler
    from agentkit.supervise import Service, run_all

    settings = get_settings()
    run_bot_enabled = bot and bool(settings.telegram_bot_token)
    if not (a2a or mcp or run_bot_enabled or settings.webui_enabled):
        typer.echo("nothing to run")
        return

    _enable_observability()
    durability.init(settings)
    scheduler.init_scheduler(settings)
    runtime = _runtime()

    services: list[Service] = []
    if a2a:
        services.append(Service("a2a", lambda: _serve_a2a(settings, runtime)))
    if mcp:
        services.append(Service("mcp", lambda: _serve_mcp(settings, runtime)))
    if run_bot_enabled:
        from nudge.gateways.telegram_bot import run_bot

        services.append(Service("bot", lambda: run_bot(settings)))

    typer.echo("nudge up: " + ", ".join(service.name for service in services))
    run_all(
        services,
        settings=settings,
        runtime=runtime,
        webui_answer=_webui_answer(settings, runtime),
    )


@app.command()
def mcp(
    transport: str = typer.Option("streamable-http", help="stdio | streamable-http | sse"),
) -> None:
    """Run Nudge as an MCP server (full agent + reminder tools)."""
    _enable_observability()
    _serve_mcp(get_settings(), _runtime(), transport=transport)


@app.command()
def a2a() -> None:
    """Run Nudge as an A2A server (agent card + JSON-RPC)."""
    _enable_observability()
    settings = get_settings()
    _serve_a2a(settings, _runtime())


def _webui_answer(settings: Settings, runtime):
    """A ``(conversation_id, text) -> ChatResult`` chat callable for the web UI."""
    from nudge.agents.orchestrator import orchestrator_agent

    async def answer(conversation_id: str, text: str):
        with repositories(runtime) as repos:
            deps = build_deps(runtime, repos, model=build_model(settings))
            runner = ChatRunner(deps, agent=orchestrator_agent, conversation_id=conversation_id)
            return await runner.send(text)

    return answer


def _answer(settings: Settings, runtime):
    from nudge.agents.orchestrator import orchestrator_agent

    async def answer(text: str) -> str:
        with repositories(runtime) as repos:
            deps = build_deps(runtime, repos, model=build_model(settings))
            runner = ChatRunner(deps, agent=orchestrator_agent, conversation_id="a2a:default")
            return (await runner.send(text)).output

    return answer


def _serve_a2a(settings: Settings, runtime) -> None:
    from agentkit.a2a import (
        SQLAlchemyTaskStore,
        TaskAgentExecutor,
        build_a2a_app,
        build_card,
        serve_a2a,
    )

    card = build_card(
        name=settings.a2a_card_name,
        description="Nudge — a general reminder agent (cron + one-off).",
        url=settings.a2a_public_url,
        skills=[{"id": "reminders", "name": "Reminders", "tags": ["reminder", "schedule"]}],
    )
    app = build_a2a_app(
        card=card,
        executor=TaskAgentExecutor(_answer(settings, runtime)),
        task_store=SQLAlchemyTaskStore(runtime),
        healthz=lambda: True,
    )
    serve_a2a(app, host=settings.a2a_host, port=settings.a2a_port)


def _serve_mcp(settings: Settings, runtime, *, transport: str = "streamable-http") -> None:
    from agentkit.mcp.server import serve_mcp
    from fastmcp import FastMCP

    from nudge.agents.schemas import ReminderRecord

    server = FastMCP(name="nudge", instructions="A general reminder agent (cron + one-off).")

    @server.tool
    async def ask_nudge(prompt: str, conversation_id: str = "mcp:default") -> str:
        """Ask the full Nudge agent."""
        from nudge.agents.orchestrator import orchestrator_agent

        with repositories(runtime) as repos:
            deps = build_deps(runtime, repos, model=build_model(settings))
            runner = ChatRunner(deps, agent=orchestrator_agent, conversation_id=conversation_id)
            return (await runner.send(prompt)).output

    @server.tool
    def add_reminder(
        text: str,
        cron: str | None = None,
        at: str | None = None,
        target: str | None = None,
    ) -> ReminderRecord:
        """Schedule a reminder (exactly one of cron or at)."""
        return reminder_svc.add_reminder(
            text=text, cron=cron, at=at, target=target, settings=settings
        )

    @server.tool
    def list_reminders() -> list[ReminderRecord]:
        """List the reminders."""
        return reminder_svc.list_reminders(settings=settings)

    @server.tool
    def inbox(limit: int = 20) -> list[str]:
        """Read the delivered nudges from the outbox."""
        return nudge_svc.read_outbox(settings=settings, limit=limit)

    serve_mcp(server, transport=transport, host=settings.mcp_host, port=settings.mcp_port)


def main() -> None:
    from agentkit.logging import setup_logging

    setup_logging(get_settings())
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
