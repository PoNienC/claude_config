---
name: perf
description: Performance analysis and optimisation — measure baseline, identify the bottleneck, fix the highest-impact item, verify improvement. Use when an application is slow, an API times out, or spatial processing exceeds acceptable thresholds. Trigger phrases: "why is this slow", "optimise this query", "performance issue".
disable-model-invocation: true
context: fork
---

# Perf — Performance Engineering

## When to use

- Application or API response is slow
- PostGIS query exceeds acceptable runtime
- Raster or vector processing is a bottleneck
- Core Web Vitals failing (LCP / FID / CLS)
- Considering infrastructure scaling — check software headroom first

## Four-step process

1. **Measure** — Establish a baseline before touching anything. No baseline = guessing.
2. **Identify** — Find the largest bottleneck using the 80/20 principle. Fix the one thing causing 80% of the problem.
3. **Optimise** — Apply one fix at a time. Multiple simultaneous changes make causality impossible to establish.
4. **Verify** — Re-run the same measurement. Confirm improvement with numbers, not impressions.

## Profiling commands

```bash
# Python
python -m cProfile -o output.prof script.py
python -m pstats output.prof

# Node.js
node --prof app.js
node --prof-process isolate-*.log > profile.txt

# CLI comparison (requires hyperfine)
hyperfine 'command_a' 'command_b' --warmup 3

# PostGIS query plan
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

## Spatial-specific diagnostics

```sql
-- Find slow queries (requires pg_stat_statements)
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 20;

-- Check if spatial index is being used
EXPLAIN SELECT * FROM your_table WHERE ST_Intersects(geom, ST_MakeEnvelope(...));
-- Look for "Index Scan using your_table_geom_idx" — if absent, index is missing or not being used

-- Table bloat check
SELECT relname, n_dead_tup, n_live_tup
FROM pg_stat_user_tables WHERE relname = 'your_table';

-- Geometry complexity (high vertex count = slow rendering/processing)
SELECT id, ST_NPoints(geom) AS vertices FROM your_table ORDER BY vertices DESC LIMIT 10;
```

## Common bottlenecks

### Database / PostGIS
- Missing spatial index — add `CREATE INDEX ON table USING GIST (geom);`
- N+1 queries — use JOIN or batch fetch
- `ST_Distance < x` predicate — replace with `ST_DWithin(geom, target, x)` (uses index)
- Large result sets with no LIMIT — add pagination
- Geometry too complex — use `ST_Simplify` for display-only contexts

### Memory
- Memory leak — check unclosed DB connections, unbounded in-memory accumulation
- Large object buffering — use streaming / chunked reads
- Cache without TTL — add expiry

### CPU
- Synchronous blocking in async context — make async
- Repeated expensive computation — add memoisation
- Unnecessary reprojection per row — project once, then process

### Network / I/O
- Too many small requests — batch or consolidate
- Oversized payload — compress, paginate, or use streaming
- No HTTP caching — add cache headers or CDN

## Performance targets (reference)

| Metric | Target | Notes |
|--------|--------|-------|
| API response | <200ms P95 | Excluding network RTT |
| PostGIS spatial join | <1s for <1M rows | With GIST index present |
| Page load (4G) | <1s TTI | Time to Interactive |
| LCP | <2.5s | Largest Contentful Paint |
| FID / INP | <100ms | Interaction response |
| Bundle size | <500KB gzip | JS bundle |

## Output format

```
## Performance Report

**Before:** [baseline measurement]
**After:**  [post-optimisation measurement]
**Improvement:** [% or ms improvement]

### Bottlenecks Identified
1. [problem] — Impact: High / Medium / Low

### Optimisations Applied
1. [change] → [measured result]

### Remaining Headroom
[what else could be improved but was not addressed this time]
```

## Gotchas

- **No optimisation without a baseline** — if you cannot measure it, you cannot improve it.
- **One change at a time** — otherwise you cannot determine which change had which effect.
- **Re-run under identical conditions** — same data volume, same hardware, same load.
- **Do not optimise prematurely** — confirm the bottleneck is real before spending time on it.
