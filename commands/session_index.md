---
description: List every Claude Code session across all project folders and both profiles
---

Run the session indexer and report the result.

```
py -3 "C:\Users\po.nienchen\.claude\scripts\session_index.py" --top 30 $ARGUMENTS
```

Then tell me:

- how many sessions and project folders were found
- the absolute path of the HTML index
- the newest 10 sessions with their project folder

Useful arguments: `--top 0` prints every session; `--config-dir <path>` limits
the scan to one profile.
