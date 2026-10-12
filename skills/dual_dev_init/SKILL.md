---
name: dual_dev_init
description: One-off setup of a repository for the /dual_dev dual-agent (Claude + Codex) workflow — adds the AGENTS.md contract, the .ai/ shared-memory files (including the project's Git conventions) and the CLAUDE.md import line without replacing anything, then smoke-tests Codex. Works on new repos and on projects already run with Claude. Only when the user types /dual_dev_init.
argument-hint: "[repo path — default: current folder]"
disable-model-invocation: true
---

# Set up a repository for /dual_dev

Target: $ARGUMENTS (empty = current folder).

This skill is **additive**: it never deletes, moves or rewrites existing
text. The user's global rules apply (short replies, British English, commit
only on approval, no "claude" in names). **Project rules win** over this
skill's defaults wherever they cover the same thing.

**Skill dir** = the base directory shown when this skill loaded.
The main workflow lives in the sibling folder `<skill dir>\..\dual_dev\`:
- contract template: `..\dual_dev\templates\agents_contract.md`
- Codex launcher: Windows `..\dual_dev\scripts\run_codex.ps1` (PowerShell);
  macOS / Linux `bash ../dual_dev/scripts/run_codex.sh` (Bash; flags
  `--mode --repo --brief --out --effort`)

On macOS, OneDrive lives under `~/Library/CloudStorage/`. Do not set up a
repo there: Windows may already have put a `.git` pointer to `C:/git/...`
in that folder. Clone into `~/Developer/` instead.

## 1. Preflight

1. Resolve the target and its repo root (`git rev-parse --show-toplevel`).
   Not a git repo → ask before `git init`. Inside a OneDrive folder, and
   `.git` is a folder (or there is no repo yet) → explain that OneDrive
   sync can corrupt `.git`, then ask with AskUserQuestion:
   - **Separate git folder (Recommended):** working files stay in
     OneDrive; the history moves to `C:\git\<folder_name>.git` (snake_case;
     stop if it exists). See "OneDrive: separate git folder" below.
   - **Keep `.git` inside OneDrive** (risky).
   - **Abort** and use a clone outside OneDrive.
   If `.git` is already a file pointing outside OneDrive, nothing to do.
2. `codex --version` and `codex login status`. Missing → stop and say:
   `npm install -g @openai/codex`, then `codex login`.
3. Check both sibling files above exist. Missing → stop and report.
4. Working tree must be clean; otherwise ask (commit, stash or abort).
5. Read `CLAUDE.md` and obey any project rule about changing `CLAUDE.md`
   or `AGENTS.md` (for example a required reviewer before merge) — tell the
   user which rule applies.
6. **Other branches touching the same files.** Run `git fetch --prune`,
   then `git log --all --not HEAD --format="%h %cs %D %s" -- AGENTS.md CLAUDE.md`.
   For each branch found, report: name, last date, merged into the main
   branch or not, and what it changes (`git diff --stat <main>...<branch>`).
   If any unmerged branch changes `AGENTS.md`, **stop before writing** and
   ask the user: fold its content in, supersede it, or abort.

### OneDrive: separate git folder (tested 7 October 2026)

1. OneDrive pause:
   - **Existing repo (moving a `.git` folder out):** required. Ask the user
     to pause OneDrive sync (taskbar icon → Pause syncing → 2 hours) and
     confirm no other git process is using the repo; wait for the answer.
   - **New repo (no `.git` yet):** optional. Say in one line that pausing
     avoids OneDrive locking a file during the first `git add` (that file
     would just need a retry), then carry on without waiting. If a
     `git add` hits a locked file, retry it once; if it fails again, ask
     the user to pause OneDrive.
   Other Claude sessions editing files is fine — they do not use git.
2. Before any first commit in a new repo: list the top-level folders with
   their sizes and propose `.gitignore` lines for data and outputs — ask.
3. Run `git init --separate-git-dir=C:\git\<name>.git` in the folder. For
   an existing repo this moves `.git` there and leaves a one-line pointer
   file (`gitdir: C:/git/<name>.git`); for a new repo it creates both.
4. `attrib -H C:\git\<name>.git` (a moved `.git` keeps its hidden flag).
5. Verify: `git rev-parse --absolute-git-dir` prints `C:/git/<name>.git`;
   `git log --oneline -1` and `git status` work.
6. If OneDrive was paused, tell the user to resume it. Recommend "Always keep on this
   device" only for small folders — pinning a large data folder
   downloads all of it; ask first.
7. Record in `.ai/PROJECT.md` → "Git conventions": git folder
   `C:\git\<name>.git`; history exists on this PC, in the nightly backup
   (`mirror\git_repos`) and on GitHub only if pushed; other machines clone
   from GitHub; never edit the `.git` pointer file (OneDrive would sync
   the change back and break this PC's repo).

Codex reads a separated repo normally (log, status, diff all tested).

## 2. Detect existing setup

If `AGENTS.md` already contains "Dual-agent development contract" and
`.ai/` exists: report what is present, offer to add only missing pieces
(for example a missing "Git conventions" section), and stop there unless
the user agrees.

## 3. Read the project (context only)

`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `README*`, build files
(`pyproject.toml`, `package.json`, …), the test layout, `.gitignore`,
`docs/` index, `git log --oneline -15`, and the root `HANDOVER.md` if
present. The root `HANDOVER.md` is the user's **personal** note: use it
only for project facts and never copy personal remarks into committed files.

