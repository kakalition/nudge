#!/usr/bin/env bash
# Idempotent setup for Nudge.
set -euo pipefail

cd "$(dirname "$0")"

echo "== syncing dependencies (uv) =="
uv sync --extra dev --extra observability-phoenix

if [ ! -f .env ]; then
  echo "== creating .env from .env.example =="
  cp .env.example .env
  echo "Edit .env and set OPENAI_API_KEY before running 'nudge preview' or 'nudge chat'."
fi

echo "== done =="
echo "Try: uv run nudge add \"call mom\" --at \"tomorrow 09:00\" && uv run nudge list"
