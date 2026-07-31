---
name: chunked_progress_monitoring
description: Before kicking off any long-running task (>5 min — bulk DB load, batch download, large file import, big spatial computation, multi-step pipeline, archive Range-fetch, mass row insert, etc.) ASK the user upfront how they want progress chunked AND notified, then arm a Monitor that streams one event per chunk completion. Trigger words include "bulk load", "batch import", "download all", "ingest history", "load many files", "ingest archives", "long-running", "loop over", "many rows", "many tables", "many archives". Never silently start a long task without offering chunked progress.
---

# Chunked progress monitoring

Use this skill **at the start** of any task expected to run longer than ~5
minutes. The pattern: ask the user once how they want progress reported,
arm a `Monitor` that emits one notification per chunk boundary, then proceed
with the work.

## 1. Decide if this applies

Long-running ⇒ any of:
- Bulk DB load (> ~100 files, > ~1 M rows)
- Downloads totalling > ~100 MB or > ~10 archives
- Range-fetching multiple remote ZIPs
- Spatial overlay / split / union over > 100 k geometries
- Looping over years, months, layers, forces, regions, tiles
- Anything where you'd otherwise tail a log for hours

If you cannot estimate a >5-min runtime, ask the user before proceeding.

## 2. Ask the user the chunking question — BEFORE launching the work

Use `AskUserQuestion` with options derived from the task's natural unit. Default
options to offer when relevant:

| Chunk key | When it makes sense |
|---|---|
| **By month / year** | data.police.uk archives, monthly drops, time-partitioned ingests |
| **By archive / ZIP** | multi-archive Range-fetches |
| **By file** | per-CSV / per-GPKG iteration |
| **By N rows** (e.g. every 100 k) | big single-table COPY or INSERT |
| **By table / layer** | multi-layer pipelines |
| **By force / LAD / region / tile** | UK-geographic batch jobs |
| **Milestones only** | start-of-archive + on-error + on-completion |
| **Silent** | no event stream, just notify on completion or failure |

Always include a "Milestones only" and "Silent" option. The user may not want
184 notifications.

Also ask about NOTIFICATION VOLUME if relevant:
- One event per chunk (default)
- Aggregate every N chunks
- Aggregate every M minutes

## 3. Implement the monitor

The Monitor tool's input is a Python or awk script that:

- Tails the foreground job's stdout/stderr file (the harness writes that to
  `~/AppData/.../tasks/<job-id>.output` — pass it as argv).
- Emits one **ASCII-only** line per chunk completion. Windows codepage cp1252
  cannot encode ✓ ❌ ▶ 🎉 — use `[done]`, `[FAIL]`, `[fetch]`, `[COMPLETE]`.
- Covers terminal states too (errors + completion), not only the happy path.

Reference Python template that worked for the data.police.uk bulk run:
`scripts/_monitor.py` in `Crime_Data_UK` repo. Reads the log line-by-line,
tracks a "current chunk" key, emits when the key changes.

Two file-handle-leak gotchas learned the hard way:

1. **Never call `setup_logger()` per chunk.** If the long task uses Python
   `logging`, ensure the logger is created once and reused — repeated
   `FileHandler` creation exhausts the Windows file-handle limit at ~5000
   opens. Set the logger init to be idempotent (check `logger.handlers`
   already populated; return early if so).
2. **OneDrive-mirrored log folders** compound the leak — OneDrive holds
   handles during sync. Keep per-run log files under a single timestamp,
   not one per chunk.

## 3.5 Output style — how to relay each event to the user

The raw Monitor output is for the assistant's eyes (e.g. `[fetch] [N/M] fetching X: Y`,
`[done] Y done - loaded A, skipped B`). When you relay it back to the user,
**rewrite each event into the per-chunk format below**. Don't dump the raw
monitor text.

For each `[fetch]` event from the monitor, emit ONE line:

```
`[N/M]` `(P%)` fetching `<archive>` for `<chunk-key>`.
```

For each `[done]` event, emit ONE line:

```
`<chunk-key> done` (loaded N, skipped M).
```

Add a **short contextual comment** on milestone events only — never on every
line. Examples (one-liner, append after the period):
- ` — fully fresh load.` when skipped count drops to 42 / first non-skip
- ` Entered 2019.` / ` Crossing into 2019.` on year boundaries
- ` Hash-skip done.` when the loader leaves the previously-loaded section
- ` Halfway.` at ~50%
- ` Almost done.` at >90%

Calculate `(P%)` from `N/M` rounded to integer (e.g. `47/108` → `(44%)`).

Format hygiene:
- Use Markdown inline-code backticks for `[N/M]`, archive names, and chunk keys.
- ASCII only — no emoji in the assistant reply either.
- ONE event per assistant turn = one line. Don't batch.
- Don't add metadata the user didn't ask for (no ETA per event, no rolling totals).

Worked example (the data.police.uk bulk-load thread used this style across
~180 month events):

```
`[37/108]` `(34%)` fetching `2023-03` for `2020-04`.
`2020-05 done` (loaded 87, skipped 42) — fully fresh load.
`[38/108]` `(35%)` fetching `2023-02` for `2020-03`.
`2020-04 done` (loaded 87, skipped 42).
…
`[41/108]` `(38%)` fetching `2022-11` for `2019-12`. Crossing into 2019.
`2020-01 done` (loaded 87, skipped 42).
`[42/108]` `(39%)` fetching `2022-10` for `2019-11`.
`2019-12 done` (loaded 87, skipped 42). Entered 2019.
```

