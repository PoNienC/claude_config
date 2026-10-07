# Format specification — "Tool Design Brief" (Masterplan+ house style)

Reverse-engineered, verbatim-where-compact, from one exemplar:
`masterplan_plus_tool_design_brief_v5_260804.html` (Prior + Partners, Digital
Innovation, author initials "PNC", 4 August 2026, v5).

A **dark-mode, fixed-size 16:9 "slide deck" in a single HTML file**: one
`<style>` block + `<section class="page">` blocks + a small resize
script. No external CSS/JS/font files, no build step (raster screenshots
are relative-path references to a sibling asset folder, §6).

---

## 1. Genre / what a "Tool Design Brief" contains

An internal Prior + Partners pitch/proposal narrative for a named,
in-development software tool, aimed at aligning leadership and the digital
innovation team around **why / what / how / current status / roadmap**. It
is qualitative and narrative, not a technical spec (no code, no API
tables, no data charts) and not external marketing collateral (no CTA, no
pricing, no contact form).

Fixed content arc, in order, across roughly 14 "pages" (slides) plus
appendices:

1. **Cover** — product wordmark, one-line strapline, one-sentence
   proposition, firm/date meta.
2. **The issue** — problem statement, 3 bullet points with sub-explanations.
3. **Key drivers** — requirements, 6 bullets in two columns.
4. **The approach** (spans several consecutive pages, each tagged as a
   sub-section of "The approach" in the kicker): how the system is
   structured (3-stage pipeline diagram), what makes it trustworthy (2×2
   rule cards), the shared/declared data model (two comparison panels),
   what a model layer means (list + screenshot figure).
5. **Project configuration** — the configuration tool/wizard, as a 5-step
   sequence diagram.
6. **The working product** — what ships by default (table + screenshot),
   what the current workflow enables (a 5-row stage/function/impact table).
7. **The platform / component library** — a capability "board" grouped
   into 4 families, each with a colour swatch, description and screenshot,
   followed by a 6-term status legend.
8. **Audiences** — two side-by-side comparison panels (internal team vs
   read-only client output).
9. **Future direction** — a 4-stage maturity roadmap (now / next / then /
   future) as a horizontal card row.
10. **Closing proposition** — split hero-image layout, restated value
    proposition, a 3-point "trio" (current/traceable/reusable), one bold
    closing line.
11. **Appendix A1** — full step-by-step table of the configuration
    sequence (9 rows).
12. **Appendix A2** — full capability inventory, grouped into the same 4
    families as the component library page, each capability tagged with a
    development-status pill (core / available / being extended / planned /
    project-specific / parked).

Every interior page carries a two-level **kicker** label: either a single
section name ("The issue", "Key drivers") or "Section / Sub-section"
("The approach / how it fits together") — the "/" form is how a multi-page
section signals its sub-pages without literal numbering.

## 2. Full visual token set

### CSS custom properties (verbatim, `:root`)

```css
--bg: #0a0a0a; --surface: #141414; --surface2: #1c1c1c;
--line: rgba(255,255,255,0.14); --line-strong: rgba(255,255,255,0.28);
--text: #c8c8c8; --strong: #ffffff; --dim: #9a9a9a; --faint: #5f5f5f;
--accent: #005DFF; --kicker: #FF511D; --success: #4ade80; --warn: #f59e0b;
--violet: #a78bfa;
--sans: "GT America", Arial, Helvetica, sans-serif;
--mono: "GT America Mono", "GT America", Consolas, monospace;
```

