---
name: codex_usage
description: Show Codex usage — plan limits (weekly / 5-hour % used and reset time, limit-reset credits) and Codex token totals for today and the last 7 days by project folder. Use when the user types /codex_usage or asks how much Codex they have used or have left, about Codex limits, quota or tokens.
---

# Codex usage report

Read-only. Uses none of the Codex quota.

**Skill dir** = the base directory shown when this skill loaded.

1. Run the report:
   - Windows (PowerShell tool): `node "<skill dir>\scripts\codex_usage.mjs"`
   - macOS / Linux (Bash tool): `node "<skill dir>/scripts/codex_usage.mjs"`
2. Reply in the user's style: first line = weekly (and 5-hour, if any)
   limit % used and when it resets. Then short bullets: plan, reset
   credits, tokens today and last 7 days (note how much was cached input),
   the top projects with full paths, and the dashboard link
   <https://chatgpt.com/codex/settings/usage>.
3. Above 80% of any limit: say so plainly and suggest lower Codex effort
   (`medium` or `low`) for `/dual_dev`, or spending a limit-reset credit
   if one is available — the user decides.
4. "Plan limits: unavailable" → Codex is not signed in or not installed:
   suggest `codex login status`.

Notes:
- Token totals come from Codex's own session files
  (`~/.codex/sessions`), so they cover every Codex use on this machine —
  `/dual_dev`, the Codex app and the VS Code extension. A session counts
  on the day it was last active.
- Limits are reported by OpenAI as % used, not tokens; the dashboard is
  the source of truth if numbers disagree.
- `--brief` gives one line (used by the `/dual_dev` launchers); `--json`
  gives everything for scripting.
