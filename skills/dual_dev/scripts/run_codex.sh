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
    echo "usage: run_codex.sh --mode plan|audit|execute --repo DIR --brief FILE --out FILE [--effort low|medium|high|xhigh] [--model NAME] [--diff-range BASE..END|HEAD] [--max-diff-chars N]" >&2
    exit 64
}

# --model empty = the model set in Codex's own config.toml (shared with the Codex app).
# --diff-range (audits): paste that range's commits and diff into the brief, so
# Codex reviews it directly instead of exploring the repo first.
mode=""; repo=""; brief=""; out=""; effort="high"; model=""; diff_range=""; max_diff_chars=150000
while [ $# -gt 0 ]; do
    case "$1" in
        --mode)   [ $# -ge 2 ] || usage; mode="$2";   shift 2 ;;
        --repo)   [ $# -ge 2 ] || usage; repo="$2";   shift 2 ;;
        --brief)  [ $# -ge 2 ] || usage; brief="$2";  shift 2 ;;
        --out)    [ $# -ge 2 ] || usage; out="$2";    shift 2 ;;
        --effort) [ $# -ge 2 ] || usage; effort="$2"; shift 2 ;;
        --model)  [ $# -ge 2 ] || usage; model="$2";  shift 2 ;;
        --diff-range)     [ $# -ge 2 ] || usage; diff_range="$2";     shift 2 ;;
        --max-diff-chars) [ $# -ge 2 ] || usage; max_diff_chars="$2"; shift 2 ;;
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

if [ -n "$diff_range" ] && ! printf '%s' "$diff_range" | grep -Eq '^[A-Za-z0-9._/~^-]+(\.\.[A-Za-z0-9._/~^-]+)?$'; then
    echo "Bad diff range: $diff_range" >&2; exit 64
fi
case "$max_diff_chars" in ''|*[!0-9]*) usage ;; esac

log="$out.log"
mkdir -p "$(dirname "$out")"
rm -f "$out"

# An audit brief must carry the acceptance criteria and handover as committed
# (pasted by the coordinator); an unfilled placeholder means it does not.
# (A placeholder standing alone on its line; the pasted text may quote them inline.)
if [ "$mode" = "audit" ] && grep -Eq '^\{\{(CRITERIA|HANDOVER)\}\}[[:space:]]*$' "$brief"; then
    echo "Audit brief still has an unfilled {{CRITERIA}} or {{HANDOVER}} placeholder: $brief" >&2; exit 64
fi
# Pin a committed range to hashes, so the pasted header says exactly what was
# reviewed even if HEAD moves later.
if [ -n "$diff_range" ] && [ "$diff_range" != "HEAD" ]; then
    base_ref=${diff_range%%..*}; end_ref=${diff_range##*..}
    base_hash=$(git -C "$repo" rev-parse --short "$base_ref" 2>/dev/null)
    end_hash=$(git -C "$repo" rev-parse --short "$end_ref" 2>/dev/null)
    [ -n "$base_hash" ] && [ -n "$end_hash" ] && diff_range="$base_hash..$end_hash"
fi

# The text sent to Codex: the brief, plus the pasted changes for audits.
send=$(mktemp "${TMPDIR:-/tmp}/run_codex_brief.XXXXXX")
trap 'rm -f "$send"' EXIT
cat "$brief" > "$send"
if [ -n "$diff_range" ]; then
    # The .ai/ records (plans, task matrix, audit log) are context, not code:
    # leave them out so they never crowd the code out of the paste limit.
    if [ "$diff_range" = "HEAD" ]; then
        commits="(uncommitted changes)"
        stat=$(git -C "$repo" -c core.quotepath=off diff --stat HEAD -- . ':(exclude).ai')
        untracked=$(git -C "$repo" -c core.quotepath=off ls-files --others --exclude-standard -- . ':(exclude).ai')
        [ -n "$untracked" ] && stat=$(printf '%s\n\nUntracked files (open them directly):\n%s' "$stat" "$untracked")
        git -C "$repo" -c core.quotepath=off diff HEAD -- . ':(exclude).ai' > "$send.diff"
    else
        commits=$(git -C "$repo" -c core.quotepath=off log --oneline "$diff_range")
        stat=$(git -C "$repo" -c core.quotepath=off diff --stat "$diff_range" -- . ':(exclude).ai')
        git -C "$repo" -c core.quotepath=off diff "$diff_range" -- . ':(exclude).ai' > "$send.diff"
    fi
    note=""
    if [ "$(wc -c < "$send.diff")" -gt "$max_diff_chars" ]; then
        note="**Diff truncated at $max_diff_chars characters.** For files beyond this point, run \`git diff $diff_range -- <file>\`."
    fi
    {
        printf '\n\n## Changes under review — pasted by the launcher\n\n'
        printf 'Range: `%s` (changes under `.ai/` left out — they are records, not\n' "$diff_range"
        printf 'code). Review the diff below directly; run git or open files only when you\n'
        printf 'need more context, and read files as they are at the end of the range\n'
        printf '(`git show <end>:<path>`), not from the working tree, which may already\n'
        printf 'hold later work.\n\n### Commits\n\n~~~~text\n%s\n~~~~\n\n### Files\n\n~~~~text\n%s\n~~~~\n\n### Diff\n\n~~~~diff\n' "$commits" "$stat"
        head -c "$max_diff_chars" "$send.diff"
        printf '\n~~~~\n'
        [ -n "$note" ] && printf '\n%s\n' "$note"
    } >> "$send"
    rm -f "$send.diff"
fi

started=$(date +%s)
if [ -n "$model" ]; then
    codex exec --sandbox "$sandbox" -C "$repo" --model "$model" -c "model_reasoning_effort=\"$effort\"" -o "$out" - < "$send" > "$log" 2>&1
else
    codex exec --sandbox "$sandbox" -C "$repo" -c "model_reasoning_effort=\"$effort\"" -o "$out" - < "$send" > "$log" 2>&1
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
# A marker that already appears in the brief (e.g. when this launcher is itself
# under review) is echoed in the log and the reply, so it is ignored.
pattern=""
for m in sandbox_apply CreateProcessAsUserW UnsupportedOperation 'refusing to run unsandboxed'; do
    grep -Fq "$m" "$send" 2>/dev/null && continue
    pattern="${pattern:+$pattern|}$m"
done
# Degraded means the sandbox blocked Codex's commands, so judge by behaviour, not
# by wording: markers count only when Codex ran commands and every one of them
# failed (marker lines >= commands run). Codex echoing the launchers' own
# comments while it reads them leaves most commands successful.
marker_lines=0; commands_run=0
if [ -n "$pattern" ]; then
    marker_lines=$(cat "$out" "$log" 2>/dev/null | grep -Ec "$pattern")
    commands_run=$(tr -d '\r' < "$log" | grep -cx 'exec')
fi
if [ "$marker_lines" -gt 0 ] && [ "$commands_run" -gt 0 ] && [ "$marker_lines" -ge "$commands_run" ]; then
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