- `--surface2` (#1c1c1c) is declared but **never used** anywhere in the
  document — carry it forward for future use (e.g. a third card tier) but
  don't feel obliged to invoke it.
- Page/canvas background is pure black (`html, body { background:#000 }`)
  with the `.page` itself painted `--bg` (#0a0a0a) — a near-black, not
  true-black, reading surface, so black letterboxing shows around scaled
  pages on screen.
- One extra swatch colour appears only inline, not as a variable:
  `#4BB400` (a saturated green, distinct from `--success` #4ade80), used
  for the "Registers and schedules" family colour dot. Treat the family/
  group colour-coding as a 4-colour cycle: kicker-orange → accent-blue →
  this extra green → violet.

### Brand-palette relationship (flag explicitly, do not silently assume)

Only the orange (`#FF511D`) is shared with the official P+P brand
palette; aubergine and cream are **absent**. This is a deliberate dark
"product UI" sub-brand borrowing brand orange as its single signature
accent — do not assume the full P+P palette applies (see the umbrella
`pnc_documentation_styles.md`).

### Typography

- Sans stack `"GT America", Arial, Helvetica, sans-serif` — body copy.
  Body default weight is **300 (light)**; headings/emphasis use **500
  (medium)**. Only two weights are used anywhere; nothing is ever bold
  (700) or italic.
- Mono stack `"GT America Mono", "GT America", Consolas, monospace` —
  reserved exclusively for "structural/metadata" text: kickers, footers,
  table column headers, tags/pills, step numbers, family/group titles,
  figure captions, panel sub-labels. Always set uppercase with wide
  letter-spacing (0.06em–0.2em depending on element). **Never** used for
  body prose and never used as a literal code/chip element — there are no
  `<code>` or `<pre>` blocks anywhere in this genre.
- Font sizes are all in **points (pt)**, not px/rem/em for base sizing —
  consistent with the fixed-size print/slide canvas (see §3). Key sizes:
  - h1: 58pt / line-height 1.08 / letter-spacing -.02em / weight 500 /
    max-width 34ch (constrains wrap length). Modifiers seen: `.tight`
    (margin-bottom 16pt instead of 24pt), `.wide` (max-width 46ch),
    `.sm` (50pt, max-width 52ch). One page also inline-overrides to 46pt.
    The closing page's h1 is unconstrained width, 58pt, line-height 1.1.
  - `.lead` / `.say` intro paragraph: 25pt / line-height 1.45 / colour
    `--dim` / max-width 96ch. `.say` variant (used mid-body as a bold
    lead-in callout line, e.g. "**Why this structure.** …") sets colour
    to `--text` instead of `--dim` and drops max-width/margin.
  - Big bulleted list items (`ul.big li`): 24pt, weight 500, colour
    `--strong`, with a nested `.m` explanatory sub-line at 21pt, weight
    300, colour `--dim`.
  - Table body text 20pt (17.5pt for the secondary/description column,
    `td.sm`); a `.tight` table variant drops to 18pt/16.5pt for denser
    tables.
  - Card/panel body copy ranges roughly 18–21pt depending on component;
    mono labels range 11.5–15.5pt.

### Spacing / layout system

- **Fixed-size canvas, not fluid**: each `.page` is exactly **1920pt ×
  1080pt** (16:9, equivalent to 26.67in × 15in / a slide, per an
  in-file comment). Padding: `74pt` top, `92pt` left/right, `106pt`
  bottom. `overflow: hidden` — content must be authored to fit exactly
  one canvas; nothing scrolls within a page.
- **No sidebar, no nav rail.** Each page is a single full-bleed column;
  internal multi-column layouts (two-panel, 2×2 grid, 5-column steps,
  4-column horizon, etc.) are composed with CSS grid/flex inside the
  fixed canvas, not a persistent site-wide layout.
- **Screen behaviour**: pages stack vertically in normal document flow
  with 18pt gaps between them, each uniformly scaled down to fit the
  viewport width via a JS-computed CSS variable `--k` and
  `transform: scale(var(--k,1))` with `transform-origin: top left`; a
  compensating negative margin avoids extra blank space beneath the
  scaled box. This is how a 1920pt-wide canvas is made viewable in a
  normal browser window without horizontal scrolling.
- **Print behaviour**: `@page { size: 1920pt 1080pt; margin: 0 }`, each
  `.page` forced onto its own printed/PDF page (`page-break-after:
  always`, transform disabled) — the intended deliverable is a
  slide-per-page PDF export as much as an on-screen HTML file.
- Borders/dividers are hairlines: 1px solid `--line` (rgba white 14%)
  for most rules, `--line-strong` (rgba white 28%) for emphasis
  (e.g. table header underline), and heavier 3pt solid colour rules for
  "top accent" treatments on steps/families/trio blocks.

## 3. Page anatomy, in order

Every interior content page (P02–P13, A1, A2) follows the same skeleton,
top to bottom:

1. **Kicker** (`.kick`) — mono, 15pt, uppercase, letter-spacing .2em,
   colour `--kicker` (orange). Either a bare section name or
   `Section <span class="sep">/</span> Sub-section` (the separator glyph
   is coloured `--faint`, not orange).
2. **H1 headline** — a full declarative **sentence, ending in a full
   stop**, sentence case (not title case), not a noun-phrase title. E.g.
   "A masterplan moves faster than the information around it.",
   "What the platform needs to do." This sentence-headline convention is
   used on every single page without exception.
3. **Optional `.lead` paragraph** — one sentence elaborating the headline,
   dimmed colour, present on most but not all pages (P05, P11's board
   page, and A1/A2 vary in whether they include one — check the specific
   page's rhythm rather than assuming it's mandatory).
4. **Body block** (`.body`, flex, `flex: 1`) — the page's structured
   content: a table, a list, a pipeline/steps/horizon diagram, a pair of
   panels, a card grid, or a component board. Optionally followed by one
   or two `.say` callout paragraphs (bold lead-in phrase + explanatory
   continuation) as closing commentary on that page's content.
5. **Footer** (`.foot`) — mono, 12.5pt, uppercase, letter-spacing .1em,
   colour `--faint`, top hairline border. Standard format, left field:
   `Prior + Partners · digital innovation · PNC | Masterplan+ tool design
   brief | 4 August 2026`; right field: two-digit page number (`02`…`13`),
   coloured `--dim`. **The two appendix pages deviate**: A1's date field
   is replaced with the word "appendix" and its page number is "A1"; A2
   drops the document-title/date entirely and instead prints the firm's
   postal address and website (`70 Cowcross Street, London EC1M 6EJ |
   priorandpartners.com`) with page number "A2" — i.e. the very last page
   closes with a letterhead-style corporate signature rather than a
   restated document title.

**Cover page** (P01) is structurally different: no kicker/h1/footer.
Full-bleed background photo with a directional dark gradient veil, a
large two-line wordmark block (`.wm` product name + `.t2` subtitle), one
proposition sentence with a left orange accent-border rule, and a
bottom-left meta line (`Prior + Partners · Digital Innovation · PNC ·
4 August 2026` — note "Digital Innovation" is capitalised here, unlike
the lowercase "digital innovation" used in every interior footer; this
inconsistency exists in the exemplar and should be resolved one way or
the other by a future author, not silently copied as if intentional).

**Closing page** (P14, `.closing`) is also structurally distinct: split
57/43 layout — right-hand bleed image with its own left-fading gradient,
left-hand content column with kicker, h1, a support paragraph, a 3-item
"trio" row (mono uppercase labels, alternating orange/blue top accent
rules), and a bold final statement line with a left orange border rule.
Footer is replaced by a minimal one-line `.cfoot` (product name ·
"Working title" · firm · department · initials) with **no date and no
page number**.

**No table of contents / navigation exists anywhere in the document** —
confirmed absent. Reading order is purely linear (scroll or print).
**No persistent header/masthead repeats across pages** beyond the
per-page kicker+footer described above — there is no logo image, only
text.

## 4. Recurring components and styling

- **Tables** (`table` / `table.tight`): no cell borders except a bottom
  hairline per row; header row is mono/uppercase/faint with a heavier
  bottom rule; first data column typically bold-white (`td.nm`) as a
  label, remaining column(s) dimmed smaller text (`td.sm`) as
  description. No zebra striping, no vertical rules, no background fills.
- **Status/tag pills** (`.tag`): mono, 11.5pt, uppercase, letter-spacing
  .12em, **outline-only** (1px coloured border, no fill), inline-block,
  small padding. Six fixed semantic variants — this exact 6-term
  vocabulary is a reusable "roadmap grammar" worth keeping consistent
  across future briefs:
  - `.core` (violet) — core/foundational
  - `.ok` (green) — available
  - `.dr` (blue) — being extended / in development
  - `.ph` (amber) — planned
  - `.ps` (orange) — project-specific (bespoke, outside shared platform)
  - `.pk` (grey/faint) — parked (retained but not offered)
- **Panel boxes** (`.panelbox`): bordered card, `--surface` background,
  two colour-tinted border variants (`.k` orange-tinted, `.a` blue-tinted)
  used for paired comparisons (e.g. "shared vs declared", "design team vs
  client"), each with an h3 title, a mono uppercase subtitle, an
  em-dash-bulleted list, and a `.close` bold closing statement pinned to
  the bottom of the box via `margin-top:auto`.
- **Em-dash bullets**: every "big" bulleted list (`ul.big li`,
  `.panelbox li`) uses a CSS `::before { content:"—" }` in kicker-orange
  instead of a native list marker — a consistent, distinctive bullet
  style throughout.
- **Process/diagram components** — all built from plain CSS grid/flex,
  never images or SVG:
  - `.pipe` — horizontal 3-stage flow, mono 2-digit stage numbers, blue
    borders, orange "→" arrow glyphs between stages.
  - `.steps` — 5-column grid, each cell with a 3pt blue top rule, mono
    step number, h3, body copy.
  - `.horizon` — 4-column roadmap grid (now/next/then/future), each
    bordered card with a colour-coded mono label (green/blue/grey/orange
    in that order) — a maturity-stage pattern.
  - `.fam` — 2-column capability-family grid; each family has a mono
    uppercase title with a coloured 3pt top rule (4-colour cycle: orange/
    green/blue/violet) and a stack of label+status-tag rows separated by
    hairlines — the same 6-term tag vocabulary as above.
  - `.grid4` — plain 2×2 bordered card grid (h3 + p), used once for a
    "4 rules" page.
  - `.board` — 2-column component-library grid; each entry has a small
    coloured square swatch + mono uppercase name, a description line,
    and a screenshot figure; the page closes with a 6-column `.legend`
    grid spelling out the tag vocabulary in full prose (this is where
    "Selected / Available / Draft / Placeholder / Project-specific /
    Parked" are defined for a human reader — note this legend's wording
    doesn't map 1:1 onto the `.tag` CSS class names, e.g. "Draft" in the
    legend corresponds to the `.dr`/"being extended" tag).
- **Figures** (`figure`/`figcaption`): bordered, `--surface` background,
  image `object-fit: cover` (or `contain` inside the component board),
  caption overlaid as a bottom scrim (semi-opaque dark background, top
  hairline, mono text with a bold lead-in phrase). All images are **raster
  PNG screenshots of the product itself** (dashboard renders), referenced
  by relative path — never inline SVG, never mermaid, never base64.
- **No code blocks/chips** and **no dedicated callout/warning box**
  component exist in this genre — the closest analogue to a callout is
  the `.say` paragraph (bold lead-in + prose) or a tinted `.panelbox`.
  There is no icon system anywhere in the document.
- **`.defs`** (a 3-column definitions grid) is declared in the CSS but
  **not used anywhere in this exemplar** — likely a leftover/planned
  component from a sibling document in the same series; available for
  future use as a glossary block but not evidenced in actual page
  layout here.

## 5. Writing conventions

- **British English**, and explicitly declared: `<html lang="en-GB">`.
  Evidence in copy: "metres" (not "meters").
- **Sentence case** for every heading level (kickers are visually
  uppercase only via `text-transform: uppercase` in CSS — the underlying
  authored text is sentence case, e.g. "The issue", "Key drivers").
- **Headlines are full sentences with a full stop**, not noun-phrase
  titles — this is the single most load-bearing writing convention to
  reproduce: every h1 reads as a standalone declarative statement.
- **Date format**: `D Month YYYY`, no leading zero on single-digit days,
  full (unabbreviated) month name, four-digit year — e.g. "4 August
  2026". No ordinal suffixes ("4th").
- **Firm name always "Prior + Partners"** with spaces around the `+`.
- **Separator glyphs**: a middle dot with non-breaking spaces
  (`&nbsp;·&nbsp;`) joins same-tier items (firm / department / author,
  or family / colour terms); a pipe with spaces (`&nbsp;|&nbsp;`)
  separates distinct field-groups within the footer (e.g. attribution
  block | document title | date). An em dash separates title parts in
  `<title>` ("Masterplan+ — tool design brief") and is reused as the
  bullet glyph for `ul.big`/`.panelbox` lists.
- **Author identified only by initials** ("PNC"), never a full name —
  consistent with an internal working-document convention.
- No numeric-data formatting convention exists (no charts/stats
  tables); a future brief introducing numbers must define its own.

## 6. File naming convention

Exemplar filename: `masterplan_plus_tool_design_brief_v5_260804.html`

Pattern: `<product_name_snake_case>_<doc_type_snake_case>_v<N>_<YYMMDD>.html`

- Product name in snake_case; a `+` in the product name (e.g.
  "Masterplan+") becomes the word "plus" (`masterplan_plus`).
- Document type in snake_case, here `tool_design_brief` — this is the
  genre label to reuse verbatim for future documents of this exact
  format.
- Version as `v<integer>`, no zero-padding, no decimal point (`v5`, not
  `v5.0` or `v05`).
- Date as `YYMMDD`, six digits, no separators (`260804` = 2026-08-04),
  matching the "4 August 2026" prose date used inside the document.

**Asset folder convention** (evidenced by image `src` paths inside the
file): images live in a sibling folder `pages/brief_assets_<same
YYMMDD>/`, i.e. the asset folder's date stamp matches the HTML
filename's date stamp exactly, and is regenerated (new folder) on every
dated revision. Individual image files are named
`<two-digit-index>_<snake_case_description>.png`, e.g.
`21_dashboard_plan_night.png`, `40_board_intake_wiring.png` — the index
prefix appears to group related shots (the 40-series are all component-
board crops) rather than being strictly sequential page order.

## 7. Distinctive, recognisable traits

- **Dark-mode only** — no light theme, no `prefers-color-scheme`; a
  light-mode reproduction would not read as "same format".
- **Fixed 16:9 "HTML-as-slide-deck"** (1920×1080pt canvas per section,
  JS viewport-fit scaling, one-slide-per-PDF-page print) — the single
  most defining structural signature.
- GT America / GT America Mono two-voice type system (§2); five-part
  page rhythm kicker → sentence-headline → lead → body → footer (§3).
- The **6-term development-status vocabulary** (§4) applied identically
  on the component-library page and appendix inventory — the taxonomy,
  more than any visual rule, is what future briefs must preserve.
- Closing appendix swaps the running footer for a letterhead-style firm
  address + website — the document's implicit "back cover".
- No interactivity beyond the resize script; no external dependencies —
  fully self-contained single-file HTML (images by relative path).
