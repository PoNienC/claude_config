---
globs: notebooks/**/*.ipynb
---

# Notebook rules

Loaded only when working inside `notebooks/`.

## Purpose
Notebooks are for **exploration and one-off analysis**, not production code. Anything reusable should be promoted to a module under `python/`.

## Hygiene
- First cell is markdown: title, author, date, and the question being explored.
- Second cell imports — keep them minimal.
- No hard-coded paths to local data — use `pathlib.Path` with environment variables or a known relative root.
- Strip outputs before committing (`nbstripout` runs as a post-edit hook automatically).

## Anti-patterns to flag
- Long notebooks (> 50 cells) — propose splitting or promoting to a module.
- Side-effecting cells that mutate the database without a guard (`if CONFIRMED:`).
- Display-only reprojections that get reused elsewhere — promote the function.

## Reproducibility
- Pin random seeds at the top.
- Note the PostGIS database name and CRS used in the title cell.
