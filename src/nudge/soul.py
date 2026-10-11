"""SOUL.md resolution for Nudge (project root, else the agent home)."""

from __future__ import annotations

from pathlib import Path

from agentkit.soul import DEFAULT_SOUL, compose_instructions  # noqa: F401  (re-export)
from agentkit.soul import ensure_soul as _ensure_soul
from agentkit.soul import load_soul as _load_soul
from agentkit.soul import soul_path as _soul_path

from nudge.config import Settings, get_settings

PROJECT_SOUL = Path("SOUL.md")

# The persona Nudge ships with (written to the project root by ``ensure_soul``).
NUDGE_SOUL = """\
# Soul

I am **Nudge**, a quiet reminder companion. I help you remember — then I get out
of the way.

## How I speak

- One short message. A reminder, not an essay.
- Warm and specific, never nagging. I nudge once; I don't pile on.
- I keep your words for the substance and add nothing you didn't ask me to track.
- For repeating reminders I vary the wording so it never feels robotic.
- No guilt, no streak-shaming, no exclamation-mark spam.

## Boundaries

- I remind; I don't decide. I never invent tasks you didn't ask me to track.
- I keep your reminders and their contents private; no secrets in logs.
- If a reminder looks like it needs real help, I say so plainly.
"""


def resolve_soul_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return PROJECT_SOUL if PROJECT_SOUL.exists() else _soul_path(settings)


def load_soul(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if PROJECT_SOUL.exists():
        text = PROJECT_SOUL.read_text(encoding="utf-8").strip()
        if text:
            return text
    return _load_soul(settings)


def ensure_soul(settings: Settings | None = None, *, overwrite: bool = False) -> Path:
    if overwrite or not PROJECT_SOUL.exists():
        try:
            PROJECT_SOUL.write_text(NUDGE_SOUL, encoding="utf-8")
            return PROJECT_SOUL
        except OSError:
            pass
    return _ensure_soul(settings, overwrite=overwrite)


__all__ = [
    "DEFAULT_SOUL",
    "NUDGE_SOUL",
    "compose_instructions",
    "load_soul",
    "resolve_soul_path",
    "ensure_soul",
]
