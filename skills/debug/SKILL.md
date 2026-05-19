---
name: debug
description: Systematic debug workflow — capture the error, isolate the scope, form hypotheses, test with evidence, apply a minimal fix, verify. Use when you have an error message, stack trace, test failure, or unexpected behaviour. Trigger phrases: "debug this", "why is this failing", "help me fix this error".
disable-model-invocation: true
context: fork
---

# Debug — Systematic Debugging

## When to use

- Error message or stack trace present
- Test failing
- Unexpected or non-deterministic behaviour
- Production anomaly (log spikes, silent failures)

## Six-step process

1. **Capture** — Get the full error message, stack trace, and reproduction steps. Do not start without these.
2. **Isolate** — Narrow the fault to a module, function, or time window.
3. **Hypothesise** — Form 2–3 plausible root cause hypotheses. Write them down.
4. **Test** — Verify each hypothesis with evidence from tool calls. Do not act on intuition.
5. **Fix** — Apply the minimal fix. Do not clean up unrelated code.
6. **Verify** — Confirm the fix works. Confirm no new problems were introduced.

## Quick diagnostic commands

```bash
# What changed recently?
git log --oneline -10
git diff HEAD~3

# Search logs for error patterns
grep -rn "error\|Error\|ERROR" logs/ 2>/dev/null | tail -20

# Run the failing test only (not the full suite)
pytest tests/test_specific.py -x --tb=short   # Python
npm test -- --testPathPattern=specific         # Node
go test ./pkg/specific/...                     # Go
```

## Spatial pipeline diagnostics

```bash
# PostGIS: check for invalid geometries
psql -c "SELECT id FROM your_table WHERE NOT ST_IsValid(geom) LIMIT 10;"

# PostGIS: check CRS mismatch
psql -c "SELECT ST_SRID(geom), count(*) FROM your_table GROUP BY 1;"

# GDAL: inspect a raster or vector file
gdalinfo /path/to/file.tif
ogrinfo -al -so /path/to/file.gpkg

# Check spatial index exists
psql -c "\d your_table"   # look for gist index on geom column
```

## Log analysis

```bash
# Most recent errors with context
grep -B 5 -A 10 "ERROR" /var/log/app.log

# Error frequency by type
grep -oE "Error: [^:]*" app.log | sort | uniq -c | sort -rn

# Errors in a time window
awk '/2026-05-18 14:/ && /ERROR/' app.log
```

## Common error patterns

| Pattern | Points to | Action |
|---------|-----------|--------|
| NullPointer / AttributeError / KeyError | Missing null check or wrong key | Add defensive check |
| Timeout | Slow dependency or missing index | Add timeout + retry; check query plan |
| Connection refused | Service not running | Check health endpoint |
| CRS mismatch / wrong coordinates | SRID not set or wrong projection | Validate CRS before join |
| OOM / MemoryError | Unbounded data load | Use streaming or chunked reads |
| Rate limit | Too many requests | Add backoff and queue |

## Cross-system correlation (SQL)

```sql
-- Error frequency by endpoint
SELECT endpoint, count(*) AS errors
FROM logs
WHERE level = 'ERROR' AND time > NOW() - INTERVAL '1 hour'
GROUP BY endpoint ORDER BY errors DESC;

-- Trace a request across services
SELECT service, message, time
FROM logs
WHERE request_id = 'req-xxxxx'
ORDER BY time;
```

## Output format

```
## Debug Report

**Issue:** [one-sentence description]
**Root Cause:** [actual root cause found]

### Evidence
- [specific evidence 1 — file:line or log excerpt]
- [specific evidence 2]

### Fix
[minimal code or config change]

### Verification
[command or test that confirms the fix works]

### Prevention
[how to prevent this class of failure recurring]
```

## Gotchas

- **Minimal fix only** — debug is not refactoring. Do not touch code outside the fault scope.
- **Every hypothesis needs evidence** — verify with a tool call, not intuition.
- **Run the specific failing test first** — not the full suite. Confirm direction before investing time.
- **Record the root cause** — write it in the commit message so future retros have context.
