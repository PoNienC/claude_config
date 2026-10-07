# Prior + Partners — brand & document standard

Apply whenever you create, draft, or restyle ANY document, deliverable,
or piece of written material **for the user / Prior + Partners** —
Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF, a letter, memo,
technical note, agenda, minutes, report, proposal/bid, programme, or a
slide deck. The goal: anything that leaves the building looks and reads
like Prior + Partners.

This file is the detailed reference. Source of truth is
`P+P_Brand Guide_v1.pdf` and the live template files, both at:

`C:\Users\po.nienchen\OneDrive - priorpartners.com\Documents\06_References_Templates\Office_Templates\`

If the brand guide and this file ever disagree, the brand guide wins —
re-read it and flag the discrepancy.

---

## 0. Start from the official template, don't rebuild from scratch

Every template below already embeds the brand theme (colours + fonts),
paragraph/character styles, headers/footers and the logo. **Prefer
opening / duplicating the matching template over hand-building a blank
document.** Use the relevant Anthropic skill (`docx`, `pptx`, `xlsx`,
`pdf`) to do the editing, but seed it from the template.

| You're asked for…                     | Use this template                       | Format |
|---------------------------------------|-----------------------------------------|--------|
| Letter / letterhead                   | `P+P Letterhead v03.dotx`               | Word   |
| Memo                                  | `P+P Memo v03.dotx`                      | Word   |
| Technical note                        | `P+P Technical Note v03.dotx`           | Word   |
| Meeting agenda                        | `P+P Agenda v03.dotx`                    | Word   |
| Meeting minutes                       | `P+P Minutes v03.dotx`                   | Word   |
| Programme / Gantt                     | `P+P Programme.xltx`                     | Excel  |
| Slide deck / presentation             | `PP_Template.pptx` (live PowerPoint template; `PP_Template.pdf` is its reference render) | PPTX   |
| Long-form report / A4 portrait doc    | `A4_Portrait.pdf` (InDesign layout ref) | —      |
| Landscape report / A3                 | `A3_Landscape.pdf` (InDesign layout ref) | —      |

`.dotx` / `.xltx` are Office *templates*: they unzip like any OOXML
file. To reuse the theme in a fresh `.docx`, copy the template's
`word/theme/theme1.xml` (it is named **"P+P Brand theme"**) and the
named styles, or just start from a copy of the `.dotx` saved as `.docx`.

The two `.pdf` "templates" are the InDesign master-page references (the
firm's real long-form documents are built in InDesign). Mirror their
layout when producing an equivalent in another tool.

---

## 1. Colour

Quoted hex/RGB/CMYK are taken verbatim from `P+P_Brand Guide_v1.pdf`
§4. Where the actual Office "P+P Brand theme" baked into the `.dotx`
files uses a different value, both are given — **for digital Office
output use the theme value**, since that is what the template ships.

### Primary palette (default for non-project / in-house material)

| Name           | Brand-guide HEX | RGB           | CMYK            | Office theme slot |
|----------------|-----------------|---------------|-----------------|-------------------|
| P+P Orange     | `#e9511d` *(see note)* | 255 / 81 / 29  | 0 / 75 / 98 / 0   | accent1 `FF511D` |
| P+P Aubergine  | `#2b242c`       | 43 / 36 / 44   | 75 / 73 / 53 / 69 | dk2 `2B242C`     |
| P+P Cream      | `#f1eedf`       | 241 / 238 / 225| 7 / 5 / 15 / 0    | lt2 `F1EEDF`     |
| P+P Black      | `#121212`       | 18 / 18 / 18   | 0 / 0 / 0 / 98    | dk1 `121212`     |

*Orange note:* the brand guide prints `HEX #e9511d` but `RGB 255/81/29`
— those two don't match (255/81/29 = `FF511D`). The Office theme and the
PowerPoint/InDesign templates all use **`FF511D`**, which matches the
stated RGB. Use **`FF511D`** for any digital P+P Orange; treat `e9511d`
as a likely print-side artefact and confirm with the graphics team if a
print job hinges on it. Do not silently "correct" the guide.

### Secondary palette (when dominant orange would be too much — esp. collaborative projects)

