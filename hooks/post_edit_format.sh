#!/usr/bin/env bash
# post-edit-format.sh
# Fires after Write/Edit. Auto-formats Python files; logs SQL edits for review.
# Reads tool event JSON from stdin and extracts the touched file path.

set -euo pipefail

PATH_TOUCHED=$(cat | python3 -c '
import sys, json
try:
    e = json.load(sys.stdin)
    inp = e.get("tool_input", {})
    print(inp.get("file_path") or inp.get("path") or "")
except Exception:
    print("")
')

[ -z "$PATH_TOUCHED" ] && exit 0
[ ! -f "$PATH_TOUCHED" ] && exit 0

case "$PATH_TOUCHED" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff check --fix "$PATH_TOUCHED" >/dev/null 2>&1 || true
    fi
    if command -v black >/dev/null 2>&1; then
      black --quiet "$PATH_TOUCHED" 2>/dev/null || true
    fi
    ;;
  *.sql)
    # Don't auto-rewrite SQL — too risky. Just log.
    echo "[hook] SQL edited: $PATH_TOUCHED — review before committing" >&2
    ;;
  *.ipynb)
    # Strip notebook outputs to keep diffs clean, if nbstripout is installed
    if command -v nbstripout >/dev/null 2>&1; then
      nbstripout "$PATH_TOUCHED" 2>/dev/null || true
    fi
    ;;
esac

exit 0