**Git conventions** — extract, with the source path and section for each:
- branch naming pattern (e.g. `feat/<module>-<short-description>`);
- commit format (e.g. Conventional Commits);
- push cadence (e.g. "push at session end", or none stated);
- pull request and merge rules, required reviewers;
- the main branch name;
- the GitHub account: owner from `git remote get-url origin`, and whether
  the active GitHub CLI account can see it (`gh repo view <owner>/<repo>`);
  if not, which logged-in account can (`gh auth status`).

Derive the `/dual_dev` patterns: request branch = the project pattern with
`T001_slug` as the description (slug in underscores, the project's own
separators kept, e.g. `feat/<module>-T001_slug`); commit subject = the
project format with the task ID (e.g. `feat(<module>): <title> [T01]`).
No project rule → defaults `dual_dev/T001_slug`, `T01 <title>`, no push
without approval.

## 4. Create a setup branch

Tell the user the current branch. Name the setup branch by the project's
pattern if it has one (e.g. `feat/tooling-dual_dev_setup`), else
`dual_dev_setup`; add `_2`, `_3`, … if the name exists. `git switch -c <name>`.

## 5. Write or merge files

| File | If absent | If present |
|---|---|---|
| `AGENTS.md` | copy the contract template | append the contract as a new section at the end; keep existing text untouched |
| `CLAUDE.md` | create: one-line title, then `@AGENTS.md` | if no `@AGENTS.md` line, append `## Dual-agent workflow`, blank line, `@AGENTS.md` |
| `.ai/PROJECT.md` | seed (below) | append the "Git conventions" section only if missing |
| `.ai/STATE.md` | seed (below) | leave alone |
| `.ai/DECISIONS.md` | seed (below) | leave alone |
| `.ai/tasks/.gitkeep` | create | — |

Seeds — facts only, cite source paths, write `TBC` for unknowns:
- **PROJECT.md**: purpose; stack and versions; top-level layout; setup
  steps; exact test and lint commands; coding conventions (from
  `CLAUDE.md`); key documents; and a section **"Git conventions (used by
  /dual_dev)"** with: request branch pattern, commit format, push policy,
  pull request rules and required reviewers, main branch, GitHub account
  for this remote — each with its source.
- **STATE.md**: date (DD Month YYYY); current branch and last commit;
  work in flight (including the other branches found in step 1.6); known
  issues; at the end, a "Sources" list including which facts came from the
  root `HANDOVER.md` so the user can check them.
- **DECISIONS.md**: title, format line (date · decision · context ·
  alternatives · consequences), then any existing decisions found in the
  docs with their paths — or none.

`.gitignore`:
- add `.ai/tasks/*/codex/*.log` (Codex run logs are large);
- confirm `.ai/` is not ignored and task handovers are not caught by a
  `HANDOVER*` pattern: `git check-ignore -v .ai/tasks/T000_probe/TASK_HANDOVER.md`
  must print nothing;
- if a root `HANDOVER.md` exists and is not ignored, propose adding
  `/HANDOVER.md` — ask first.

## 6. Codex smoke test (about two minutes, effort low)

Write a probe brief to the session scratchpad:

> Read-only probe. 1) Read `AGENTS.md` and `.ai/PROJECT.md`; report the
> test command and up to three statements in PROJECT.md that look wrong
> or missing, with evidence. 2) Try to create `codex_sandbox_probe.txt` in
> the repo root and report whether it was blocked, quoting the error.
> Under 120 words.

Run the launcher:
- Windows: `& "<skill dir>\..\dual_dev\scripts\run_codex.ps1" -Mode plan -Repo "<repo root>" -BriefFile "<scratchpad>\init_probe_brief.md" -OutFile "<scratchpad>\init_probe_out.md" -Effort low`
- macOS / Linux: `bash "<skill dir>/../dual_dev/scripts/run_codex.sh" --mode plan --repo "<repo root>" --brief "<scratchpad>/init_probe_brief.md" --out "<scratchpad>/init_probe_out.md" --effort low`

Pass = exit 0, commands ran, and the write was blocked. Fix any real
`PROJECT.md` errors Codex found. A fail means `/dual_dev` will not work
yet — report the log path.

**Write probe** (about one minute): `git init` a throwaway folder in the
scratchpad, then run the launcher in `execute` mode, effort low, with the
brief "Create hello.txt containing the word ok, then print it." Pass =
exit 0 and `hello.txt` exists. Record in `.ai/PROJECT.md` → "Git
conventions": `Codex execution on <machine>: available | not available
(<date>)`. `/dual_dev` offers Codex-executed tasks at Gate 2 only when it
says available for the current machine.

## 7. Hand back

1. Show `git status` and `git diff --stat`. List every file written as a
   clickable link, plus **one** code block with all absolute paths.
2. Ask: commit to the local setup branch? (No push.) Subject in the
   project's commit format — e.g. `chore: set up dual-agent workflow
   (AGENTS.md contract, .ai shared state)` for Conventional Commits, else
   `Set up dual-agent workflow (AGENTS.md contract, .ai shared state)`.
3. Next steps for the user, either:
   - merge the setup branch through the project's normal flow (required
     reviewers first; for a pull request, use the GitHub account found in
     step 3 — switch with `gh auth switch -u <account>` only after telling
     the user, then switch back); or
   - `/dual_dev` can be started from the project root or any folder up to
     three levels above the repo; it finds the repo and asks to confirm
     (or pass `--repo <path>`);
   - for a pilot, run `/dual_dev <request>` straight from the setup branch:
     the request branch stacks on it, and its pull request will include
     the setup commit unless setup merges first.
