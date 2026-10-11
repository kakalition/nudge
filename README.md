# Nudge

**A general reminder agent that speaks in your own voice.** Set a reminder once —
recurring or a single moment — and when it fires, Nudge rewrites it in the persona
defined by `SOUL.md`: warm, short, and specific, never an alarm. It keeps a durable
local outbox, pushes to Telegram when configured, and runs everything on
agentkit's exactly-once scheduler that survives restarts.

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
![Built on agentkit](https://img.shields.io/badge/built%20on-agentkit-6f42c1)

Built on [**agentkit**](https://github.com/kakalition/agentkit) — PydanticAI v2 +
DBOS durable execution + MCP/A2A. Nudge is the reminders domain; agentkit is the
plumbing.

> Nudge is a reminder companion, not a task manager. It reminds; it does not
> decide, and it never invents tasks you didn't ask it to track.

---

## Why Nudge

- **Reminders, not alarms.** Every nudge is composed from your reminder text plus
  `SOUL.md`, so a daily "keep the streak" never reads the same way twice.
- **Recurring *or* one-off.** `--cron "0 8 * * 1"` for a schedule; `--at
  "tomorrow 09:00"` for a single moment (ISO or natural language).
- **Never loses a reminder.** The outbox write is durable and happens first; if
  the model is down it falls back to a fixed template, and if Telegram fails the
  reminder is still in the outbox.
- **Exactly-once scheduling.** Jobs are `scheduled_jobs` rows fired by a durable
  DBOS tick with a deterministic workflow id — a restart can't double-fire a job.
- **Local and private.** Everything runs on your machine; the outbox is a local
  conversation you own, and secrets are redacted from logs.
- **Reachable everywhere.** CLI, Telegram, MCP, A2A, plus a zero-code operator
  web UI.

## Table of contents

- [What it does](#what-it-does)
- [How it works](#how-it-works)
- [Install](#install)
- [Configure](#configure)
- [CLI](#cli)
- [Web UI](#web-ui)
- [Agents](#agents)
- [MCP & A2A](#mcp--a2a)
- [Persona (`SOUL.md`)](#persona-soulmd)
- [Observability](#observability)
- [FAQ](#faq)
- [Development](#development)
- [License](#license)

## What it does

```console
$ nudge add "call mom" --at "tomorrow 09:00"
reminder 'call-mom' registered (once/on: 2026-10-12T09:00:00); run 'nudge worker' or 'nudge up' to fire it

$ nudge add "drink water" --cron "0 10 * * *" --target both
reminder 'drink-water' registered (cron/on: 0 10 * * *); run 'nudge worker' or 'nudge up' to fire it

$ nudge list
drink-water [cron/on] 0 10 * * * -> both  drink water
call-mom [once/on] 2026-10-12T09:00:00 -> local  call mom

$ nudge preview "call mom"
Time for a quick call with your mom — even a two-minute hello counts.

$ nudge fire call-mom          # deliver now, without waiting for the scheduler
Time for a quick call with your mom — even a two-minute hello counts.

$ nudge inbox
Time for a quick call with your mom — even a two-minute hello counts.
```

- **Add / update / remove** reminders, with names derived from the text (or
  `--name`).
- **Compose** each nudge with a small PydanticAI agent whose instructions are
  `SOUL.md` + a one-line brief — deterministic fallback if the model is
  unavailable.
- **Deliver** to the durable **outbox** always, and to **Telegram** when
  configured; every delivery is written to the hash-chained audit log.
- **Fire exactly once** via agentkit's DBOS tick while `nudge up` / `nudge worker`
  is running, or on demand with `nudge fire`.

## How it works

```text
nudge up
  ├─ worker   durability.init + scheduler.init_scheduler  → DBOS tick (every minute)
  ├─ bot      Telegram bot (optional)
  ├─ a2a      A2A server (optional)          ┐
  ├─ mcp      MCP HTTP server (optional)     ├─ run_all
  └─ webui    Schedules + Conversations (auto-appended)
                                    │
   tick (exactly-once) ──▶ run_job("nudge", args)
                              └─ nudge_task(text, target, name)
                                   ├─ compose_nudge()  model + SOUL.md → message
                                   ├─ outbox           append to "nudge:outbox"
                                   ├─ telegram         send_markdown to owner chat
                                   └─ audit            "nudge.delivered"

data: ~/.agentkit/nudge/{nudge.db, dbos.sqlite, SOUL.md, artifacts/, logs/}
```

Reminders are ordinary `scheduled_jobs` rows (`task="nudge"`,
`args={"text": …, "target": …}`) and the outbox is a normal conversation
(`nudge:outbox`) — **no domain tables**, so the stock web UI Schedules and
Conversations pages work with zero per-agent code.

## Install

```bash
git clone https://github.com/kakalition/nudge && cd nudge
./install.sh                 # uv sync (incl. the local Phoenix observability UI)
cp .env.example .env         # then set OPENAI_API_KEY
```

Requires **Python 3.11–3.12** and [uv](https://docs.astral.sh/uv/). Nudge depends
on `agentkit`, installed from the sibling checkout via `[tool.uv.sources]`.

### Quickstart

```bash
export OPENAI_API_KEY=sk-...                      # or put it in .env
uv run nudge add "call mom" --at "tomorrow 09:00"
uv run nudge list
uv run nudge preview "call mom"                    # SOUL-voiced rewrite, no schedule
uv run nudge fire call-mom                          # deliver now (non-durable)
uv run nudge inbox                                  # read the outbox
uv run nudge up                                     # worker + A2A + MCP + web UI (:8787)
```

## Configure

Nudge reads standard agentkit variables plus its own. Copy `.env.example` to
`.env` and set what you need; every variable can also be exported.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | – | Model credential |
| `OPENAI_BASE_URL` | – | Any OpenAI-compatible gateway |
| `MODEL_NAME` | `openai:gpt-4o-mini` | Model id |
| `OWNER_ID` / `OWNER_NAME` | `owner` / `Owner` | The owner |
| `AGENTKIT_HOME` | `~/.agentkit` | Workspace root (`~/.agentkit/nudge`) |
| `AGENT_HOME` | `~/.agentkit/nudge` | Explicit home override |
| `NUDGE_DEFAULT_TARGET` | `local` | `local` \| `telegram` \| `both` |
| `WEBUI_ENABLED` / `WEBUI_HOST` / `WEBUI_PORT` | `true` / `127.0.0.1` / `8787` | Operator web UI |
| `OBSERVABILITY` | `phoenix` | `phoenix` (local UI) \| `console` \| `otlp` \| `off` |
| `TELEGRAM_BOT_TOKEN` | – | Enables Telegram delivery / the bot |
| `TELEGRAM_ALLOWED_CHAT_IDS` | – | Allowlist; the **first** id is the owner chat |
| `A2A_PUBLIC_URL` / `A2A_HOST` / `A2A_PORT` | `http://127.0.0.1:9200` | A2A |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8960` | MCP HTTP |

## CLI

| Command | Purpose |
| --- | --- |
| `nudge add TEXT --cron "…" \| --at "…" [--name N] [--target local\|telegram\|both] [--disabled]` | Add or update a reminder |
| `nudge list` | List reminders |
| `nudge remove NAME` | Remove a reminder |
| `nudge enable NAME` / `nudge disable NAME` | Turn a reminder on/off |
| `nudge inbox [--limit 20]` | Read delivered nudges from the outbox |
| `nudge preview TEXT` | Rewrite a reminder in Nudge's voice (no schedule) |
| `nudge fire NAME` | Deliver one reminder now (non-durable) |
| `nudge soul [--init]` | Show (or scaffold) the persona |
| `nudge chat` | Interactive chat with the orchestrator |
| `nudge worker` | Run the durable worker only (cron + one-off fire here) |
| `nudge up` | One process: worker + A2A + MCP + bot + web UI |
| `nudge mcp` / `nudge a2a` | Run just the MCP / A2A server |

`add`, `list`, `remove`, `enable`, `disable` and `inbox` are deterministic (no
model). `preview`, `fire` and `chat` use the model.

`--at` accepts an ISO datetime or light natural language (`tomorrow 09:00`,
`today 18:30`); `--cron` takes a raw cron expression.

## Web UI

`nudge up` also serves an operator web UI at `http://127.0.0.1:8787` (loopback,
no auth) for **this agent only**:

- **Schedules** — create, edit, enable/disable and delete reminders. They are
  ordinary `task="nudge"` jobs, so the page lists the `nudge` task and accepts it
  as-is.
- **Conversations** — read delivered nudges in `nudge:outbox`.
- **Usage / Audit / Workflows** — token counts, the hash-chained audit log, and
  durable DBOS workflows.

## Agents

An orchestrator routes natural-language chat to one specialist:

| Agent | Tools | Notes |
| --- | --- | --- |
| **reminder** (specialist) | `add_reminder`, `list_reminders`, `cancel_reminder`, `pause_reminder`, `resume_reminder` | Thin wrapper over `agentkit.scheduler` |
| **nudge** (voice) | *(structured output)* | Rewrites one reminder in the SOUL voice; template fallback |

Chat via `nudge chat`, Telegram, MCP or A2A can set and manage reminders in words —
the specialist resolves timing (e.g. "remind me every Monday at 8").

## MCP & A2A

`nudge up` exposes Nudge over both protocols in one process:

- **MCP** (`http://127.0.0.1:8960/mcp`): `ask_nudge`, `add_reminder`,
  `list_reminders`, `inbox`.
- **A2A** (`http://127.0.0.1:9200`): agent card + JSON-RPC, task-based, backed by
  a durable task store.

Point another agent (Hermes, nanobot, …) at either endpoint to let it schedule or
read reminders through Nudge.

## Persona (`SOUL.md`)

Nudge's identity lives in `SOUL.md` (project root, else `$AGENT_HOME/SOUL.md`) and
is composed with the routing instructions — it is the same text that flavours
every delivered nudge. Edit it to change how Nudge talks.

```bash
nudge soul          # show the active persona
nudge soul --init   # scaffold one if missing
```

## Observability

**On by default** with a local **Arize Phoenix** UI (self-hosted, no account);
falls back to console spans if Phoenix isn't installed. Set `OBSERVABILITY=otlp`
to export to Jaeger/Tempo/Langfuse/a collector.

## FAQ

**Do reminders fire when my laptop sleeps?** No — cron/one-off jobs fire only while
`nudge up` or `nudge worker` is running (agentkit's semantics). `nudge fire NAME`
is the on-demand escape hatch, and a one-off that comes due while the worker is up
fires exactly once even across restarts.

**What if the model is down when a reminder fires?** Nudge falls back to a fixed
template, still writes the outbox, and audits `nudge.compose_failed` — a reminder
is never lost to a model error.

**Where does it send nudges?** To the local outbox always; to Telegram when
`TELEGRAM_BOT_TOKEN` is set and the target is `telegram`/`both`. With no dedicated
chat id configured, the **first** `TELEGRAM_ALLOWED_CHAT_IDS` entry is the owner
chat.

**Can I reuse a name?** Yes — `--name` upserts (updates) that reminder. Without
`--name`, the name is a slug of the text with a numeric suffix if taken.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run mypy src/nudge
```

Layout: `config`, `soul`, `cli`; `services/` (reminders, nudges); `agents/`
(deps, prompts, schemas, reminder, nudge, orchestrator);
`gateways/telegram_bot.py`.

## License

MIT — see [LICENSE](LICENSE).
