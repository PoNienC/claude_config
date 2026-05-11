# GeoAI-Architect Overlay for `claude_config`

This overlay drops onto your `PoNienC/claude_config` repository, adding:

- A spatial-discipline section to append to your `CLAUDE.md` (or, if you
  have no `CLAUDE.md` at repo root, this file becomes it).
- Two domain Skills: `urban_plan_evaluator`, `accessibility_equity_auditor`.
- One namespaced subagent: `geoai_critic`.
- Two slash commands: `/audit_urban_plan`, `/audit_accessibility`.
- One cross-platform Python Hook: `pre_tool_geoai_validate_crs.py`.
- One path-scoped rule: `geoai_spatial_discipline.md`.
- A complete MCP server at `mcp_servers/geoai_mcp/` with three working
  tools (`geoai_get_crs_info`, `geoai_calculate_isochrone`,
  `geoai_stac_search`) and a safety module.

Nothing in this overlay conflicts with the files currently in your repo.
Everything new is either in a new top-level directory (`mcp_servers/`),
or namespaced with `geoai_` prefix to coexist with anything you already
have.

---

## Naming compliance with your conventions

All names use underscores — no dashes. Verified against your
`sync_guide.md` section 3 rule.

## Extraction

From your local clone of `claude_config`:

```bash
# macOS
cd ~/.claude
tar -xzf /path/to/claude_config_geoai_overlay.tar.gz --strip-components=1
```

```powershell
# Windows PowerShell
cd $HOME\.claude
tar -xzf C:\path\to\claude_config_geoai_overlay.tar.gz --strip-components=1
```

`--strip-components=1` discards the top-level `claude_config_geoai_overlay/`
wrapper directory so files land directly into your repo's existing
`agents/`, `commands/`, `hooks/`, etc.

After extraction, run `git status` from GitHub Desktop. You should see
the new files in the **Changes** tab. None of your existing files will
appear modified.

## Settings.json patch

Two ways to apply:

**Path A — via your `update_config` skill (recommended).** Open Claude
Code and paste:

> Use update_config to add the three top-level blocks from
> `settings_patch.json` (in the overlay root) to my settings.json:
> `mcpServers`, `hooks`, `permissions`. Preserve the existing
> `extraKnownMarketplaces` entry exactly. Do not change anything else.

**Path B — manual JSON merge.** Open `settings.json` and add the three
top-level keys from `settings_patch.json` as siblings of
`extraKnownMarketplaces`. The end state is shown in
`settings_after_merge.json` as a reference.

## Per-machine Python setup

The MCP server requires Python with pyproj and the MCP SDK. Each machine
needs this done once:

```bash
# macOS
cd ~/.claude/mcp_servers/geoai_mcp
python3 -m pip install --user -r requirements.txt
```

```powershell
# Windows PowerShell
cd $HOME\.claude\mcp_servers\geoai_mcp
python -m pip install --user -r requirements.txt
```

This installs to the user site-packages. The MCP server in
`settings.json` invokes plain `python3` (Mac) or `python` (Windows) —
no virtual-environment activation required. If you later want
isolation, see `mcp_servers/geoai_mcp/README.md` for the venv pattern.

## Verify

After extraction and pip install:

1. **Quit and relaunch Claude Code.**
2. In a new session, run `/context`, `/hooks`, `/mcp`. You should see:
   - Skills: `urban_plan_evaluator`, `accessibility_equity_auditor`.
   - Subagents: `geoai_critic`.
   - Hooks: a `PreToolUse` matcher on `mcp__geoai__.*`.
   - MCP servers: `geoai` listed with 3 tools.
3. Test the round-trip:
   > Use the geoai MCP server to tell me about EPSG:27700.

   A correct response describes British National Grid in metres with the
   area-of-use bbox. That confirms the entire stack.

## Commit + push from GitHub Desktop

Per your `sync_guide.md` section 2. Recommended commit message:

> Add geoai_mcp overlay — MCP server, 2 skills, 1 critic, 1 hook, 1 rule, 2 commands

After pushing, on the other machine: pull → run `pip install` step → restart
Claude Code. The sync model is your existing one; the overlay adds
nothing new to the workflow except the Python install on first sync.

## What this overlay deliberately does NOT do

- Does not modify your existing `settings.json` directly. You apply the
  patch yourself with the safety net of `update_config`.
- Does not commit a Python venv. Each machine creates its own if you
  choose isolation later.
- Does not commit `references/sensitive_zones.geojson`. That file is
  gitignored per the safety doctrine. If you populate it, it stays
  per-machine.
- Does not assume any existing `CLAUDE.md`. The constitution content
  ships as `CLAUDE_geoai_section.md` — you append it to your existing
  `CLAUDE.md` or rename it if you have none at the repo root.

## File inventory

```
overlay-root/
├── INTEGRATION_README.md                          (this file)
├── CLAUDE_geoai_section.md                        (append-or-rename)
├── settings_patch.json                            (JSON to add)
├── settings_after_merge.json                      (reference of end state)
│
├── agents/
│   └── geoai_critic.md                            [GLOBAL]
├── commands/
│   ├── audit_urban_plan.md                        [GLOBAL]
│   └── audit_accessibility.md                     [GLOBAL]
├── hooks/
│   └── pre_tool_geoai_validate_crs.py             [GLOBAL] cross-platform
├── rules/
│   └── geoai_spatial_discipline.md                [PROJECT]
├── skills/
│   ├── urban_plan_evaluator/SKILL.md              [PLUGIN]
│   └── accessibility_equity_auditor/SKILL.md      [PLUGIN]
└── mcp_servers/
    └── geoai_mcp/                                 [MIXED]
        ├── README.md
        ├── requirements.txt
        ├── .gitignore
        ├── __init__.py
        ├── server.py
        ├── tools/
        │   ├── __init__.py
        │   ├── crs_info.py
        │   ├── isochrone.py
        │   └── stac_search.py
        ├── safety/
        │   ├── __init__.py
        │   └── sensitive_zones.py
        └── references/
            └── epsg_quickref.md
```

Tags follow your existing `[GLOBAL]` / `[PROJECT]` / `[PLUGIN]` / `[MIXED]`
convention from your repo's main `README.md`.
