# PNC documentation styles — Brief / Architecture / QA-QC report

> Read when: producing ANY tool design brief, source-code architecture
> document, or QA/QC testing report. Declared canonical by Po on
> 10 August 2026 from three Masterplan+ exemplars. This file is the
> shared system + dispatch; the per-format reproduction specs are:
> `pnc_doc_style_tool_brief.md` · `pnc_doc_style_architecture.md` ·
> `pnc_doc_style_qaqc_report.md` — Read the matching one BEFORE
> authoring, and copy the scaffold from the canonical exemplar.

## The three formats

| Format | Use for | Spec | Canonical exemplar |
|---|---|---|---|
| Tool design brief | why/what/roadmap pitch for a named tool; leadership-facing narrative, no code | pnc_doc_style_tool_brief.md | `Masterplan_Plus\01_briefs\masterplan_plus_tool_design_brief_v5_260804.html` |
| Tool architecture | module map, data flow, repo tree, file inventory, QA/rollout path of a codebase | pnc_doc_style_architecture.md | `Masterplan_Plus\urban_intelligence\00_docs\urban_intelligence_architecture_260808.html` |
| QA/QC testing report | evidentiary test-run record: gates, assertions, transcripts, critic verdicts | pnc_doc_style_qaqc_report.md | `Masterplan_Plus\urban_intelligence\qa\reports\qa_report_260809_7.html` |

Exemplar root (prefix each path above): `C:\Users\po.nienchen\OneDrive - priorpartners.com\Documents\05_Code_Scripts\tool_development\`

## Shared design system — the "dark technical annex" sub-brand

- INTERNAL documents only. They borrow exactly two things from the
  official P+P brand: Orange `#FF511D` (as the kicker/eyebrow accent)
  and the GT America typeface. Aubergine/cream are deliberately absent.
  Anything client-facing still follows
  `references/prior_partners_brand.md` — do not mix the two systems.
- Single HTML file, one inline `<style>` block, no external CSS/JS/
  fonts, no build step. Fonts by name only (GT America → Arial
  fallback) — never ship font files. Raster figures are the one
  exception: brief screenshots and QA evidence images are relative
  `<img>` references to a sibling asset folder (so those two are NOT
  single-file portable); the architecture doc alone is fully
  self-contained.
- Core palette tokens (shared verbatim across all three):
  `--bg:#0a0a0a; --surface:#141414; --line:rgba(255,255,255,.14);
  --text:#c8c8c8; --strong:#fff; --dim:#9a9a9a; --faint:#5f5f5f;
  --accent:#005DFF; --kicker:#FF511D; --success/--ok:#4ade80;
  --warn:#f59e0b`, plus an emphasis border `rgba(255,255,255,.28)`
  (named `--line-strong` in brief/architecture, `--line2` in QA).
  Format-specific accents: `--violet:#a78bfa` (brief + architecture
  only); `--ui:#c8b5e2` (P+P Thistle, "this stream's own" colour —
  architecture + QA only).
- Two-voice typography: GT America sans weight 300 for prose (500 for
  headings — never bold 700, never italic); GT America Mono, uppercase
  + wide letter-spacing, for ALL structural text (kickers, footers,
  tags, table headers, step numbers, trees, evidence values).
- Page rhythm: orange mono kicker → h1 as a full sentence in sentence
  case ENDING IN A FULL STOP → dim lead paragraph → structured body →
  mono footer (`<owner> · <classification> · <project> | <doc title> |
  <date>`, page number right). Author is initials "PNC", never a name.
- Diagrams are pure HTML/CSS flex/grid boxes with Unicode arrow glyphs
  (→ ↓ ↵ ⟲) — NEVER SVG, mermaid, canvas or base64 images. Colour-coded
  borders carry meaning (default = existing; accent blue = the one
  highlighted change; thistle = this stream's own; orange = gate/
  decision point); legends are prose, not colour-key boxes.
- Status chips/tags: outline-only mono pills, no fill. Brief +
  architecture share a six-term dev-status vocabulary: core (violet) /
  available–ok (green) / being extended–dr (blue) / planned–ph (amber)
  / project-specific–ps (orange) / parked–pk (faint); architecture adds
  a stream-phase tag `.uip` (thistle, e.g. UI-0…UI-5). The QA report
  uses its own separate four-term verdict vocabulary — pass (green) /
  fail (red `#f87171`) / not_built / not_run (faint) — never the dev
  tags.
- Writing: British English (`lang='en-GB'`), sentence case everywhere,
  short declarative present-tense sentences, no "we"/"I". Separators:
  `·` joins same-tier items, `|` separates footer field groups, `/`
  separates kicker topic/sub-topic, em dash sets up clauses.
- Dates INSIDE these documents: `D Month YYYY`, unpadded day
  ("4 August 2026") — Po CONFIRMED 10 Aug 2026 that these three
  families follow the exemplars; the global `DD Month YYYY` rule
  stands for everything else.

## Two page models

- **Slide-canvas** (brief + architecture): fixed 1920×1080pt
  `<section class="page">` blocks, `overflow:hidden`, JS-computed
  `--k` scale-to-viewport on screen, `@page {size:1920pt 1080pt}` +
  `page-break-after:always` for one-slide-per-PDF-page print. Cover
  page has no footer; content must be authored to fit each canvas.
- **Scrolling evidence page** (QA report): normal flow, max-width
  1400px, `padding:40px 56px`, no JavaScript at all, h2 rules as
  section dividers. Machine-generated by the QA runner script named in
  the footer.

## File naming (all snake_case, lower, YYMMDD)

- Brief: `<product>_<doc_type>_v<N>_<YYMMDD>.html` + raster screenshots
  in sibling `pages/brief_assets_<YYMMDD>/` ("+" in a product name →
  the word "plus").
- Architecture: `<slug>_architecture_<YYMMDD>.html` — fully
  self-contained, no asset folder.
- QA report: `qa_report_<YYMMDD>_<N>.html` + matching
  `img_<YYMMDD>_<N>/` figure folder, in `qa/reports/`; transcripts in
  sibling `qa/transcripts/<YYMMDD>_<gate_id>.txt` (date only — shared
  across same-day reruns, while report+img pairs stay per-run).

## Open decisions (single-exemplar inferences — ask Po if load-bearing)

- QA filename `_N`: inferred same-day run counter — Po asked
  10 Aug 2026, didn't know either. Whatever it counts, keep the
  report's `_N` and its `img_<date>_<N>/` folder suffix paired.
- QA failure-state styling (fail chips/✗ rows/"not acceptable"
  verdict): inferred by symmetry — exemplar was all-green.
- Whether other streams swap Thistle for their own registry colour.
- Per-spec flagged internal inconsistencies in the exemplars (e.g.
  cover-vs-footer capitalisation in the brief) — resolve deliberately,
  do not copy.

## Decided since the exemplars

- **Architecture annex with UI screenshots** (Po, 19 September 2026):
  an architecture deck MAY add "In use" pages showing the tools on
  screen. Screenshots are raster files in a sibling
  `<slug>_architecture_assets_<YYMMDD>/` folder (the brief's pattern,
  `<NN>_<desc>` names) and a PDF export goes with it for sending, as the
  HTML is no longer single-file. Diagrams stay HTML/CSS. Each frame
  keeps its image's aspect ratio so HTML markers (orange-outlined
  circles) land on the same pixel on screen and in the PDF; shots still
  to come are amber dashed placeholders naming the expected file. First
  use and reusable tooling: `uk_baseline_architecture_260919.html`,
  `uk_baseline\scripts\docs\capture_deck_shots.py` + `render_deck.py`
  (overflow check, previews, PDF).
