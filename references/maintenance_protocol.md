# Maintenance protocol — who may edit what, and when to condense

> Read when: editing any config/memory file, ending a session, or a
> file has grown past its cap. Written 4 July 2026.

## Edit-permission matrix

| Surface | Weak model may… | Requires asking Po first |
|---|---|---|
| Project memory (`~/.claude/projects/<slug>/memory/*`) | create/update/delete freely per the memory rules | — |
| Root `HANDOVER.md` (project live state) | overwrite-in-place every session | — |
| `~/.claude/references/*` | fix factual errors, add examples, append lessons | wholesale rewrites; deleting a file |
| `~/.claude/CLAUDE.md` (router) | add a ROUTE LINE for a new reference file | changing/removing any Universal rule; raising the 150-line cap |
| `~/.claude/rules/*` (paths-gated + stubs) | fix a wrong path pattern | content changes to sql.md / gpkg (they encode Po's firm rules) |
| `~/.claude/backup_*` | READ ONLY | any modification or deletion (Po only) |
| Repo code/docs | per the normal approval flow | commits/merges not explicitly ordered (PR + wait) |
| Production DB objects, published names | never | always |

## Where lessons go (one place each — no duplicates)

- **Behavioural correction from Po** ("never do X again") → project
  memory file (type: feedback) + one-line pointer in MEMORY.md. If it
  applies to ALL projects, ALSO propose a Universal-rule line to Po —
  do not add it to the router yourself.
- **Technical gotcha with a workaround** (API quirk, Windows footgun)
  → the topical references/ file (e.g. a new "gotchas" section), cited
  with date + incident.
- **Project state change** (merge landed, decision taken) → root
  HANDOVER.md, same session.
- **Judgment example worth teaching** → judgment_rubrics.md as a ✅/❌
  example under the matching rubric.

Format for feedback memories (existing convention): frontmatter
(name/description/type) + the fact + **Why:** + **How to apply:**.

## Condensation triggers (act when hit, not before)

| File | Trigger | Action |
|---|---|---|
| MEMORY.md index | >30 entries or >150 lines | run the `consolidate-memory` skill |
| Root HANDOVER.md | >120 lines | compress finished threads to one line each; archive nothing separately — git/PRs are the history |
| Any references/*.md | >350 lines | split by topic; update the router table |
| CLAUDE.md router | >150 lines | move detail down into references/; the router only routes |
| rules/sql.md | — | leave alone; Po's firm doctrine, paths-gated |

## Session-end checklist (every session, cheap-model executable)

1. Approved work committed or PR'd? (Never park approved diffs.)
2. Root HANDOVER.md overwritten with: state table, pending decisions,
   next actions?
3. Any Po correction this session → memory file written + indexed?
4. Any background servers you started that should be stopped?
5. New file that Po must not lose → is its path in HANDOVER.md as a
   clickable link + absolute path?

## Verification duty on config edits

After ANY edit to CLAUDE.md or references/: line-count the always-on
set (CLAUDE.md + every rules/*.md WITHOUT a `paths:` key). If it
exceeds 500 lines, condense before ending the session. Command:
PowerShell — count lines of CLAUDE.md and each rules file lacking a
`paths:` line; sum.