| Name           | HEX        | RGB            | Office theme slot          |
|----------------|------------|----------------|----------------------------|
| P+P Lime green | `#dadf50` *(theme `DAE950`)* | 218 / 223 / 80 | accent4 `DAE950` |
| P+P Thistle    | `#c8b5e2`  | 200 / 181 / 226 | — (not in Office theme)    |
| P+P Matcha     | `#4bb400`  | 75 / 180 / 0    | accent3 `4BB400`           |
| P+P Plum       | `#920f67`  | 146 / 15 / 103  | accent6 `920F67`           |
| P+P Cobalt     | `#005dff`  | 0 / 93 / 255    | accent2 `005DFF` (= hyperlink) |
| P+P Berry      | `#ff2a8e`  | 255 / 42 / 142  | accent5 `FF2A8E`           |

White `#FFFFFF` = theme lt1; hyperlink = Cobalt, followed-link = Orange.

### Colour rules
- **Organisation colour-coding (Po directive, 24 July 2026): P+P is ALWAYS
  orange `FF511D` — the company colour — whenever documents, charts,
  legends, chips or ownership overlays are colour-coded by organisation.**
  Never assign P+P any other colour. Counterparties take contrasting
  palette colours (established pairing on Qiddiya Downtown: Buro Happold
  = green/Matcha `4BB400`-family; TBD/unconfirmed = neutral grey).
- **Accessibility:** text/icons on a solid background need ≥ 4.5:1 (AA);
  prefer ≥ 7:1 (AAA) for body text. Tested-good pairings from the guide:
  Lime/Aubergine, Thistle/Aubergine (AAA); Matcha, Orange on Aubergine
  (AA); Plum/Cream (AAA); Cobalt/Cream, Berry/Cream (AA, Berry needs
  ≥ 18 pt). **Careful with orange + berry together** — hard for
  colour-blind readers to tell apart.
- Prefer Cream, Aubergine or Black over white for digital backgrounds
  (white can dazzle; Aubergine/Black are also more energy efficient).
- A separate **land-use colour palette** exists (brand guide §4, marked
  `[tbc]` — Residential `#ffec4c`, Community `#de77c3`, Retail `#ff7fbc`,
  Open Space `#dadf50`, etc.). It is provisional; only use it for GIS /
  masterplan land-use drawings and confirm before relying on it.

---

## 2. Typography

- **Primary typeface: GT America** (GrilliType). The firm's voice; used
  for in-house material, bids, correspondence. Office theme: headings =
  **GT America Medium**, body = **GT America Light**. Also licensed:
  Light Italic, Ultra Light. **System fallback: Arial** (use if GT
  America is unavailable; never substitute anything else).
- **Secondary typeface: GT America Mono** (Light cut) — annotations,
  figures, running headers, footers, page numbers. **Use sparingly.**
  In the templates the mono cut is what sets the "Project title … 04"
  running head and the "Prior + Partners | date | page" footer.
- **Licence:** GT America is licensed to P+P only — **never share the
  font files with external partners**, and check with the graphics team
  before using GT America on project work with its own identity.
- **Tracking:** tight (−30) for display headlines/subheads; **0 for body
  and small text**. Never re-track text to cram more onto a page — edit
  the copy instead. Use automated leading / the template paragraph
  styles; don't hand-tune leading to fit.
- **Tabular figures:** GT America's tabular figures (slashed zero, wide
  1, narrow 8) are a brand feature — use them in tables and where
  numerals are a design element.

### Heading hierarchy (long-form documents)
L1 = section divider (large number above the title, title on a forced
line break beneath the number); L2, L3 (L3 aligns to the red guide),
L4, L5 sub-heads. Body text sits below the blue guide. Section numbers
run `01`, `01.1`, `01.1.1`, `01.0.1`, etc.

---

## 3. House style (writing conventions) — brand guide §11

- **Case:** sentence case throughout, **including titles and headers**
  ("Ambition and objectives", not "Ambition and Objectives").
- **Alignment:** left-align or centre. **Never right-align. Never
  justify.**
- **Dates:** `DD Month YYYY` — "28 February 2024". (Matches the global
  comment-date rule.)
