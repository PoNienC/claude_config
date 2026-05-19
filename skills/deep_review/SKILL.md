---
name: deep_review
description: Run a three-dimensional parallel code review on staged changes — security, performance, and style. Synthesises a prioritised findings summary. Use before every non-trivial commit. Trigger phrases: "deep review", "review before commit", "pre-commit check".
disable-model-invocation: true
context: fork
---

# Deep Review — Three-Dimensional Parallel Code Review

Run the following three reviews in parallel against current staged changes.

## 1. Security Review

Use the security-reviewer agent. Check for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication and authorisation flaws
- Sensitive data exposure
- Insecure defaults or hardcoded credentials
- For spatial code: unsafe SQL construction, unsanitised geometry inputs

## 2. Performance Review

Check for:
- N+1 queries or repeated expensive operations
- Memory leak risks (unclosed connections, unbounded accumulation)
- Blocking operations in async contexts
- Unnecessary recomputation (missing memoisation or caching)
- For spatial code: missing spatial indexes, ST_Distance predicates instead of ST_DWithin, unfiltered raster reads

## 3. Style Review

Check for consistency with the existing codebase:
- Naming conventions (snake_case for Python/SQL, camelCase for JS)
- Unused imports and dead code
- Comment quality — does it explain WHY, not WHAT
- British English in user-facing strings and docstrings
- For spatial code: explicit SRID declarations, COMMENT ON TABLE present

## Output Format

Merge findings from all three dimensions into a single prioritised list:

1. 🔴 **Critical** — must fix before merging
2. 🟡 **Warning** — recommended fix
3. 🔵 **Info** — optional improvement

Each item includes a `file:line` reference and a specific fix suggestion.

## `/ultrareview` — Cloud Multi-Agent Review

For large or security-sensitive changes, use `/ultrareview` instead:

```
/ultrareview           # reviews current branch vs main
/ultrareview <PR-num>  # reviews a specific GitHub PR
```

| | Local Deep Review | `/ultrareview` |
|---|---|---|
| Runs | Locally | Anthropic cloud fleet |
| Time | Immediate | 5–10 minutes |
| Cost | Subscription quota | 3 free (Pro/Max), then $5–20/run |
| Use for | Daily pre-commit | Large PRs, security-critical changes |

## Gotchas

- **Only staged changes are reviewed.** Run `git add` before invoking. Unstaged modifications are out of scope.
- **All three agents must complete** before the report is synthesised. If one times out, output partial results and mark as "partial review".
- **Security reviewer reads the full file**, not just the diff. Related vulnerabilities outside the diff will be flagged.
- **Changes to `.claude/` are flagged automatically** — these are system instructions and any modification carries security implications.
- **Do not propose rewrites** — this is a review, not a refactor. Critical items must be genuine blockers.
