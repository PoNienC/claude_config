# `.claude/` — Configuration for Claude Code

> Companion to `CLAUDE.md` at the repo root.
> This folder configures how Claude Code behaves in this project.

## Layout

```
.claude/
├── settings.json           [PROJECT]  Permissions and hook wiring. Commit this.
├── settings.local.json     [LOCAL]    Personal overrides. Gitignored.
├── hooks/                  [MIXED]    Deterministic scripts wired in settings.json
├── skills/                 [PLUGIN]   Reusable workflows (auto-invoked by Claude)
├── agents/                 [PLUGIN]   Subagents with isolated context windows
├── commands/               [PLUGIN]   Slash commands (e.g. /ship, /qa_spatial)
├── rules/                  [PROJECT]  Path-scoped instructions (use globs:)
└── plugins/                [META]     See plugins/README.md for how to share
```

## Reuse model

| Tag | Meaning |
|-----|---------|
| **[GLOBAL]** | Promote to `~/.claude/` to use in every project on your machine. |
| **[PROJECT]** | Stays here. Repo-specific. |
| **[PLUGIN]** | Bundle into a firm-wide plugin. See `plugins/README.md`. |
| **[MIXED]** | Some files are global-friendly, others project-specific. Check the file's tag. |

## Loading order (highest priority wins)
1. Enterprise managed settings
2. CLI `--settings` flag
3. **`.claude/settings.json`** (this repo)
4. `~/.claude/settings.json` (your global)
5. Built-in defaults

Array settings (`permissions.allow`, hook lists) merge across scopes rather than replace. So a global hook stays in effect even when a project adds project-specific ones.

## Quick verification

After dropping these files into a real repo:

```bash
# Check what's loaded
claude
> /context        # shows skills, rules, agents that loaded
> /memory         # shows CLAUDE.md and rules content
> /hooks          # shows wired hooks
```

If a path-scoped rule isn't loading, it's almost certainly the `paths:` vs `globs:` frontmatter bug — these files use the working `globs:` form.

## What to commit

Commit:
- `settings.json` (team-shared permissions, hook wiring)
- All of `hooks/`, `skills/`, `agents/`, `commands/`, `rules/`
- `plugins/README.md`

Do NOT commit:
- `settings.local.json`
- `projects/` (auto-generated session state)
- Anything under `~/.claude/` (that's per-machine)

## First-time setup checklist

1. `chmod +x .claude/hooks/*.sh`
2. Verify `python3` is on PATH (the hooks use it for JSON parsing)
3. Optional: install `black`, `ruff`, `nbstripout` for the post-edit hook to do its job
4. Open Claude Code in this repo and run `/context` to confirm everything loaded