If the user picked a non-month chunk key (rows, files, tables), adapt the
phrasing but keep the structure:
- "by N rows" → `[N rows / total]` `(P%)` ingesting <table>. <chunk> done (loaded N, skipped M).
- "by file" → `[N/M]` `(P%)` loading <filename>. <filename> done.
- "by table" → `[N/M]` `(P%)` loading <table>. <table> done (rows: N).

## 4. Launch sequence (literal)

```
1. AskUserQuestion("How would you like progress reported?", options=…)
2. Acknowledge their answer in plain text
3. Bash with run_in_background: true → start the long task
4. Monitor with persistent: true → emit chunk events
5. (Optional) ScheduleWakeup for an interim health-check
```

### Reference Monitor invocation (use this verbatim)

This is the exact pattern that worked for the Crime_Data_UK month-by-month
relay. Re-use it. Adjust only the description (task ID + project name), the
script path, and the output-file path.

```
Monitor(
  description    = "<short task name> month/chunk progress (<project> <task-id>)"
  persistent     = true
  timeout_ms     = 3600000          # max — covers ~hour-long stretches
  command        = "<abs path to python.exe>" -u \
                   "<abs path to monitor script>.py" \
                   "<abs path to the BACKGROUND TASK's stdout file>"
)
```

Concrete example (Windows, Crime_Data_UK):

```
"/c/Users/po.nienchen/AppData/Local/Programs/Python/Python313/python.exe" -u \
  "C:/Users/po.nienchen/OneDrive - priorpartners.com/Documents/05_Code_Scripts/Python/Crime_Data_UK/scripts/_monitor.py" \
  "C:/Users/POA9FF~1.NIE/AppData/Local/Temp/claude/<session-uuid>/tasks/<bg-task-id>.output"
```

The `-u` flag is essential — without it, Python's stdout buffering delays
events by minutes.

### Reference monitor script shape

`_monitor.py` tails the bg task's output file and emits one line per
chunk-boundary event, plus error and completion lines:

```python
# Sketch only — see Crime_Data_UK/scripts/_monitor.py for the working version.
LOG = Path(sys.argv[1])
cur = None
counts = {"loaded": 0, "skipped": 0}

with open(LOG, encoding="utf-8", errors="replace") as f:
    f.seek(0, 2)   # only LIVE events, not catchup spam
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.5); continue
        if m := FETCH_RE.search(line):
            print(f"[fetch] [{n}/{total}] fetching {name}: {months}", flush=True)
        elif ERROR_RE.search(line):
            print(f"[FAIL] {line.strip()}", flush=True)
        elif DONE_RE.search(line):
            flush_chunk()
            print(f"[COMPLETE] {line.strip()}", flush=True)
            sys.exit(0)
        elif m := BASENAME_RE.search(line):
            chunk = m.group(1)            # the chunk key (YYYY-MM, table, …)
            if chunk != cur:
                flush_chunk()
                cur = chunk
            if "Loaded " in line: counts["loaded"] += 1
            elif "unchanged since last load" in line: counts["skipped"] += 1

def flush_chunk():
    if cur is not None:
        print(f"[done] {cur} done - loaded {counts['loaded']}, "
              f"skipped {counts['skipped']}", flush=True)
        counts.update(loaded=0, skipped=0)
```

### Raw monitor output → user-facing relay

The Monitor emits exactly these 4 ASCII-only line types (`cp1252`-safe):

```
[fetch] [N/M] fetching <archive>: <chunk-key>
[done] <chunk-key> done - loaded N, skipped M
[FAIL] <stack-trace summary>
[COMPLETE] Done. N files processed, M rows loaded, K failures.
```

Each one becomes ONE assistant turn, formatted per §3.5.

When the long task finishes (auto-notify from the harness fires), do the
post-run checklist:
- Drop any temporary indexes you created with the user's approval
- Export any sidecar manifest / state to its archival location
- Compile-check + smoke-test the final DB / output state
- Report a concise final summary to the user

## 5. Pause / resume etiquette

The user may say "pause", "stop now", "I need the DB", "killing my laptop".
On any such signal:

- `TaskStop` BOTH the long task AND the monitor (separate task IDs).
- Confirm: no active DB sessions if it was a DB job; verify any locks released.
- Give the user the resume command (copy-paste shell snippet).
- Do NOT poll or check back automatically — the user owns timing.

When stale wake-ups fire after a pause, acknowledge and skip — never re-run
silently.

## 6. Re-arming after a transient failure

Network blips and VPN drops are common with corporate Postgres. Loader code
should ideally retry, but if it bails:

- Inspect the error before restarting (DNS failure ≠ DB constraint failure).
- Confirm the underlying cause is resolved (VPN back, server reachable).
- Restart the same command; idempotency in the long task should re-skip
  already-done chunks (hash-skip, source_file dedup, etc.).
- Re-arm the Monitor with the NEW task's output file.

## 7. Anti-patterns

- ❌ Starting a 4-hour bulk load with no Monitor and no scheduled check.
- ❌ Asking the user to tail a log file in another PowerShell — they want
  in-session updates.
- ❌ Streaming one event per CSV file when the user picked "by month".
- ❌ Per-chunk loggers (file-handle leak).
- ❌ Unicode in monitor output on Windows.
- ❌ Polling the DB while the loader is running — use the monitor stream.
