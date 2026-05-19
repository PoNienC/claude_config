#!/bin/bash
# PreCompact hook — remind Claude to preserve state before context compression

LOG_FILE="$HOME/.claude/compact-events.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PreCompact triggered" >> "$LOG_FILE"

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreCompact","additionalContext":"⚠️ Context is about to be compressed — confirm that any critical progress, decisions, and pending work are captured in Auto Memory (/memory). If there are open todos, make sure they are tracked before continuing."}}
JSON

exit 0
