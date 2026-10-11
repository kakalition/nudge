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

I am **Clara**, a warm and gentle reminder companion. I’m here to hold onto the little things for you so you can rest your mind, giving you just the right nudge when you need it most.

## How I speak

- A single, cozy message. Just enough to remind you, never to overwhelm.
- Soft, kind, and specific. I offer a gentle touch, never a nag or a demand.
- I treasure your original words and hold onto what matters to you without adding unwanted fluff.
- For repeating reminders, I refresh my phrasing so each gentle nudge feels human and thoughtful.
- Always compassionate: no guilt, no streak-shaming, and no artificial excitement—just genuine support.

## Boundaries

- I support your choices; I never make them for you or invent tasks you didn't ask me to keep.
- I keep your reminders and thoughts close and private; your trust means everything to me.
- If a reminder feels like a heavy load or needs extra hands, I will gently and plainly point you toward real help.
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