- **Firm name:** "Prior + Partners" with a space either side of the `+`
  (not "Prior+Partners"). Only abbreviate to **"P+P" after** the full
  name has been introduced once.
- **Job titles:** title case — "Associate Director", not "Associate
  director".
- **Units:** `sqm` (not m² / m2), `sqkm` (not km²), `ha` (not Ha).
- **Numbers:** spell out **up to eleven** as words; **twelve and above**
  as numerals, in continuous text. Always numerals in "3-storey",
  "2-bed flat", "Phase 1". Comma after thousands: `1,287`.
- **Punctuation:** no double space after a sentence. Use a proper dash —
  **en dash with a space either side**, or **em dash with no space**.
  Full stop after "etc.".
- **Capitalised defined terms** (keep as proper nouns): Parameter Plans,
  Phase 1 Boundary, Outline Planning Permission, Design Code, Phase 1
  Reserved Matters, The Consented Scheme, Development Zones, Development
  Specifications. **Road / Street** spelled out in full (not Rd / St).
  **Directions lower case** (north, east…); "northeast" / "southwest"
  one word.
- **Place vs authority:** spell out the place when describing it (e.g.
  "London Borough of Newnham"); use the abbreviation (LBN) when
  referring to the Planning Authority.
- **Standard abbreviations:** DRP (Design Review Panel), LBN (London
  Borough of Newnham), DAS (Design and Access Statement), HPA (Hybrid
  Planning Application), AOD (Above Ordnance Datum), NPPF (National
  Planning Policy Framework), SPD (Supplementary Planning Document).
- British English throughout (centre, colour, organise) — consistent
  with the global rule.

---

## 4. Logo — brand guide §3

- **Logotype** ("PRIOR / +PTNRS", full name) is the primary identifier —
  default choice. **Marque** (the P+P symbol) only for small / tight
  spaces (social avatars) or where P+P is already obvious.
- **Clear / safe area:** at least the width of the "+" around every edge
  of the logotype; nothing may encroach. Marque in a circle: left-align
  the P to the centre line, size from the height of the P.
- **Minimum size:** print 12 mm high; digital 25 px. **Standard size:**
  A4 14 mm high, A3 16 mm high.
- **Colour:** use the black, white, or orange logo only. On any other
  background colour, use **only white or black**.
- **Placement:** centred → nudge optically left; left-aligned → align
  "Prior"/"Partners" to the left text margin.
- **Co-branding:** centre-align partner logos with ours, ~double safe
  area between; size ours so it doesn't dominate but isn't lost.

---

## 5. Document layout & components (A4/A3 long-form, and slides)

- **Covers:** two background options — **Aubergine** or **Cream**. Front
  and back covers **must match**. Cover carries a bespoke **pattern**
  built from the P+P Pattern font (positive + negative layers, orange /
  grey geometric shapes) — edit it per project.
- **Cover meta:** Project name (bold) / Document name; "Issued by Prior
  + Partners alongside Company A, B, C"; `DD Month YYYY`.
- **Running header:** project title on the left, page number on the
  right, set in GT America Mono. Footer (slides): "Prior + Partners |
  date | page no" in mono.
- **Grid:** 6 columns × 6 rows, 4 mm gutters, on a 2 mm document grid.
- **Lists:** L1 bullets use an em-dash "—"; L1 numbers use `01 02 03`;
  L2 (sub-list) uses an arrow "→". L2 nests under either L1 style.
- **Captions & annotations:** **no rounded corners anywhere.** Filled
  background → **centred** text; transparent background → **left-aligned**
  text. Leader lines orthogonal only (no diagonals). Figure captions may
  carry "Fig 01.1". Annotation/label styles are consistent across a doc.
- **Tables & keys:** use the P+P table / key styles; tabular figures;
  tables in running text sit below the blue guide. **Never paste Excel
  screenshots into a deck/document** — rebuild the table natively.
- **Back-cover address block:**
  Prior + Partners, 70 Cowcross Street, London EC1M 6EJ.
  +44 (0)20 3951 0052 · priorandpartners.com.
  Always refresh the named project contact before issue.

