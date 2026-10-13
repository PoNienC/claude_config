"""Context guard: ask Claude for a handover before the context window fills.

Not spatial. Data layer: Claude Code hook (PostToolUse and UserPromptSubmit).
Written 13 October 2026.

Hooks are not told how full the context is, so this reads the session
transcript named in the hook input and takes the context size of the latest
assistant reply (input + cache-read + cache-creation tokens, the same sum the
status line uses), divided by the model's context window.

  threshold (90%)  Claude is told to stop at the next safe point, run the
                   session_handover skill (live HANDOVER.md + a ready-to-paste
                   prompt for a new session) and wait. The user sees a notice.
  final (95%)      If no HANDOVER.md has been written since the 90% notice,
                   Claude is halted (PostToolUse "continue": false) and the user
                   is told to type /session_handover. If one has been written,
                   Claude only gets a short reminder, so a handover in progress
                   is never cut off.

Each level fires once per session; a compaction that drops usage below 80%
resets them. A user prompt is never blocked. Any error, a missing transcript or
an unreadable file means "do nothing" and exit 0 - a failing hook can block
prompts (see references/quick_diagnosis_20260704.md, Break 1).

Optional settings in context_guard.json next to this file:
  {"threshold": 0.90, "final": 0.95, "reset_below": 0.80,
   "final_action": "halt" | "remind",
   "windows": {"claude-opus-5": 1000000, "default": 200000}}
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULTS: dict = {
    "threshold": 0.90,
    "final": 0.95,
    "reset_below": 0.80,
    "final_action": "halt",
    # Context window by model-id prefix (longest prefix wins). Claude 5-family
    # models have 1M tokens by default; Haiku 4.5 and older models 200k. Any
    # id containing "[1m]" is always 1,000,000.
    "windows": {
        "claude-opus-5": 1_000_000,
        "claude-sonnet-5": 1_000_000,
        "claude-fable-5": 1_000_000,
        "claude-haiku-5": 1_000_000,
        "default": 200_000,
    },
}
TAIL_BYTES = 2_000_000


def load_settings() -> dict:
    settings = dict(DEFAULTS)
    path = HERE / "context_guard.json"
    if path.is_file():
        try:
            user = json.loads(path.read_text(encoding="utf-8-sig"))
            settings.update({k: v for k, v in user.items() if k != "windows"})
            settings["windows"] = {**DEFAULTS["windows"], **user.get("windows", {})}
        except (OSError, ValueError):
            pass
    return settings


def last_usage(transcript: Path) -> tuple[int, str] | None:
    """Context tokens and model id of the latest assistant reply, or None."""
    with transcript.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - TAIL_BYTES))
        tail = fh.read().decode("utf-8", errors="replace")
    for line in reversed(tail.splitlines()):
        if '"usage"' not in line or '"assistant"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        if rec.get("type") != "assistant" or not usage:
            continue
        tokens = (int(usage.get("input_tokens") or 0)
                  + int(usage.get("cache_read_input_tokens") or 0)
                  + int(usage.get("cache_creation_input_tokens") or 0))
        return tokens, str(msg.get("model") or "")
    return None


def window_for(model: str, windows: dict) -> int:
    if "[1m]" in model:
        return 1_000_000
    best = ""
    for prefix in windows:
        if prefix != "default" and model.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return int(windows[best] if best else windows["default"])


def state_path(session_id: str) -> Path:
    folder = Path(tempfile.gettempdir()) / "context_guard"
    folder.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "unknown"
    return folder / f"{safe}.json"


def handover_written_since(cwd: str, since: float) -> bool:
    """True if a live HANDOVER.md near the session folder changed after `since`."""
    candidates: list[Path] = []
    if cwd:
        here = Path(cwd)
        candidates += [p / "HANDOVER.md" for p in [here, *list(here.parents)[:3]]]
    for home in (Path.home() / ".claude" / "handovers", Path.home() / ".claude-work" / "handovers"):
        if home.is_dir():
            candidates += list(home.glob("*/HANDOVER.md"))
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_mtime >= since:
                return True
        except OSError:
            continue
    return False


def main() -> int:
    data = json.loads(sys.stdin.read() or "{}")
    event = data.get("hook_event_name", "")
    transcript = Path(data.get("transcript_path") or "")
    if event not in ("PostToolUse", "UserPromptSubmit") or not transcript.is_file():
        return 0
    found = last_usage(transcript)
    if not found:
        return 0
    used, model = found
    settings = load_settings()
    window = window_for(model, settings["windows"])
    ratio = used / window if window else 0.0

    sp = state_path(str(data.get("session_id", "")))
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {}
    if ratio < float(settings["reset_below"]):
        if state:
            sp.unlink(missing_ok=True)
        return 0
    if ratio >= float(settings["final"]):
        level = "final"
    elif ratio >= float(settings["threshold"]):
        level = "threshold"
    else:
        return 0
    if state.get(level):
        return 0
    state[level] = time.time()
    state.setdefault("threshold", state[level])
    sp.write_text(json.dumps(state), encoding="utf-8")

    pct = int(ratio * 100)
    head = f"CONTEXT GUARD: this session's context is {pct}% full ({used:,} of {window:,} tokens, {model})."
    if level == "threshold":
        text = (head + " Pause at the next safe point: finish only the step in hand (no half-written "
                "file or half-applied edit), start nothing new, then run the session_handover skill: "
                "write the live HANDOVER.md and give the user a ready-to-paste prompt for a new "
                "session. Then stop and wait for the user.")
        notice = f"Context {pct}% full - Claude will hand over at the next safe point."
        out = {"systemMessage": notice,
               "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
        print(json.dumps(out))
        return 0

    handover_done = handover_written_since(str(data.get("cwd") or ""), float(state["threshold"]))
    if event == "PostToolUse" and settings.get("final_action") == "halt" and not handover_done:
        out = {"continue": False,
               "systemMessage": f"Context {pct}% full - Claude stopped before writing a handover.",
               "stopReason": (f"Context {pct}% full and no handover yet. Type /session_handover to "
                              "write HANDOVER.md and get the prompt for a new session.")}
        print(json.dumps(out))
        return 0
    text = (head + " Do not start any new work in this session. If the handover is not finished, "
            "finish it now (session_handover skill); otherwise tell the user to continue in a new "
            "session with the prompt already given.")
    out = {"systemMessage": f"Context {pct}% full - finish the handover and move to a new session.",
           "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a guard must never break the session; any failure = no-op
        sys.exit(0)
