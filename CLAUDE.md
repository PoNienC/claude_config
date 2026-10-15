# Global operating rules — router edition

> Restructured 4 July 2026 (Po-approved). Full previous text preserved at
> `~/.claude/backup_20260704/CLAUDE.md`. This file stays ≤150 lines and
> holds only (1) universal always-on rules and (2) the routing table.
> Long-form doctrine lives in `~/.claude/references/` and loads ONLY via
> an explicit Read — never add big content here, and never use @imports
> (they load eagerly at launch).

## Routing table — Read the file BEFORE starting the matching work

| When the task involves… | Read first |
|---|---|
| Spawning subagents, model/effort choice, escalation | `~/.claude/references/model_dispatch.md` |
| Unsure: escalate? done? ask user? change approach? | `~/.claude/references/judgment_rubrics.md` |
| Writing a task brief for any agent | `~/.claude/references/task_templates.md` |
| Editing config/memory/rules; end-of-session upkeep | `~/.claude/references/maintenance_protocol.md` |
| Importing/ingesting ANY external dataset to ANY store | `~/.claude/references/source_fidelity_ingestion.md` (MANDATORY before destination writes) |
| Heavy spatial ops (>100k geoms, >5 min, big overlays) | `~/.claude/references/performance_discipline.md` |
| Geospatial work (CRS, imagery, routing, analysis) | `~/.claude/references/geoai_operating.md` |
| ANY SQL/PostGIS work — incl. psql via shell | `~/.claude/rules/sql.md` (paths-gated; Read it explicitly) |
| GPKG → PostGIS loads | `~/.claude/rules/gpkg_to_postgis.md` |
| Creating ANY document/deck/deliverable for P+P | `~/.claude/references/prior_partners_brand.md` |
| Writing a tool brief / tool architecture doc / QA-QC report (PNC dark annex HTML) | `~/.claude/references/pnc_documentation_styles.md` |
| Producing a diagram-led HTML workflow / PL / process report | invoke skill `pp_workflow_report` (bundled template) |
| Dual-agent Claude + Codex development (plan / execute / audit) | user types `/dual_dev_init` once per repo, then `/dual_dev <request>`; skills in `~/.claude/skills/dual_dev*`; all Codex calls via its `scripts/run_codex.ps1` (Windows) or `scripts/run_codex.sh` (macOS) |
| Diagnosing token waste, session slowness, or Claude not responding / prompts blocked | `~/.claude/references/quick_diagnosis_20260704.md` |
| Continuing the long-term system build | `~/.claude/references/letter_to_future_sessions.md` |

## Universal rules (always on)

### Reply style (Po-approved update, 24 Aug 2026)
- Open EVERY reply with a one-line summary of the result — the outcome,
  not a restatement of the request. One line, before anything else.
- SUPER CONCISE, bullets only, EASY ENGLISH: plain words, short
  sentences, straight to the point. Use prose only where a bullet
  genuinely cannot carry the point. Never pad.
- Applies to every reply in every session, including mid-task progress
  updates and error reports.
- HARD CAP (Po, 26 August 2026): max 12 bullets and about 150 words per reply.
  No headings, no evidence dumps, no log/code quotes, no "why it happens"
  section, no options survey - unless I ask for them. Give the answer and the
  next action only. If I want the reasoning I will ask for it. This applies to
  EVERY reply in EVERY session, including progress updates and error reports.

### Drafted messages and emails (Po, 28 August 2026)
- When I ask for a draft message, email, Teams/Slack post or letter,
  give it ready to paste: NO hard line breaks inside a sentence or a
  paragraph. One paragraph = one continuous line, wrapped by my client,
  never by you.
- Breaks go between paragraphs, between list items, and after the
  subject line only. Never mid-sentence, never at a fixed column width.
- Put the draft in one fenced block so I can copy it whole. The draft
  body does not count against the 12-bullet / 150-word reply cap.

### Written documents — title first, detail later (Po, 15 October 2026)
- Applies to every MD, HTML, Word or PDF file you write: reports, model
  comparisons, audit and review logs, plans, briefs, handovers.
