# Hand-off review — {{REQUEST_ID}}: {{TITLE}}

- Date: {{DATE}} · branch `{{BRANCH}}`
- Hand-off commit: `{{HANDOFF_COMMIT}}` (request started at `{{START_COMMIT}}`)
- Push: only after every audit below is complete. Fixes come as new
  commits on top; nothing you review is amended or rebased.

## In short

- **Built:** <one line>
- **Tests:** {{TEST_SUMMARY}}
- **Audits:** <n> complete, <n> still running
- **Look at first:** <one line>

## What was built

| Task | Title | Executor | Commit | What it does (one line) |
|---|---|---|---|---|
| T01 | | Claude | | |

## How to try it

1. <the shortest way to see the result: command, notebook, tool, file to open>

## Audits

| Scope | Tasks | Reviewer (model, effort) | Status | Findings B/H/M/L/N | Fix commit |
|---|---|---|---|---|---|
| B1 | T01-T03 | Codex (<model>, medium) | running | | |

Status: running · awaiting your review · fixing · re-check running · complete.

## Your review notes

Send notes in chat; please do not edit repo files until completion (fixes
land here, each one announced). A change you ask for becomes a new task.

| # | Your note | Became task, or "no action" | Status |
|---|---|---|---|

## Changes since the hand-off

<!-- Filled at completion: `git diff <hand-off commit>..HEAD --stat`, then one line per commit since the hand-off (fix commit → findings it fixes; new task → your note). "None" if nothing changed. -->

## Detail

### Files changed

~~~text
<git diff <start commit>..<hand-off commit> --stat>
~~~
