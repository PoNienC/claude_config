---
name: email_dual_draft
description: Write or refine an email with two drafters — Claude and Codex each draft it independently, each reviews the other's draft, and Claude merges the best into one final version with a few highlight bullets. Use EVERY time the user asks to write, draft, reply to, answer, forward, rewrite, polish, refine, shorten or improve an email (a new email, a reply to a pasted thread, or a pasted draft), in either account.
---

# Email — Claude + Codex draft, cross-review, merge

Request: $ARGUMENTS (if empty, the email request in the conversation)

In short: the user always gets ONE final email, ready to paste, and at
most four short bullets. Drafts, briefs and reviews stay in the work
folder unless the user asks to see them.

## Fixed conventions

- **Skill dir** = the base directory shown when this skill loaded; the
  skills folder is its parent.
- **Work folder** `<work>` = `<session scratchpad>/email_<yymmdd_hhmm>`
  (system temp folder if there is no scratchpad). Never in OneDrive, a
  repo or a network drive. Create `<work>/codex_repo` and run
  `git init` in it once — Codex needs a git folder to run in.
- **Codex** runs through the dual_dev launcher, read-only, in the
  background (`run_in_background: true`):
  - Windows (PowerShell tool):
    `& "<skills>\dual_dev\scripts\run_codex.ps1" -Mode plan -Repo "<work>\codex_repo" -BriefFile "<brief>" -OutFile "<out>" -Effort medium`
  - macOS (Bash tool):
    `bash "<skills>/dual_dev/scripts/run_codex.sh" --mode plan --repo "<work>/codex_repo" --brief "<brief>" --out "<out>" --effort medium`
  - Exit 0 = use the output file. Exit 1 or 2, a missing launcher, or a
    `CODEX USAGE` line above 80%: say so in one line and give a
    Claude-only version (still reviewed by you against the checklist).
- **Email style** for both drafters (written into every brief):
  British English; ready to paste — one paragraph is one line, no line
  breaks inside a paragraph; a new email starts with `Subject: …`;
  plain, warm and concise; keep every fact, name, date, number and
  attachment exactly as given; never invent facts, promises or
  deadlines — put `[placeholder]` where something is missing; match the
  thread's tone and greeting style when replying; Prior + Partners
  conventions where they apply ("Prior + Partners", dates DD Month YYYY,
  sentence case).
- **What goes to Codex:** only the text the email needs (the request,
  the thread or draft, key facts). Codex runs on the account signed in
  on this machine.

## Steps

1. **Brief.** Collect the request verbatim, the full source text
   (thread, draft or notes), the recipient and relationship, the tone,
   the length, and anything that must be said or avoided. Ask one
   question only if the purpose or the recipient is truly unclear;
   otherwise assume and note the assumption. Fill
   `templates/codex_email_draft.md` → `<work>/codex_draft_brief.md` and
   launch Codex (output `<work>/codex_draft.md`) **now**.
2. **Your draft (A).** Write your own draft independently — do not read
   Codex's output first. Save it as `<work>/draft_a.md`.
3. **Cross-review.**
   - Fill `templates/codex_email_review.md` with draft A →
     `<work>/codex_review_brief.md`; launch Codex (output
     `<work>/codex_review.md`) in the background.
   - When Codex's draft (B) arrives, review it yourself with the
     checklist below: what does B do better than A, and what is wrong
     in B?
4. **Merge.** Once both Codex outputs are in: start from the stronger
   draft, take the better parts of the other, apply the review points
   you accept (from Codex on A, and yours on B), check every fact
   against the source, then run the checklist once more. Save the final
   as `<work>/final.md`.
5. **Reply** in the format below.

Checklist: purpose clear in the first two lines · facts, names, dates
and numbers match the source · days of the week match their dates
(check the calendar) · no promise or deadline the user did not give ·
one clear ask or next step · tone right
for the recipient · no padding · British English · ready-to-paste line
breaks · placeholders marked.

## Reply format

- First line: one-line result, e.g. "Final reply to Sarah below, merged
  from both drafts."
- The final email in one fenced `text` block, ready to paste.
- Then at most four very short bullets:
  - **Highlights:** the one or two key choices (tone, structure, the ask).
  - **Merged:** what came from Claude's draft and what from Codex's.
  - **Changed in review:** the main fix from the cross-review.
  - **Check:** placeholders or assumptions, only if there are any.
- Nothing else. Show drafts A and B or the reviews only if asked.
