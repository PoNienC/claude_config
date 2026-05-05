---
description: Run format, lint, tests, then prepare a commit. Stops on any failure.
allowed-tools: Bash(black:*), Bash(ruff:*), Bash(pytest:*), Bash(git:*), Read
---

# /ship

Run the project's pre-commit pipeline and prepare a commit message. Halt on any failure — never push past a broken test.

## Steps

1. **Format**
   ```bash
   black python/ arcpy/ pyqgis/ 2>/dev/null || true
   ruff check --fix python/ arcpy/ pyqgis/
   ```

2. **Lint** (no auto-fix this time)
   ```bash
   ruff check python/ arcpy/ pyqgis/
   ```
   If errors, stop and report.

3. **Tests**
   ```bash
   pytest -x --tb=short
   ```
   If any test fails, stop and surface the failure. Do not proceed.

4. **Inspect changes**
   ```bash
   git status --short
   git diff --stat
   ```

5. **Compose commit message**
   - Imperative present tense ("Add CRS validator", not "Added" or "Adds").
   - First line ≤ 72 characters.
   - Body explains *why*, not *what* — the diff shows what.
   - If the change touches a layer naming convention, the OWL/PostGIS boundary, or CRS handling, mention it explicitly.
   - British English.

6. **Show the proposed commit and stop.**
   Do not run `git commit` automatically — the user confirms via the main session. Per `settings.json` the commit itself is gated by an `ask` permission.

## Failure modes
If the working tree is clean, output "nothing to ship" and exit. If the user is on `main` and the change is non-trivial, suggest creating a feature branch first.
