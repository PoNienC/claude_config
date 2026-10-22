---
name: message_dual_draft
description: Write or refine a Slack, Teams or other chat message with two drafters — Claude and Codex each draft it independently, each reviews the other's draft, and Claude merges the best into one final, paste-ready message (Slack / Teams paste rule — "• " bullets, plain-text titles, no markdown) with a few highlight bullets. Use EVERY time the user asks to write, draft, reply to, answer, rewrite, polish, refine, shorten or improve a Slack or Teams message, post, thread reply, announcement, DM or other chat message (WhatsApp, LinkedIn, text), in either account. Emails use email_dual_draft instead.
---

# Message — Claude + Codex draft, cross-review, merge

Request: $ARGUMENTS (if empty, the message request in the conversation)

In short: the user always gets ONE final message, ready to paste into
Slack or Teams, and at most four short bullets. Drafts, briefs and
reviews stay in the work folder unless the user asks to see them.

## Fixed conventions

- **Skill dir** = the base directory shown when this skill loaded; the
  skills folder is its parent.
- **Work folder** `<work>` = `<session scratchpad>/message_<yymmdd_hhmm>`
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
- **Slack / Teams paste rule** (the user's global setting, 22 October
  2026) — binding for both drafters and the final:
  - Lists use the `• ` bullet character, never `- ` or `*` (those paste
    as plain text in Slack).
  - Section titles are plain text on their own line.
  - No markdown at all: no `#`, `**`, `_`, backticks or `>` quotes.
  - One paragraph is one line — no line breaks inside a paragraph.
    Breaks only between paragraphs, between list items and after a
    title.
- **Message style** for both drafters (written into every brief):
  British English; shorter and more direct than an email — lead with
  the point or the ask; no subject line; a greeting only if the thread
  uses one; keep every fact, name, date, number, link and @mention
  exactly as given; never invent facts, promises or deadlines — put
  `[placeholder]` where something is missing; match the channel's tone
  (a DM, a team channel, a client channel); no emoji unless the user or
  the thread uses them; Prior + Partners conventions where they apply
  ("Prior + Partners", dates DD Month YYYY).
- **What goes to Codex:** only the text the message needs (the request,
  the thread or draft, key facts). Codex runs on the account signed in
  on this machine.

## Steps

1. **Brief.** Collect the request verbatim, the full source text
   (thread, draft or notes), where it will be posted (Slack or Teams;
   channel, thread or DM) and to whom, the tone, the length, and
   anything that must be said or avoided. Ask one question only if the
   purpose or the audience is truly unclear; otherwise assume and note
   the assumption. Fill `templates/codex_message_draft.md` →
   `<work>/codex_draft_brief.md` and launch Codex (output
   `<work>/codex_draft.md`) **now**.
2. **Your draft (A).** Write your own draft independently — do not read
   Codex's output first. Save it as `<work>/draft_a.md`.
3. **Cross-review.**
   - Fill `templates/codex_message_review.md` with draft A →
     `<work>/codex_review_brief.md`; launch Codex (output
     `<work>/codex_review.md`) in the background.
   - When Codex's draft (B) arrives, review it yourself with the
     checklist below: what does B do better than A, and what is wrong
     in B?
4. **Merge.** Once both Codex outputs are in: start from the stronger
   draft, take the better parts of the other, apply the review points
   you accept (from Codex on A, and yours on B), check every fact
   against the source, then run the checklist once more — the paste
   rule last. Save the final as `<work>/final.md`.
5. **Reply** in the format below.

Checklist: the point or ask in the first line · facts, names, dates,
links and @mentions match the source · days of the week match their
dates (check the calendar) · no promise or deadline the user did not
give · short enough for the channel · tone right for the audience ·
British English · paste rule: `• ` bullets, plain-text titles, no
markdown, one paragraph per line · placeholders marked.

## Reply format

- First line: one-line result, e.g. "Final Slack reply to the team
  thread below, merged from both drafts."
- The final message in one fenced `text` block, ready to paste — it
  follows the paste rule exactly.
- Then at most four very short bullets:
  - **Highlights:** the one or two key choices (tone, structure, the ask).
  - **Merged:** what came from Claude's draft and what from Codex's.
  - **Changed in review:** the main fix from the cross-review.
  - **Check:** placeholders or assumptions, only if there are any.
- Nothing else. Show drafts A and B or the reviews only if asked.
