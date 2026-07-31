"""Progress relay for the pp_di_network_simplification skill (optional).

Tails the output file of a backgrounded `run_simplification.py` job (path given
as argv[1]) and emits one tidy ASCII line per event, suitable for streaming back
to the user via a Monitor tool. Exits when the run completes.

Used only when a Monitor tool is available. If it is not, the skill falls back to
reading the output file periodically — see SKILL.md Step 5.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

if len(sys.argv) < 2:
    print("[FAIL] _progress_monitor.py: missing output-file path argument", flush=True)
    sys.exit(2)

LOG = Path(sys.argv[1])
for _ in range(120):  # wait up to ~60s for the file to appear
    if LOG.exists():
        break
    time.sleep(0.5)
else:
    print(f"[FAIL] output file never appeared: {LOG}", flush=True)
    sys.exit(2)

CHUNK = re.compile(r"^\[(\d+)/(\d+)\]\s+(chunk_\S+)\s+simplified:\s+([\d,]+)\s*->\s*([\d,]+)\s*\(-([\d.]+)%\)")
FALLBACK = re.compile(r"^\[(\d+)/(\d+)\]\s+(chunk_\S+)\s+FALLBACK")
SAVED = re.compile(r"^Saved\s+(\S+)\s+\(([\d,]+)\s+rows\)")
DONE = re.compile(r"^=== SIMPLIFICATION COMPLETE in ([\d.]+) min ===")
ERROR = re.compile(r"^!!! ERROR")
PHASE = re.compile(r"^(Network downloaded:|Buildings:|Final network:|Unlinks:|Built \d).*")


def emit(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> None:
    with open(LOG, encoding="utf-8", errors="replace") as f:
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            line = line.rstrip("\n")

            if m := CHUNK.match(line):
                idx, total, cid, n_in, n_out, pct = m.groups()
                p = round(int(idx) / int(total) * 100)
                emit(f"[{idx}/{total}] ({p}%) {cid} done: {n_in} -> {n_out} (-{pct}%)")
            elif m := FALLBACK.match(line):
                idx, total, cid = m.groups()
                emit(f"[{idx}/{total}] {cid} FALLBACK (kept originals — harmless)")
            elif m := SAVED.match(line):
                name, rows = m.groups()
                emit(f"[save] {name} ({rows} rows)")
            elif PHASE.match(line):
                emit(f"[phase] {line}")
            elif ERROR.match(line):
                emit(f"[FAIL] {line}")
            elif m := DONE.match(line):
                emit(f"[COMPLETE] finished in {m.group(1)} min")
                sys.exit(0)


if __name__ == "__main__":
    main()
