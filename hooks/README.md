# Hooks — `.claude/hooks/`

> **[MIXED]** Some hooks are universally useful (global). Others are project-specific.
> Drop scripts here — but they only fire when registered in `.claude/settings.json` under the `hooks` key.

## How hooks actually work
Hooks are deterministic shell scripts that fire at lifecycle events:
- `SessionStart` — when a Claude Code session opens
- `UserPromptSubmit` — before Claude sees your prompt
- `PreToolUse` — before any tool runs (can block)
- `PostToolUse` — after a tool runs
- `Stop` — when Claude finishes

A script in this folder is dormant until `settings.json` lists it. See `settings.json` in the parent folder for wiring.

## Hooks in this folder

| File | Event | Reusable? |
|------|-------|-----------|
| `session_start_context.sh` | `SessionStart` | **[GLOBAL]** — works in any repo with a `.git` directory |
| `pre_tool_block_secrets.sh` | `PreToolUse` (Write/Edit) | **[GLOBAL]** — blocks obvious secret patterns |
| `post_edit_format.sh` | `PostToolUse` (Write/Edit) | **[GLOBAL for Python]** — runs `black` + `ruff` if installed |

## Sharing across projects
Promote any of these to `~/.claude/hooks/` and reference them with absolute paths in your global `~/.claude/settings.json`. Or bundle them in a plugin (see `../plugins/README.md`).
