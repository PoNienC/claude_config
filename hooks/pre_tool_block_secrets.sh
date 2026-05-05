#!/usr/bin/env bash
# pre_tool_block_secrets.sh
# Fires before Write/Edit. Blocks common secret patterns.
# Reads the tool event JSON from stdin; exits non-zero with a message to block.

set -euo pipefail

# Read event payload
PAYLOAD=$(cat)

# Extract candidate content (works for Write/Edit shapes)
CONTENT=$(printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    e = json.load(sys.stdin)
    parts = []
    inp = e.get("tool_input", {})
    for k in ("content", "new_string", "file_text"):
        v = inp.get(k)
        if isinstance(v, str):
            parts.append(v)
    print("\n".join(parts))
except Exception:
    pass
')

# Patterns to refuse
PATTERNS=(
  'AKIA[0-9A-Z]{16}'                 # AWS access key
  'aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{20,}'
  'sk-[A-Za-z0-9]{32,}'              # OpenAI / Anthropic-style
  'xox[abprs]-[0-9A-Za-z-]{10,}'     # Slack token
  'ghp_[A-Za-z0-9]{30,}'             # GitHub PAT
  'postgres(ql)?://[^:]+:[^@]+@'     # libpq URL with embedded password
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
)

for p in "${PATTERNS[@]}"; do
  if printf '%s' "$CONTENT" | grep -E -q "$p"; then
    echo "BLOCKED: pattern '$p' detected. Refusing to write a secret. Move it to .env (gitignored) or a secret manager." >&2
    exit 2
  fi
done

exit 0
