#!/usr/bin/env bash
# session_start_context.sh
# Fires once when a Claude Code session opens. Output is injected as system context.
# Reusable across any GIS / data project.

set -euo pipefail

echo "=== Session context ==="
echo "Date: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "CWD:  $(pwd)"

# Git state
if [ -d .git ]; then
  echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
  CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  echo "Uncommitted changes: ${CHANGES}"
  echo "Last commit: $(git log -1 --pretty=format:'%h %s' 2>/dev/null || echo 'none')"
fi

# PostGIS connection check (non-blocking; just informational)
if command -v psql >/dev/null 2>&1 && [ -n "${DATABASE_URL:-}" ]; then
  if psql "$DATABASE_URL" -tAc "SELECT 1" >/dev/null 2>&1; then
    echo "PostGIS: reachable"
  else
    echo "PostGIS: unreachable (check DATABASE_URL)"
  fi
fi

# Surface in-flight TODOs
if [ -f docs/TODO.md ]; then
  echo ""
  echo "=== Open TODOs (docs/TODO.md, first 10 lines) ==="
  head -n 10 docs/TODO.md
fi

# Remind Claude of current model/runtime if Ollama is in play
if command -v ollama >/dev/null 2>&1; then
  RUNNING=$(ollama ps 2>/dev/null | tail -n +2 | awk '{print $1}' | head -n 3 | tr '\n' ' ')
  if [ -n "$RUNNING" ]; then
    echo "Ollama models running: $RUNNING"
  fi
fi

exit 0
