"""Index every Claude Code session across all profiles and project folders.

Not spatial. Data layer: local Claude Code transcript store
(`<config_dir>/projects/<slugified_cwd>/<session_id>.jsonl`).

VS Code scopes the session picker to the folder that is open, so sessions run
in another folder are invisible even though they are on disk. This walks every
profile and every project folder and produces one list: title, project folder,
when it ran, and the exact command to resume it.

Outputs a console table, a CSV, and a searchable HTML index.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Only these record types are parsed; everything else is skipped by a substring
# pre-filter so multi-megabyte transcripts stay cheap to scan.
TITLE_KEYS = ('"type": "custom-title"', '"type":"custom-title"',
              '"type": "ai-title"', '"type":"ai-title"',
              '"type": "last-prompt"', '"type":"last-prompt"')
MAX_PARSE_LEN = 4000  # title records are tiny; never parse a giant tool result


def _iter_session_files(config_dir: Path) -> Iterator[tuple[str, Path]]:
    """Yield (project_slug, jsonl_path) for real sessions only.

    Depth-1 files only - nested `subagents/` and `workflows/` transcripts are
    not resumable sessions and would pollute the list.
    """
    projects = config_dir / "projects"
    if not projects.is_dir():
        return
    for project_dir in sorted(projects.iterdir()):
        if not project_dir.is_dir():
            continue
        for jsonl in sorted(project_dir.glob("*.jsonl")):
            yield project_dir.name, jsonl


def _scan(jsonl: Path) -> dict[str, Any]:
    """Pull cwd, titles, first timestamp and prompt count from one transcript."""
    cwd = ""
    first_ts = ""
    custom_title = ai_title = last_prompt = ""
    prompts = 0
    version = ""
    entrypoint = ""

    with jsonl.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"last-prompt"' in line:
                prompts += 1
            if not cwd and '"cwd"' in line and len(line) < 200_000:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = rec.get("cwd", "") or ""
                first_ts = first_ts or rec.get("timestamp", "") or ""
                version = version or rec.get("version", "") or ""
                entrypoint = entrypoint or rec.get("entrypoint", "") or ""
                continue
            if len(line) > MAX_PARSE_LEN:
                continue
            if not any(k in line for k in TITLE_KEYS):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = rec.get("type")
            if kind == "custom-title":
                custom_title = rec.get("customTitle", "") or custom_title
            elif kind == "ai-title":
                ai_title = rec.get("aiTitle", "") or ai_title
            elif kind == "last-prompt":
                last_prompt = rec.get("lastPrompt", "") or last_prompt

    title = custom_title or ai_title or (last_prompt[:70].strip() or "(untitled)")
    return {
        "title": title,
        "last_prompt": last_prompt,
        "cwd": cwd,
        "first_ts": first_ts,
        "prompts": prompts,
        "version": version,
        "entrypoint": entrypoint,
    }


def _fmt_iso(ts: str) -> str:
    """Render an ISO-8601 UTC stamp in local time, or empty if unparseable."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _unslug(slug: str) -> str:
    """Best-effort readable name when no cwd was recorded in the transcript."""
    return slug.replace("-", "/").strip("/")


def _short(folder: str, keep: int = 3) -> str:
    """Trim a long path to its last few segments for table display."""
    parts = folder.replace("\\", "/").rstrip("/").split("/")
    return folder if len(parts) <= keep else ".../" + "/".join(parts[-keep:])


def collect(config_dirs: list[Path]) -> list[dict[str, Any]]:
    """Scan every profile and return session rows, newest first."""
    rows: list[dict[str, Any]] = []
    for config_dir in config_dirs:
        if not (config_dir / "projects").is_dir():
            log.info("skipped (no projects dir): %s", config_dir)
            continue
        profile = config_dir.name
        for slug, jsonl in _iter_session_files(config_dir):
            stat = jsonl.stat()
            info = _scan(jsonl)
            rows.append({
                "profile": profile,
                "config_dir": str(config_dir),
                "session_id": jsonl.stem,
                "title": info["title"],
                "folder": info["cwd"] or _unslug(slug),
                "last_used": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "last_used_sort": stat.st_mtime,
                "first_used": _fmt_iso(info["first_ts"]),
                "prompts": info["prompts"],
                "mb": round(stat.st_size / 1_048_576, 1),
                "entrypoint": info["entrypoint"],
                "version": info["version"],
                "transcript": str(jsonl),
                "last_prompt": info["last_prompt"],
            })
    rows.sort(key=lambda r: r["last_used_sort"], reverse=True)
    return rows


