#!/bin/bash
# ~/.claude/scripts/healthcheck.sh
# Validates that hooks, agents, skills, and settings are internally consistent.
# Usage: bash ~/.claude/scripts/healthcheck.sh

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RESET='\033[0m'

PASS=0
WARN=0
FAIL=0

pass() { echo -e "${GREEN}[PASS]${RESET} $1"; PASS=$((PASS + 1)); }
warn() { echo -e "${YELLOW}[WARN]${RESET} $1"; WARN=$((WARN + 1)); }
fail() { echo -e "${RED}[FAIL]${RESET} $1"; FAIL=$((FAIL + 1)); }

CLAUDE_DIR="$HOME/.claude"

echo "======================================"
echo " Claude Code — Health Check"
echo " Config dir: $CLAUDE_DIR"
echo "======================================"
echo ""

# --------------------------------------------------
# 1. settings.json — valid JSON
# --------------------------------------------------
echo "--- settings.json ---"
SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS" ]; then
  fail "settings.json not found: $SETTINGS"
else
  if python3 -m json.tool "$SETTINGS" > /dev/null 2>&1; then
    pass "settings.json is valid JSON"
  else
    fail "settings.json has JSON syntax errors"
  fi
fi

# --------------------------------------------------
# 2. Hooks — bash syntax + executable bit
# --------------------------------------------------
echo ""
echo "--- Hooks ($CLAUDE_DIR/hooks/) ---"
HOOKS_DIR="$CLAUDE_DIR/hooks"
if [ ! -d "$HOOKS_DIR" ]; then
  warn "hooks/ directory not found"
else
  COUNT=0
  for script in "$HOOKS_DIR"/*.sh; do
    [ -f "$script" ] || continue
    COUNT=$((COUNT + 1))
    name="$(basename "$script")"
    if bash -n "$script" 2>/dev/null; then
      pass "hooks/$name — bash syntax OK"
    else
      fail "hooks/$name — bash syntax error"
    fi
    if [ -x "$script" ]; then
      pass "hooks/$name — executable bit set"
    else
      warn "hooks/$name — not executable (run: chmod +x $script)"
    fi
  done
  [ "$COUNT" -eq 0 ] && warn "No .sh files found in hooks/"
fi

# --------------------------------------------------
# 3. Agents — required frontmatter fields
# --------------------------------------------------
echo ""
echo "--- Agents ($CLAUDE_DIR/agents/) ---"
AGENTS_DIR="$CLAUDE_DIR/agents"
REQUIRED_AGENT_FIELDS="name description tools model"
if [ ! -d "$AGENTS_DIR" ]; then
  warn "agents/ directory not found"
else
  COUNT=0
  for agent in "$AGENTS_DIR"/*.md; do
    [ -f "$agent" ] || continue
    COUNT=$((COUNT + 1))
    name="$(basename "$agent")"
    for field in $REQUIRED_AGENT_FIELDS; do
      if grep -q "^${field}:" "$agent" 2>/dev/null; then
        pass "agents/$name — field '$field' present"
      else
        fail "agents/$name — missing required field '$field'"
      fi
    done
  done
  [ "$COUNT" -eq 0 ] && warn "No .md files found in agents/"
fi

# --------------------------------------------------
# 4. Skills — required frontmatter in SKILL.md
# --------------------------------------------------
echo ""
echo "--- Skills ($CLAUDE_DIR/skills/) ---"
SKILLS_DIR="$CLAUDE_DIR/skills"
REQUIRED_SKILL_FIELDS="name description"
if [ ! -d "$SKILLS_DIR" ]; then
  warn "skills/ directory not found"
else
  COUNT=0
  for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_file="$skill_dir/SKILL.md"
    name="$(basename "$skill_dir")"
    if [ ! -f "$skill_file" ]; then
      fail "skills/$name — SKILL.md not found"
      continue
    fi
    COUNT=$((COUNT + 1))
    for field in $REQUIRED_SKILL_FIELDS; do
      if grep -q "^${field}:" "$skill_file" 2>/dev/null; then
        pass "skills/$name — field '$field' present"
      else
        fail "skills/$name — missing required field '$field'"
      fi
    done
  done
  [ "$COUNT" -eq 0 ] && warn "No skill directories found in skills/"
fi

# --------------------------------------------------
# 5. Hook files referenced in settings.json exist
# --------------------------------------------------
echo ""
echo "--- Hook file references ---"
if [ -f "$SETTINGS" ]; then
  # Extract command strings from settings.json and check for .sh references
  python3 - "$SETTINGS" "$CLAUDE_DIR" <<'PYEOF'
import json, sys, re
from pathlib import Path

settings_file = sys.argv[1]
claude_dir = sys.argv[2]

with open(settings_file) as f:
    data = json.load(f)

hooks = data.get("hooks", {})
found_scripts = set()

def extract_commands(obj):
    if isinstance(obj, dict):
        cmd = obj.get("command", "")
        if cmd:
            # Find .sh file references
            matches = re.findall(r'\$\{?HOME\}?/\.claude/hooks/(\S+\.sh)', cmd)
            found_scripts.update(matches)
        for v in obj.values():
            extract_commands(v)
    elif isinstance(obj, list):
        for item in obj:
            extract_commands(item)

extract_commands(hooks)

all_pass = True
for script_name in sorted(found_scripts):
    script_path = Path(claude_dir) / "hooks" / script_name
    if script_path.exists():
        print(f"\033[0;32m[PASS]\033[0m settings.json → hooks/{script_name} exists")
    else:
        print(f"\033[0;31m[FAIL]\033[0m settings.json → hooks/{script_name} NOT FOUND")
        all_pass = False

sys.exit(0 if all_pass else 1)
PYEOF
fi

# --------------------------------------------------
# 6. CLAUDE.md size warning
# --------------------------------------------------
echo ""
echo "--- CLAUDE.md ---"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
  LINE_COUNT=$(wc -l < "$CLAUDE_MD")
  if [ "$LINE_COUNT" -gt 200 ]; then
    warn "CLAUDE.md is $LINE_COUNT lines — consider splitting into rules/ files (>200 lines reduces model compliance)"
  else
    pass "CLAUDE.md is $LINE_COUNT lines (within 200-line guideline)"
  fi
else
  warn "CLAUDE.md not found at $CLAUDE_MD"
fi

# --------------------------------------------------
# Summary
# --------------------------------------------------
echo ""
echo "======================================"
echo " Results: ${GREEN}${PASS} passed${RESET}  ${YELLOW}${WARN} warnings${RESET}  ${RED}${FAIL} failed${RESET}"
echo "======================================"

[ "$FAIL" -gt 0 ] && exit 1
exit 0
