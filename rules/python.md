# Python rules (global within this repo)

These apply to every Python file. No `globs:` frontmatter — always loaded.

- Type hints on every public function. Internal helpers may skip them if obviously typed.
- Module docstring on every file describing the spatial input/output CRS and the data layer (`data_ingestion`, `preprocessing`, etc.).
- Use context managers for PostGIS connections, file handles, and ArcPy cursors.
- Relative paths only. Use `pathlib.Path` over `os.path`.
- British English in docstrings, comments, and user-facing strings.
- Never `print()` for anything other than CLI output — use `logging`.
- Don't catch bare `Exception` unless re-raised with context.
- Prefer `psycopg.Connection` with `dict_row` factory for explicit column access.
