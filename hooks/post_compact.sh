#!/bin/bash
# PostCompact hook — remind Claude to restate current state after compression

LOG_FILE="$HOME/.claude/compact-events.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PostCompact triggered" >> "$LOG_FILE"

cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PostCompact","additionalContext":"Context has been compressed. Before continuing, briefly restate: what task is in progress, what has been verified, and what is the next step. Do not continue from an unverified state."}}
JSON

exit 0