def resume_command(row: dict[str, Any]) -> str:
    """PowerShell one-liner that reopens this exact session."""
    return ("$env:CLAUDE_CONFIG_DIR='" + row["config_dir"] + "'; "
            "cd '" + row["folder"] + "'; claude --resume " + row["session_id"])


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write the full index as CSV for filtering in Excel."""
    cols = ["profile", "title", "folder", "last_used", "first_used", "prompts",
            "mb", "session_id", "entrypoint", "version", "transcript"]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_html(rows: list[dict[str, Any]], path: Path) -> None:
    """Write a searchable, self-contained HTML index."""
    folders = sorted({r["folder"] for r in rows})
    opts = "".join('<option value="' + html.escape(f) + '">' + html.escape(f)
                   + "</option>" for f in folders)

    body = []
    for r in rows:
        cmd = resume_command(r)
        hint = (r["last_prompt"] or "")[:220]
        hay = (r["title"] + " " + r["folder"] + " " + r["session_id"] + " " + hint).lower()
        body.append(
            '<tr data-folder="' + html.escape(r["folder"]) + '" '
            'data-hay="' + html.escape(hay) + '">'
            + '<td class="t"><div class="ti">' + html.escape(r["title"]) + "</div>"
            + '<div class="hint">' + html.escape(hint) + "</div></td>"
            + '<td class="f"><span title="' + html.escape(r["folder"]) + '">'
            + html.escape(_short(r["folder"])) + "</span></td>"
            + '<td class="n">' + r["last_used"] + "</td>"
            + '<td class="n">' + str(r["prompts"]) + "</td>"
            + '<td class="n">' + str(r["mb"]) + "</td>"
            + '<td class="p">' + html.escape(r["profile"]) + "</td>"
            + '<td><button class="cp" data-cmd="' + html.escape(cmd)
            + '">copy resume</button></td></tr>')

    generated = datetime.now().strftime("%d %B %Y, %H:%M")
    doc = (_HTML_HEAD
           .replace("__COUNT__", str(len(rows)))
           .replace("__FOLDERS__", str(len(folders)))
           .replace("__GENERATED__", generated)
           .replace("__OPTIONS__", opts)
           + "\n".join(body) + _HTML_TAIL)
    path.write_text(doc, encoding="utf-8")


_HTML_HEAD = """<!doctype html>
<meta charset="utf-8"><title>Claude Code session index</title>
<style>
:root{color-scheme:dark;--bg:#1c1c1a;--fg:#e8e6e1;--dim:#9a968d;--line:#33322e;
--card:#242320;--acc:#d97757}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,Segoe UI,system-ui,sans-serif}
h1{font-size:19px;margin:0 0 4px;font-weight:600}
.sub{color:var(--dim);font-size:13px;margin-bottom:18px}
.bar{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}
input,select{background:var(--card);color:var(--fg);border:1px solid var(--line);
border-radius:7px;padding:8px 11px;font-size:13px;font-family:inherit}
input{flex:1;min-width:240px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
color:var(--dim);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:hover{background:var(--card)}
.ti{font-weight:500}
.hint{color:var(--dim);font-size:12px;margin-top:2px;max-width:52ch;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.f{color:var(--dim);font-size:12px;font-family:ui-monospace,Consolas,monospace;
max-width:30ch}
.n{white-space:nowrap;color:var(--dim);font-size:12.5px}
.p{color:var(--dim);font-size:12px}
button.cp{background:transparent;border:1px solid var(--line);color:var(--dim);
border-radius:6px;padding:4px 9px;font-size:11.5px;cursor:pointer;white-space:nowrap}
button.cp:hover{border-color:var(--acc);color:var(--acc)}
button.cp.ok{border-color:var(--acc);color:var(--acc)}
tr.hide{display:none}
</style>
<h1>Claude Code session index</h1>
<div class="sub">__COUNT__ sessions across __FOLDERS__ project folders &middot;
generated __GENERATED__ &middot; newest first</div>
<div class="bar">
<input id="q" placeholder="Search title, folder, session id, last prompt&hellip;">
<select id="folder"><option value="">All project folders</option>__OPTIONS__</select>
</div>
<table><thead><tr><th>Session</th><th>Project folder</th><th>Last used</th>
<th>Prompts</th><th>MB</th><th>Profile</th><th></th></tr></thead><tbody id="tb">
"""

_HTML_TAIL = """</tbody></table>
<script>
const q=document.getElementById('q'),fs=document.getElementById('folder'),
rows=[...document.querySelectorAll('#tb tr')];
function filter(){const t=q.value.toLowerCase().trim(),f=fs.value;
rows.forEach(r=>{const ok=(!t||r.dataset.hay.includes(t))&&(!f||r.dataset.folder===f);
r.classList.toggle('hide',!ok)});}
q.addEventListener('input',filter);fs.addEventListener('change',filter);
document.addEventListener('click',e=>{const b=e.target.closest('button.cp');if(!b)return;
navigator.clipboard.writeText(b.dataset.cmd).then(()=>{const o=b.textContent;
b.textContent='copied';b.classList.add('ok');
setTimeout(()=>{b.textContent=o;b.classList.remove('ok')},1200)});});
</script>
"""


def main() -> None:
    """CLI entry point."""
    home = Path.home()
    parser = argparse.ArgumentParser(description="Index all Claude Code sessions.")
    parser.add_argument("--config-dir", action="append", type=Path,
                        help="Claude config dir to scan; repeatable. "
                             "Default: ~/.claude and ~/.claude-work")
    parser.add_argument("--out-dir", type=Path,
                        default=home / ".claude" / "session_index",
                        help="Where to write the CSV and HTML index.")
    parser.add_argument("--top", type=int, default=25,
                        help="How many rows to print to the console (0 = all).")
    args = parser.parse_args()

    config_dirs = args.config_dir or [home / ".claude", home / ".claude-work"]
    rows = collect([Path(c) for c in config_dirs])
    if not rows:
        log.info("No sessions found in: %s", ", ".join(str(c) for c in config_dirs))
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "session_index.csv"
    html_path = args.out_dir / "session_index.html"
    write_csv(rows, csv_path)
    write_html(rows, html_path)

    shown = rows if args.top == 0 else rows[:args.top]
    width = min(max(max((len(r["title"]) for r in shown), default=20), 20), 52)
    log.info("")
    log.info("%-16s  %-*s  %s", "LAST USED", width, "SESSION", "PROJECT FOLDER")
    log.info("%s", "-" * (18 + width + 40))
    for r in shown:
        log.info("%-16s  %-*s  %s", r["last_used"], width, r["title"][:width],
                 _short(r["folder"], 2))
    log.info("")
    log.info("%d sessions in %d project folders across %d profile(s).",
             len(rows), len({r["folder"] for r in rows}),
             len({r["profile"] for r in rows}))
    log.info("HTML index : %s", html_path)
    log.info("CSV        : %s", csv_path)


if __name__ == "__main__":
    main()
