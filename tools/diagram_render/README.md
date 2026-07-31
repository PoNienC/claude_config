# Diagram render tools (personal, local)

Personal tooling to render the **Prior + Partners company-Claude-system diagrams**
(`operating-model` / `kitchen` / `mcp`) from their source `.html` into the PNGs that get
embedded in Markdown. GitHub doesn't render raw HTML inline, so the diagrams ship as PNGs —
**re-run these after editing any diagram `.html`** to refresh the images.

Kept here (local `~/.claude/`) on purpose: it's personal, not part of the shared OneDrive
project tree.

## Where the diagrams live

The handbook + the four core repos were archived locally and **deleted from GitHub**
(18 Jun 2026), so edit the **local** copies:

- Source HTML: `…/05_Code_Scripts/GitHub/pp_claude_handbook/docs/{operating-model,kitchen,mcp}.html`
- Embedded PNGs: same repos' `docs/img/`
- Clean backup: `…/05_Code_Scripts/PP_Claude_archive_2026-06-18/`

## Prerequisites

Playwright (Python) using **system Chrome** — no browser download:
`pip install playwright` (Chrome already installed).

## The scripts

Run from the `…/GitHub/` working dir (paths are relative to it):

| Script | Purpose | Example |
|---|---|---|
| `_render_diagram.py` | Full-page PNG of a diagram HTML (2× DPI). | `python <dir>/_render_diagram.py pp_claude_handbook/docs/mcp.html out.png` |
| `_stage_png.py` | Just the diagram panel (`.stage`) → the handbook image. | `python <dir>/_stage_png.py pp_claude_handbook/docs/kitchen.html pp_claude_handbook/docs/img/kitchen.png` |
| `_verify_diagram.py` | Renders operating-model in each highlight state to `_preview/`. | `python <dir>/_verify_diagram.py pp_claude_handbook/docs/operating-model.html` |
| `_gen_readme_pngs.py` | Writes the per-repo "you are here" PNG into each repo's `docs/img/`. Hardcoded repo paths — run from `…/GitHub/`. | `python <dir>/_gen_readme_pngs.py` |

`_preview/` holds throwaway intermediate renders — safe to clear anytime.

## Diagram design notes

See the `handbook-diagram-system` memory for the palette and per-repo highlight pattern
(dark aubergine canvas, light boxes, central agent loop, green output arrow, `setView()` toggle).
