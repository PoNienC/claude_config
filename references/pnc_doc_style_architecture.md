# Format specification — "Tool architecture" document

Derived from one exemplar: `urban_intelligence_architecture_260808.html`
(Masterplan+ / urban_intelligence stream, dated 8 August 2026, ~34.7 KB raw / 499 lines).
This is a **single self-contained HTML file** — no external CSS, fonts, images or
JS libraries. One `<style>` block in `<head>`; one small IIFE `<script>` at the
end of `<body>` that only handles screen-fit scaling. Nothing else loads.

---

## 1. Genre and purpose

The document is a **slide-deck-style technical annex**, not a flowing report. It is
built as a sequence of fixed-size "pages" (`<section class="page">`), each one
screen/slide, each answering one question about the tool's architecture. Confirmed
content pattern across the 7 pages of this exemplar:

1. **Cover** — title, one-sentence proposition, ownership/date metadata.
2. **Architecture diagram** — the system as horizontal "bands" (pipeline stages),
   each band a row of labelled boxes connected by arrows, with inter-band notes
   describing what crosses the boundary.
3. **Flow chart** — the same system as a numbered step-by-step process, with
   explicit **gate** steps (decision/refusal points) and "what happens if it's
   refused" annotations. Ends in a feedback loop back to step 1.
4. **Source tree** — the repo/folder layout as a monospaced directory tree, paired
   with a small file-count-by-area summary table.
5. **File-by-file inventory (code)** — a table: file path, phase/priority tag,
   one-sentence description. One table per logical layer (here: Python
   runner/adapters/contracts, then JS dashboard modules).
6. **QA and integration path** — two-column list: QA gates/tests on the left,
   a numbered "integration at maturity" checklist plus "standing rules" on the
   right.

So an "architecture" doc in this house style = **cover → big-picture diagram →
process/flow diagram → repo map → component inventory table(s) → QA/rollout
checklist**. It documents module map, data flow, and dependency/handoff rules —
not API reference detail, not prose narrative essays.

---

## 2. Visual token set

### Palette (verbatim CSS custom properties, from `:root`)

```css
--bg: #0a0a0a; --surface: #141414; --surface2: #1c1c1c;
--line: rgba(255,255,255,0.14); --line-strong: rgba(255,255,255,0.28);
--text: #c8c8c8; --strong: #ffffff; --dim: #9a9a9a; --faint: #5f5f5f;
--accent: #005DFF; --kicker: #FF511D; --success: #4ade80; --warn: #f59e0b;
--violet: #a78bfa; --ui: #c8b5e2; --plum: #920F67;
--sans: "GT America", Arial, Helvetica, sans-serif;
--mono: "GT America Mono", "GT America", Consolas, monospace;
```

Usage map (what each token is *for*, not just its value):