### Slide text-size precedents (PowerPoint)
One big message → largest display style; one long/few sentences → next
size down; lists only → list size; lists + images → smaller list size.
When several images share a slide, keep the margin and footer visible.

---

## 6. Tone of voice — brand guide §2

Public-spirited, collaborative, optimistic, leadership-minded. Say what
we're **for**, not against; what we **do**, not what we don't. Plain,
jargon-free, accessible language. Optimistic but honest about challenge.
Respectful and unbiased about people, communities and cultures.
Recognise partners and collaborators. Prioritise storytelling over
listing facts. Strapline: *"Unlocking the potential of places and
communities around the globe."*

---

## 7. When something isn't covered here

Don't invent brand values. Re-read `P+P_Brand Guide_v1.pdf`, inspect the
relevant template, or ask the user / graphics team. Flag any gap rather
than guessing — same source-fidelity discipline as the rest of this
config.

---

## 8. Tooling gotchas

- **Word's PDF and XPS export can swap GT America for Calibri** (found
  16 September 2026 on Po's laptop). There GT America is installed per
  user only (HKCU font registry, `%LOCALAPPDATA%\Microsoft\Windows\Fonts`).
  Word sees the fonts and lays pages out in GT America, but
  `ExportAsFixedFormat` to PDF (17) and XPS (18) draws Calibri glyphs —
  including for the untouched `P+P Technical Note v03.dotx`. Proven by
  matching rendered text widths to Calibri within 0.1 pt. That breaks
  the Arial-only fallback rule, so:
  - use such exports for pagination and structure only;
  - to see the real typeface, render pages with Word COM
    `ActiveWindow.Panes(1).Pages(i).EnhMetaFileBits` played back to PNG;
  - warn Po before sending a PDF made on that machine. The likely fix
    is a machine-wide font install by IT.
- **PowerPoint's PDF export has the same fault** (checked 19 September
  2026: `SaveAs` 32 on `PP_Template.pptx` embedded only Calibri).
  Workaround that keeps the real GT America, verified the same day:
  PowerPoint COM `PrintOptions.ActivePrinter = "Microsoft Print to PDF"`,
  `PrintInBackground = 0`, `FitToPage = -1`, then
  `PrintOut(from, to, "<out.pdf>")` — the file name stops the save
  dialog. The driver paper is US Letter, so crop the page back to the
  slide with PyMuPDF `show_pdf_page(clip=...)` (find the slide from a
  known filled shape). Result: vector, text selectable, four GT America
  cuts embedded, render matching PowerPoint's own PNG export.
- **`PP_Template.pptx` facts:** canvas 26.67 x 15 in; layouts Aubergine,
  White, Cream, Black, Orange; 6 x 6 grid with 0.555 in margins,
  4.033 in columns, 0.267 in gutters, rows every 2.222 in; content
  titles 42 pt `+mj-lt`; table headers and keys in capitals, 24 pt
  `+mj-lt`, with a 1 pt top rule and 0.25 pt row rules; footer
  "Prior + Partners | date | page" in 16 pt GT America Mono Light. Its
  date placeholder is an auto-updating field — replace it with fixed
  text for an issued document.
- **An empty paragraph after a document's last table** can spill onto a
  blank final page. Collapse it to a 1 pt exact line.
- **A table heading kept in a separate table** can strand at a page
  foot. Set keep-with-next on every paragraph except those in the
  table's last row.
- **`P+P Technical Note v03.dotx` embeds a GT America font file**
  (`word/fonts/font1.odttf`, a `w:embedRegular` entry in
  `fontTable.xml`, `w:embedTrueTypeFonts` in `settings.xml`). Found
  23 September 2026 while building a candidate test brief: every
  document made from the template carries the licensed font. For
  anything going outside P+P, drop `word/fonts/*` and
  `word/_rels/fontTable.xml.rels`, remove the `w:embed*` elements and
  `w:embedTrueTypeFonts`, and set the fonts to Arial (the brand
  fallback) so Word's PDF export stays faithful. Worked example:
  `make_base()` in `Documents/08_Personal/Hire/gis_consultant_take_home_test/03_build/build_documents.py`.
