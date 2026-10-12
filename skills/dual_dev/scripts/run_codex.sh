#!/usr/bin/env bash
# Run one fresh Codex CLI job for the dual_dev workflow (plan, audit or execute).
#
# macOS / Linux twin of run_codex.ps1 (written 7 October 2026). Every call:
#   - starts a fresh Codex thread (no carried-over context);
#   - uses a fixed sandbox per mode: plan/audit = read-only, execute = workspace-write;
#   - reads its brief from a UTF-8 file through stdin (no quoting problems);
#   - writes Codex's final message to --out and the full run log to --out.log.
#
# Exit codes: 0 = OK, 1 = failed, 2 = degraded (Codex could not run commands
# inside its sandbox - do not trust the output), 64 = bad arguments.
# Works with the macOS system bash 3.2 (no bash 4 features).
#
# Example:
#   bash run_codex.sh --mode plan --repo ~/Developer/geoai-core \
#     --brief ~/Developer/geoai-core/.ai/tasks/T001_x/codex/plan_brief.md \
#     --out   ~/Developer/geoai-core/.ai/tasks/T001_x/codex/plan_out.md

set -u

usage() {
    echo "usage: run_codex.sh --mode plan|audit|execute --repo DIR --brief FILE --out FILE [--effort low|medium|high|xhigh] [--model NAME]" >&2
    exit 64
}

# --model empty = the model set in Codex's own config.toml (shared with the Codex app).
mode=""; repo=""; brief=""; out=""; effort="high"; model=""
while [ $# -gt 0 ]; do
    case "$1" in
        --mode)   [ $# -ge 2 ] || usage; mode="$2";   shift 2 ;;
        --repo)   [ $# -ge 2 ] || usage; repo="$2";   shift 2 ;;
        --brief)  [ $# -ge 2 ] || usage; brief="$2";  shift 2 ;;
        --out)    [ $# -ge 2 ] || usage; out="$2";    shift 2 ;;
        --effort) [ $# -ge 2 ] || usage; effort="$2"; shift 2 ;;
        --model)  [ $# -ge 2 ] || usage; model="$2";  shift 2 ;;
        *) usage ;;
    esac
done

case "$mode" in
    plan|audit) sandbox="read-only" ;;
    execute)    sandbox="workspace-write" ;;
    *) usage ;;
esac
case "$effort" in low|medium|high|xhigh) ;; *) usage ;; esac
if [ -n "$model" ] && ! printf '%s' "$model" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._:-]*$'; then
    echo "Bad model name: $model" >&2; exit 64
fi
if [ -n "$model" ]; then
    model_label="$model"
else
    # Report the config default; Codex itself reads it, nothing is passed.
    cfg="${CODEX_HOME:-$HOME/.codex}/config.toml"
    default_model=$(sed -n 's/^[[:space:]]*model[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$cfg" 2>/dev/null | head -n 1)
    model_label="default(${default_model:-unknown})"
fi
[ -n "$out" ] || usage
[ -d "$repo" ]  || { echo "Not found: $repo" >&2; exit 64; }
[ -f "$brief" ] || { echo "Not found: $brief" >&2; exit 64; }

if ! command -v codex >/dev/null 2>&1; then
    echo "codex CLI not found on PATH. Install it with: npm install -g @openai/codex" >&2
    exit 1
fi

log="$out.log"
mkdir -p "$(dirname "$out")"
rm -f "$out"

started=$(date +%s)
if [ -n "$model" ]; then
    codex exec --sandbox "$sandbox" -C "$repo" --model "$model" -c "model_reasoning_effort=\"$effort\"" -o "$out" - < "$brief" > "$log" 2>&1
else
    codex exec --sandbox "$sandbox" -C "$repo" -c "model_reasoning_effort=\"$effort\"" -o "$out" - < "$brief" > "$log" 2>&1
fi
exit_code=$?
secs=$(( $(date +%s) - started ))

# Usage line (printed on every outcome): tokens for this call from the log,
# plus plan limits from the sibling codex_usage skill (read-only, ~1.5 s).
# Codex prints "tokens used" then the number on stderr; the final reply (stdout)
# can land between them, so take the last number-only line after the marker.
tokens=$(tr -d '\r' < "$log" 2>/dev/null | awk '/^tokens used$/ { f = 1; n = ""; next } f && /^ *[0-9,]+ *$/ { n = $1 } END { print n }')
[ -n "$tokens" ] || tokens="unknown"
script_dir=$(cd "$(dirname "$0")" && pwd)
usage_script="$script_dir/../../codex_usage/scripts/codex_usage.mjs"
if [ -f "$usage_script" ] && command -v node >/dev/null 2>&1; then
    limits=$(node "$usage_script" --brief 2>/dev/null | head -n 1)
else
    limits="plan limits not checked (codex_usage skill or node missing)"
fi
usage_line="CODEX USAGE: tokens this call $tokens; $limits"

if [ "$exit_code" -ne 0 ] || [ ! -f "$out" ]; then
    echo "CODEX FAILED: mode=$mode exit=$exit_code after ${secs}s"
    echo "$usage_line"
    echo "Log: $log"
    [ -f "$log" ] && tail -n 20 "$log"
    exit 1
fi

# Sandbox failures that make the output untrustworthy:
#   sandbox_apply            - macOS: Codex's Seatbelt sandbox could not start
#                              (usually because the caller is itself sandboxed)
#   CreateProcessAsUserW,
#   UnsupportedOperation,
#   refusing to run unsandboxed - Windows (see run_codex.ps1)
if grep -Eq 'sandbox_apply|CreateProcessAsUserW|UnsupportedOperation|refusing to run unsandboxed' "$out" "$log"; then
    echo "CODEX DEGRADED: Codex could not run shell commands (sandbox). Treat the output as untrustworthy."
    echo "$usage_line"
    echo "Output: $out"
    echo "Log: $log"
    exit 2
fi

echo "CODEX OK: mode=$mode sandbox=$sandbox model=$model_label effort=$effort time=${secs}s"
echo "$usage_line"
echo "Output: $out"
echo "Log: $log"