| Token | Hex/value | Role |
|---|---|---|
| `--bg` | `#0a0a0a` | Page background (near-black, not pure black) |
| `--surface` | `#141414` | Fill for diagram boxes |
| `--surface2` | `#1c1c1c` | **Defined but not used anywhere in this exemplar** — reserved token |
| `--text` | `#c8c8c8` | Default body/table text |
| `--strong` | `#ffffff` | Headings, box titles, emphasised tree/table entries |
| `--dim` | `#9a9a9a` | Secondary text: lead paragraphs, box body copy, descriptions |
| `--faint` | `#5f5f5f` | Tertiary: step numbers, tree comments, footer text, band captions |
| `--line` | `rgba(255,255,255,.14)` | Light dividers (footer rule, row dividers, support-band rule) |
| `--line-strong` | `rgba(255,255,255,.28)` | Box/table-header borders |
| `--kicker` | `#FF511D` | **The one P+P-recognisable colour** — eyebrow labels, arrows, gate accents, band labels, "refused" notes, cover accent bar. Matches P+P house Orange exactly. |
| `--accent` | `#005DFF` | Blue — marks the single "changed/highlighted" element in a diagram (`.hi`) and one tag variant (`.dr`) |
| `--success` | `#4ade80` | Green — "ok" status tag only |
| `--warn` | `#f59e0b` | Amber — "planned/future phase" status tag only |
| `--violet` | `#a78bfa` | "Core" status tag only |
| `--ui` | `#c8b5e2` | "P+P Thistle" (named explicitly in the doc's own body copy) — marks this stream's own/new components, distinct from inherited/company ones, in boxes, tags, tree text, and the cover watermark's second word |
| `--plum` | `#920F67` | **Defined but not used anywhere in this exemplar** — reserved token |

Note: this is **not** the standard light P+P brand palette (cream `F1EEDF` /
aubergine `2B242C`). It is a distinct dark "engineering annex" system that only
borrows the P+P orange as its accent/kicker colour, plus references the named
P+P "Thistle" purple. Treat it as a deliberate sibling palette for technical/dev
documents, not a substitute for client-facing brand colour.

### Fonts

- Sans: `"GT America", Arial, Helvetica, sans-serif` — body default, weight **300** (light) on `body`, weight 500 for headings/box titles. No font files embedded or linked (consistent with "fallback Arial only, never ship font files" rule) — pure `font-family` stack, relies on GT America being locally installed; degrades to Arial otherwise.
- Mono: `"GT America Mono", "GT America", Consolas, monospace` — used pervasively for anything label-like: eyebrows/kickers, footer, step numbers, tag pills, tree text, table headers, filename cells, two-column list keys.

### Type scale (body/heading sizes, pt units — this doc is authored in points, not px/rem, because it targets an exact print page size)

| Element | Size | Weight | Colour | Notes |
|---|---|---|---|---|
| Cover watermark `.wm` | 116pt | 500 | strong (2nd word `--ui`) | letter-spacing -.035em, line-height 1 |
| Cover subtitle `.t2` | 42pt | 300 | text | |
| Cover proposition `.prop` | 26pt | (inherit) | text | max-width 52ch, left border 3pt kicker |
| Cover meta line | 14pt (mono) | — | dim | uppercase, letter-spacing .14em |
| `h1` (page heading) | 52pt | 500 | strong | line-height 1.08, letter-spacing -.02em, max-width 40ch |
| `.lead` (standfirst) | 23pt | (inherit) | dim | line-height 1.42, max-width 104ch |
| `.kick` (eyebrow) | 15pt (mono) | — | kicker | uppercase, letter-spacing .2em |
| Diagram box `h4` | 18pt | 500 | strong | |
| Diagram box `p` | 14.5pt | — | dim | line-height 1.38 |
| Flow step `h4` | 16.5pt | 500 | strong | |
| Flow step `p` | 13.5pt | — | dim | |
| Flow step number | 12pt (mono) | — | faint | letter-spacing .14em |
| Table `th` | 12.5pt (mono) | 400 | faint | uppercase, letter-spacing .14em |
| Table `td` | 18pt | — | text | line-height 1.35 |
| Table `td.f` (filename col) | 16pt (mono) | — | strong | |
| Tree text | 17pt (mono) | — | dim | line-height 1.72 |
| Two-col list key `.r .n` | 13.5pt (mono) | — | strong | |
| Two-col list value `.r .x` | 15pt | — | dim | |
| Tag pill | 11.5pt (mono) | — | variant colour | uppercase, letter-spacing .12em |
| Footer | 12.5pt (mono) | — | faint | uppercase, letter-spacing .1em |

### Layout / spacing system

- **Fixed page canvas: 1920pt × 1080pt** (a 16:9 ratio expressed in points, not pixels) — every `.page` is exactly this size. This is a *slide/print hybrid*: on screen the page is scaled down uniformly with `transform: scale(var(--k))` (JS computes `--k` from `window.innerWidth` on load/resize) so it always renders at true proportions; in `@media print`, the transform is removed and `@page { size: 1920pt 1080pt; margin: 0; }` is set, with `page-break-after: always` on every `.page` — one PDF page per section, at 1:1 scale. This dual-mode is the mechanism that lets "the same single offline file" work both as a click-to-view deck and a clean PDF export.
- **Page padding**: content pages `68pt 92pt 100pt` (top/right-left/bottom — extra bottom room reserved for the footer). Cover page: `96pt` all round, content vertically centred (`justify-content: center`) instead of top-anchored.
- **Single column, no sidebar, no nav/TOC** — confirmed absent (no `<nav>`, no anchor links, no table of contents page or element anywhere in the file).
- Content pages follow one fixed vertical stack: kicker → h1 → lead paragraph → flexible body region (fills remaining height, `flex: 1`) → footer pinned to the page bottom via `position: absolute`.
- Two-column layouts (`.cols`, source-tree page's tree+table split) use CSS Grid `1fr 1fr` or explicit width splits (e.g. `flex:1` / `width:42%`), never a sidebar-style persistent nav column.

### Borders / dividers

- `--line` (14% white) — thin dividers: footer top rule, table `td` bottom rule, two-column-list row dividers, support-band top rule.
- `--line-strong` (28% white) — heavier borders: diagram box outlines, table `th` bottom rule.
- Coloured borders substitute for the neutral one to carry meaning (see §5): `--accent` blue for a highlighted/changed box, `--ui` thistle for a "belongs to this stream" box, `--kicker` orange for a gate/decision step, dashed border for a pass-through/continuation placeholder.

---

## 3. Page anatomy, in order

1. **Masthead / cover** (`section.page.cover`, no footer, no page number shown):
   - Big two-tone title treatment (`.wm`): main words in white, one word in the `--ui` accent colour — functions as the document's "logo lockup."
   - Subtitle line (`.t2`): the document's actual descriptive title, e.g. "Architecture and development map."
   - One proposition paragraph (`.prop`): a single sentence or two stating what the thing is and does, set off with a left accent bar (3pt solid kicker orange) and left padding — this is the whole document's abstract.
   - Bottom-left metadata line (`.meta`, mono, uppercase, dim): owner/author code · document class · document type · date, separated by `·` (middle-dot) with non-breaking spaces, e.g. `PNC · personal R&D stream · technical annex · 8 August 2026`.
   - No footer bar, no page number on the cover.

2. **Navigation / TOC**: **absent.** There is no contents page, no anchor nav, no running section index. The only wayfinding is the per-page kicker eyebrow and the footer page number.

3. **Section order and heading hierarchy** (content pages, repeating pattern):
   - `.kick` — eyebrow/kicker line, mono, uppercase, orange. Plain for a top-level topic ("Architecture", "Flow", "Source tree") or compound for a sub-topic using a literal `/` separator styled via `<span class="sep">` in faint grey ("File by file / runner, adapters and contracts").
   - `h1` — one page-level heading only (no h2/h3 as document headings — h3 exists but is reused *inside* the two-column list component as a group label, not a page heading). Written as a full sentence in sentence case, ending in a period, often colon-structured ("The platform pattern, extended by one band: analyse.").
   - `.lead` — one standfirst paragraph, 1–3 sentences, dim colour, explaining the page's point before the diagram/table does.
   - `.body` — the page's main content: diagram, flow chart, tree, table(s), or two-column list. Always exactly one primary content block per page in this exemplar (occasionally split into two side-by-side sub-blocks, as on the source-tree and QA pages).
   - `.foot` — footer bar (see below).

4. **Footer** (`.foot`, present on every content page, absent on the cover):
   - Fixed to page bottom, full content width, top border rule (`--line`), mono, uppercase, faint colour, small size (12.5pt).
   - Left: a running identity string, **identical wording repeated on every page**: `<owner> · <doc class> · <project name> | <document title> | <date>`, e.g. `PNC · personal R&D · urban intelligence | architecture and development map | 8 August 2026`.
   - Right: two-digit page number (`.pg`, dim colour), matching the physical page position (02–07 in this file; page 1/cover carries no visible number).

---

## 4. Recurring components and styling

- **Tables** (`table`/`th`/`td`): full-width, `border-collapse: collapse`, no vertical rules, no zebra striping, no header background fill — just a stronger bottom border under `th` and a lighter bottom border under every `td` row. `th` is mono/uppercase/faint; `td` is normal weight/size text. Special column classes: `td.f` = monospace filename/key cell (white, fixed width, may contain a `.id` sub-span in kicker colour as a prefix code); `td.d` = plain description cell; `td.t` = fixed-width tag-holding cell.

- **Status/phase tag pills** (`.tag`): inline-block, mono, uppercase, small, 1px solid border in the variant colour, no fill, `padding: 2pt 7pt`. Seven variants seen or defined (the shared six plus the stream-specific `.uip`): `.ok` (green — done/proven), `.dr` (blue — draft), `.ph` (amber — planned/future phase), `.ps` (orange — reserved), `.pk` (faint grey — reserved/parked), `.core` (violet — company-core item), `.uip` (thistle — this-stream's own phase code, used here for labels like `UI-0` … `UI-5`). Only `.uip` and `.ph` are actually exercised by content in this exemplar; the rest are defined for a shared/reused stylesheet across sibling documents.

- **Directory/repo tree** (`.tree`): monospace block built from literal box-drawing characters (`└──`, `├──`, `│`) and `&nbsp;` runs for indentation — **not** a `<ul>` list, **not** an SVG, just literal characters in a `<p>`. Folder/file names in `<b>` (white, weight 400 — bold via colour/weight-reset, not heavier boldness). Trailing inline comments after an em dash in faint grey (`.c`). Two extra inline-colour classes for emphasis inside the tree: `.k` (kicker orange, used for a standalone callout line) and `.u` (ui/thistle, used to flag the one folder that is this stream's own root).

- **Two-column definition/key-value list** (`.cols` → `.grp` → `.r`): CSS grid, two equal columns, gap only horizontal. Each `.grp` is a labelled group: mono/uppercase/kicker-coloured `h3` group title, then a stack of `.r` rows — each row itself a two-column grid (fixed 232pt key + flexible value), bottom-divider between rows (`--line`), key in mono white, value in regular dim text. This is the "QA gate list" / "checklist" / "standing rules" component — effectively a styled `<dl>` built from `div`s.

- **Key-value metadata blocks**: the cover `.meta` line and the footer are the only true metadata strings; both follow the same convention — mono, uppercase, small, dim/faint, segments joined by a middle-dot (`·`) or pipe (`|`) with explicit `&nbsp;` padding around the separator.

- **Callout box**: only one distinct callout pattern is used — a left-accent-bar blockquote-like paragraph (3pt solid kicker border + left padding), used once on the cover for the proposition statement. No separate "note/warning" admonition box style exists elsewhere in the file (the flow chart's "gate" steps serve that role instead — see §5).

---

## 5. Diagram methodology (the part that matters most)

**Technology: plain HTML/CSS boxes and flex/grid layout. No SVG, no Mermaid, no canvas, no embedded/base64 images anywhere in the file.** The stylesheet says so explicitly in its own comment: *"diagrams, built from boxes rather than SVG so they render identically on screen and in a PDF export."* Arrows are literal Unicode glyphs styled as inline text (`→` `←` `↓` `↵` `⟲`/`↺`), not vector paths.

Two diagram types appear, both reusable as named patterns:

**A. Band/layer architecture diagram** (`.arch` → `.band` → `.row` → `.bx`, used on the "Architecture" page):
- Vertical stack of horizontal **bands**, each band = a stage in the pipeline (e.g. Analyse → Define → Assemble → Run, plus a closing "Support" band).
- Each band has a left-hand label column (fixed 150pt: bold mono kicker-coloured stage name + a small faint mono caption underneath) and a right-hand **row** of boxes.
- Boxes (`.bx`) are bordered rectangles (`--line-strong` border, `--surface` fill) each containing a bold white `h4` (component name, often a literal file path) and a dim `p` (one-sentence description). Boxes are connected left-to-right by inline arrow glyphs (`.ar`, kicker-coloured `→`/`←`; a faded dim variant `.ar.d` marks an optional/lighter-weight connection).
- A `.bx.stack` variant nests smaller boxes vertically inside one column (box-of-boxes), for grouping closely related sub-components without a full extra band.
- **Colour coding for meaning, not decoration**: default border = existing/inherited/company component; `.bx.hi` (accent blue border) = the one deliberately highlighted/changed component; `.bx.ui` (thistle border) = a component that belongs to *this* stream/project specifically, as opposed to the inherited platform.
- Between bands, a `.down` row (same 150/1fr grid, empty label cell) carries a centred down-arrow (`↓`) plus a small mono caption explaining what crosses that boundary (e.g. "the runner writes only what the contract requires") — this is how the diagram narrates *data flow*, not just structure.
- A closing `.support` band (grid, top rule, no boxes) lists cross-cutting concerns (QA, docs/ledger) as plain text rather than boxes, since they apply to the whole pipeline rather than one stage.

**B. Numbered flow/process chart** (`.flow` → `.frow` → `.st`, used on the "Flow" page):
- Horizontal rows (`.frow`) of numbered step chips (`.st`), each with a small faint mono step number (`.n`, e.g. "01", zero-padded two digits), a bold white `h4` step name, and a dim one-line description. Steps connect via arrow glyphs (`.fa`), and rows read alternately left-to-right then right-to-left (a boustrophedon/serpentine layout) to keep the whole process on three compact rows instead of one long line.
- **Gate steps** (`.st.gate`) are the decision/refusal points: kicker-orange border, dark warm background override (`#1c1512`, a one-off, not a root token), kicker-coloured heading, labelled with the literal word "GATE" appended to the step number (e.g. "02 · GATE"). This is the doc's visual vocabulary for "the system can refuse/stop here."
- A **dashed-border step** (inline `style="border-style:dashed"`, empty step number) marks a pass-through/continuation point linking one row's flow to the next.
- After each row, a `.fnote` line (mono, dim, small, with a corner-arrow glyph `↵`) states what happens on the refusal/failure branch — e.g. "refused — nothing lands in the project, and the runner says why." The final `.fnote.k` (kicker-coloured, loop glyph `⟲`) states the cyclic/steady-state condition that closes the process.
- **Legend**: there is no separate boxed legend element — the legend is inline and textual, delivered via the `.lead` paragraph at the top of the page ("Orange gates are the points where the stream refuses, reports or stops rather than assuming...") plus the `.fnote` annotations themselves. Colour meaning is explained in prose, not in a colour-key box.

Both diagram types share the same underlying idiom: **label + arrow + box, in flexbox rows, with colour borders as the only semantic differentiator, and prose (lead paragraph + inline notes) doing the legend's job.**

---

## 6. Writing conventions

- **British English** throughout: "licence" (noun), "colour," "organise/analyse" spellings; `<html lang="en-GB">` declared explicitly.
- **Sentence case**, not Title Case, for every heading level: eyebrows ("Source tree," "File by file"), h1s (only first word and proper nouns capitalised), group labels (`h3` in the two-column list, e.g. "QA gates and probes — run before every phase exit").
- `h1`s are written as **complete statements ending in a full stop**, frequently using a colon to set up a two-part claim ("The platform pattern, extended by one band: analyse."; "Modules 40+ — the plugin's capability set." — note this second one uses an em dash instead and drops the terminal period after a proper-noun-like fragment; treat the terminal period as the norm and this one as a minor exception).
- **Date format: `D Month YYYY`, no zero-padding on the day, no ordinal suffix** — e.g. "8 August 2026," not "08 August 2026" or "8th August 2026." (Flag: this differs slightly from the user's general house rule of `DD Month YYYY` zero-padded — replicate what the exemplar actually does, i.e. unpadded day, since fidelity to the exemplar is the brief.)
- **Numbering**: flow-chart steps use zero-padded two-digit numbers ("01," "02"); checklist items in the two-column list also use zero-padded two-digit numbers with a literal double space before the label ("01  licence audit"); component/phase tags use a short code + dash + digit ("UI-0," "UI-1"..."UI-5") with room deliberately left in the numeric range (modules numbered from 40, "clear of the company range 01–31," explicit statement that gaps are intentional so future additions don't require renumbering).
- Middle-dot `·` (with non-breaking spaces either side, written as `&nbsp;·&nbsp;`) is the preferred inline separator for metadata strings; pipe `|` separates larger metadata clauses; a plain `/` (with padding, as a styled span) separates a topic from its sub-topic in eyebrows.
- Prose voice: short declarative sentences, present tense, first person absent (no "we"/"I"), technical but not jargon-dense; parenthetical asides used to name the underlying engine/library (e.g. "OSMnx + neatnet," "PST core (pstalgo)").

---

## 7. File naming convention (from the exemplar filename)

`urban_intelligence_architecture_260808.html`

Pattern: `<topic_or_project_slug>_<doctype>_<YYMMDD>.html`

- `topic_or_project_slug` — snake_case project/subject name (`urban_intelligence`).
- `doctype` — snake_case document type (`architecture`); by analogy the exemplar's own text references a sibling "development plan" document in the same folder, implying a `<slug>_development_plan_<YYMMDD>.html` companion using the same suffix convention.
- `YYMMDD` — **two-digit year**, then month, then day, all zero-padded, no separators (`260808` = 2026-08-08). Note this is a *different* date-stamp width than the `YYYYMMDD` (full 4-digit year) pattern seen elsewhere in this user's conventions (e.g. `quick_diagnosis_20260704.md`) — the exemplar uses the shorter `YYMMDD` form, matching the pattern already used for versioned handover docs (`HANDOVER_<Description>_<YYMMDD>.md`). Reproduce `YYMMDD` for this specific document family since that is what the exemplar itself does.
- All lower-case, underscores only, no spaces or dashes, `.html` extension (single self-contained file, no companion assets folder).

---

## 8. Distinctive / brand-recognisable elements

- **Kicker orange `#FF511D`** is an exact match to Prior + Partners' house Orange — the one deliberate brand thread running through an otherwise non-standard dark palette.
- **Named reference to "P+P Thistle #C8B5E2"** appears in the document's own body copy (page 6), confirming the `--ui` token is a recognised extended-palette colour in this firm's broader design system, used here to mean "this plugin/stream's own identity colour" as distinct from three other named company group colours mentioned but not swatched in this file ("orange, matcha, cobalt, violet").
- **GT America / GT America Mono** font family declared as the primary stack (P+P's house typeface, referenced by name only — no embedded font files, degrading gracefully to Arial/Helvetica/Consolas), consistent with the firm rule against shipping font files externally.
- The overall aesthetic — near-black background, light-weight sans body copy, mono-uppercase micro-labels everywhere, thin hairline borders, unicode-arrow flow diagrams — reads as a distinct **"technical annex / engineering deck"** sub-brand, deliberately different from Prior + Partners' light cream/aubergine client-facing brand system. It should be treated as its own recognised variant (call it, for reference, the "dark technical annex" style) rather than a deviation from brand — the document states outright it exists so this and a sibling "platform" document can "sit on the same board," implying this dark style is itself an established, reused house pattern for architecture/build documentation, separate from client deliverables.
- **1920pt × 1080pt fixed-canvas, screen-scale + print-exact dual rendering** is itself a distinctive, load-bearing technical signature of this document family — reproducing it (rather than a normal responsive/scrolling page) is necessary for a new document to "sit on the same board" as this one and its siblings.

---

## Explicit absences (stated for completeness — their absence is itself information)

- No table of contents / navigation of any kind.
- No footer, no page number, on the cover page (footer appears only on content pages 2 onward).
- No SVG, no Mermaid, no canvas, no raster/base64 images anywhere in the file — all diagrams are HTML/CSS box layouts with Unicode arrow glyphs.
- No external stylesheet, font file, or script dependency — fully self-contained, single file, works offline.
- No boxed/swatched colour legend for diagrams — colour meaning is explained in running prose (lead paragraphs, inline notes) rather than a dedicated key.
- No admonition/callout component beyond the one cover-page accent-bar paragraph and the flow chart's "gate" steps, which double as the document's only "warning/decision" visual idiom.
- `--surface2` and `--plum` custom properties are declared in `:root` but never actually applied anywhere in this exemplar — reserved tokens from a shared stylesheet, not exercised here.

---

## Reproducibility checklist for a future author (no access to the exemplar)

1. Single HTML file, inline `<style>`, `1920pt × 1080pt` page canvas, CSS-transform screen scaling + exact `@page`/`page-break-after` print rules, tiny resize-fit script — copy this scaffold verbatim.
2. Apply the palette from §2 verbatim (13 custom properties); use `--kicker` (#FF511D) as the only accent colour touching every page; use `--accent` (blue) sparingly for exactly one "this changed" highlight per diagram; reserve `--ui`/thistle for "belongs to this project" components.
3. Fonts: `"GT America", Arial, Helvetica, sans-serif` for body (weight 300, headings weight 500); `"GT America Mono", "GT America", Consolas, monospace` for every label/eyebrow/footer/tag/tree/table-header element.
4. Page skeleton per content page: kicker eyebrow → sentence-case `h1` ending in a full stop → one dim lead paragraph → flexible body region → fixed-bottom footer (identity string left, page number right). Cover page differs: big two-tone watermark title, subtitle, one accent-bar proposition paragraph, bottom-left metadata line, no footer/page number.
5. No nav/TOC. Build diagrams as flex/grid box layouts with Unicode arrows, never SVG/Mermaid/images; colour-code box borders for meaning (default = existing, accent-blue = highlighted, ui-thistle = "ours"); represent decision points as bordered/coloured "gate" chips with an explained refusal branch, never a generic warning icon.
6. British English, sentence case everywhere, `D Month YYYY` unpadded-day dates, zero-padded two-digit step/item numbering, middle-dot/pipe separators in metadata strings.
7. Name the file `<slug>_architecture_<YYMMDD>.html`.