- Open with "In short": the result and any decision needed, ≤5 lines
  (unless a skill sets the opening, e.g. pp_workflow_report).
- Every item in three layers: plain title (≤8 words) → one-line answer
  → detail below, only if needed. Never detail before its title line.
- Evidence, logs and long tables go last (HTML: a final "Detail"
  section or `<details>` fold-outs). Easy English, short sentences.
- Keep the file's structure, brand and colours: cut words, not sections.

### Language and links
- British English everywhere: centre, colour, kilometre, behaviour.
- Every output the user might open (file, folder, GPKG, report, commit,
  PR) is given as a clickable markdown link when produced or mentioned.
  EVERY file you create or write also gets its full absolute path in a
  code block, every time — not only those outside the working tree.
  Never leave the user hunting for where something landed.

### Git and naming
- NEVER append `Co-Authored-By: Claude ...` (or any Claude credit) to
  commits. End the message at the last content line. Applies to every
  repo, every commit, unless the user explicitly asks otherwise.
- The word "claude" never appears in any name you author: branches,
  PR/issue titles, commit messages, file names, identifiers.
- Names use snake_case_with_underscores, never dashes (applies to files,
  folders, branches, skills, agents you create). Vendor-shipped dashed
  names stay as upstream defines them.
- Commit or merge only what the user ordered or explicitly approved;
  approved-but-unordered work goes to a PR and waits for review.

### Claude config location
- All Claude config (`.claude/` — settings, rules, skills, agents,
  memory, hooks, launch.json) lives ONLY in the local profile
  `C:\Users\<user>\.claude\`. Never on network/shared drives (G:, N:, E:)
  and never inside OneDrive-synced project folders. Project data and
  tools MAY live on shares; Claude config never does.

### Continuity files
- `HANDOVER.md` (or any personal continuity note) in a project root is
  personal — gitignore it in the same change that creates it. The root
  `HANDOVER.md` is the single LIVE state file per project:
  overwrite-in-place, ≤120 lines, with a "pending decisions" list at
  the top. Versioned handover documents are frozen archive, named
  `HANDOVER_<Description>_<YYMMDD>.md` (e.g.
  `HANDOVER_PP_Claude_Introduction_260714.md`) — do not re-read them
  for routine session starts.

### CRS hard rules (full doctrine: references/geoai_operating.md)
- Unknown inputs are EPSG:4326 until inspection proves otherwise.
- Working CRS: UK → 27700; W Europe → 3035; CONUS → 5070; global area →
  54009; web tiles → 3857 (output only, never analysis).
- NEVER measure distance or area in EPSG:4326 — reproject first.
- Every spatial output states its CRS; verify CRS explicitly before
  declaring any spatial result correct.

### Database naming and writes
- Never invent the name of a production/published table, view, or
  schema — ask the user (staging names are yours to choose). Never
  write to a production geodatabase without an explicit `--confirm`.
- Spatial-table floor: exactly one PRIMARY KEY + exactly one GIST(geom)
  + table & column comments, or the load is INCOMPLETE. Any further
  index needs per-instance user approval. Details: rules/sql.md.

### Cost honesty
- Before any operation estimated >5 minutes: state the naive cost, the
  cheaper chunked alternative, and why it is equivalent — BEFORE
  running. A failed hour is your fault. Details:
  references/performance_discipline.md.

### P+P brand (full reference: references/prior_partners_brand.md)
- Any document/deck/spreadsheet leaving the building is in Prior +
  Partners house style by default: start from the official template;
  GT America (fallback Arial only — never ship font files externally);
  Orange FF511D / Aubergine 2B242C / Cream F1EEDF / Black 121212;
  sentence case; dates `DD Month YYYY`; units sqm/sqkm/ha; "Prior +
  Partners" with spaces around the +.

## Session pattern (cheap-model default)

1. Read the project's root `HANDOVER.md` (live state + pending
   decisions). Do not re-read archives.
2. Route via the table above before starting specialised work.
3. Delegate field work per model_dispatch.md; keep the main thread for
   decisions.
4. Close loops before ending: approved work → committed/PR'd; state
   file updated; lessons → memory per maintenance_protocol.md.
