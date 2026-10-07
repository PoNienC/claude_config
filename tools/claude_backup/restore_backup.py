"""Restore a nightly backup of Claude Code data onto Windows or macOS.

Data layer: backup and restore utility. No spatial data; CRS not
applicable.

Input: one machine folder of the backup set, e.g.
    ~/OneDrive/claude_backups/win_priorplap180                    (Windows)
    ~/Library/CloudStorage/OneDrive-Personal/claude_backups/win_priorplap180  (macOS)
written by backup_claude_data.ps1 (Windows) or backup_macos.sh (macOS).
Either can be restored onto either operating system.

Output: ~/.claude, ~/.claude-work and the Claude Desktop data folder on
this machine, plus a report in ~/.claude/restore_reports/.

Why folders get renamed: Claude Code files each project's sessions under
~/.claude/projects/<slug>, where <slug> is the project path with every
character that is not a letter or digit replaced by "-". The same
project lives at a different path on the new machine, e.g.
    C:\\Users\\po.nienchen\\OneDrive - priorpartners.com\\Documents\\X
    /Users/<you>/Library/CloudStorage/OneDrive-priorpartners.com/Documents/X
so each session folder is renamed through a prefix map (backup home ->
this home, backup Documents -> this Documents, plus any --map) and
`claude --resume` then lists the sessions when run inside X.

Merges into a machine that already has Claude Code set up - nothing on
this machine is ever deleted:
  - sessions, file history, Desktop sessions: added; a session present
    on both sides keeps the newer copy (session IDs are unique).
  - prompt history: merged line by line.
  - config (CLAUDE.md, rules, skills, settings...) and project memory:
    THIS machine's copy wins. Where the backup's copy differs it is set
    aside in ~/.claude/restore_reports/conflicts_<stamp>/ for a manual
    merge (--prefer-backup lets newer backup copies win instead).
  - an existing ~/.claude/.git clone is left untouched.
Safe by default: prints the plan and writes nothing unless --apply.
Never restores .credentials.json or .claude.json - sign in fresh.

Usage:
    python restore_backup.py <machine folder>            # dry run
    python restore_backup.py <machine folder> --apply
    python restore_backup.py <machine folder> --apply --map "N:\\=/Volumes/PP_Team_Nas"
"""

from __future__ import annotations

import argparse
import filecmp
import json
import logging
import os
import re
import shutil
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LOG = logging.getLogger("restore_backup")

SLUG_MAX = 200                       # Claude Code hashes longer slugs; not reproducible here
MTIME_TOLERANCE_S = 2.0              # FAT/zip/OneDrive timestamp rounding
SECRET_NAMES = frozenset({".credentials.json", ".claude.json"})
DESKTOP_PATH_KEYS = ("cwd", "originCwd")
ACCOUNTS = (("personal", ".claude"), ("work", ".claude-work"))

# Text that marks a settings file as tied to one operating system.
WINDOWS_MARKERS = re.compile(r"powershell|pwsh|\.ps1\b|\.exe\b|[A-Za-z]:\\\\", re.IGNORECASE)
MACOS_MARKERS = re.compile(r"/bin/|/usr/|/Users/|/opt/homebrew|\.sh\b")


# --- Path translation ---------------------------------------------------

def is_windows_path(path: str) -> bool:
    """True for C:\\... or \\\\server\\share paths."""
    return bool(re.match(r"^[A-Za-z]:[\\/]?", path)) or path.startswith("\\\\")


def project_slug(path: str) -> str | None:
    """Claude Code's project folder name for a path, or None if too long."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", path)
    return slug if len(slug) <= SLUG_MAX else None


def _strip_prefix(path: str, prefix: str) -> str | None:
    """Return the part of `path` below `prefix`, or None if not below it."""
    if is_windows_path(prefix):
        p = path.replace("/", "\\")
        pre = prefix.replace("/", "\\").rstrip("\\")
        cmp_p, cmp_pre, sep = p.casefold(), pre.casefold(), "\\"
    else:
        p, pre = path, prefix.rstrip("/")
        cmp_p, cmp_pre, sep = p, pre, "/"
    if cmp_p == cmp_pre:
        return ""
    if cmp_p.startswith(cmp_pre + sep):
        return p[len(pre) + 1:]
    return None


@dataclass
class PrefixRule:
    source: str
    target: str


class PathMapper:
    """Translate backup-machine paths into this machine's paths."""

    def __init__(self, rules: list[PrefixRule], target_os: str) -> None:
        self.rules = sorted(rules, key=lambda r: len(r.source), reverse=True)
        self.sep = "\\" if target_os == "windows" else "/"

    def translate(self, path: str) -> str | None:
        for rule in self.rules:
            rest = _strip_prefix(path, rule.source)
            if rest is None:
                continue
            target = rule.target.rstrip("\\/") or rule.target
            parts = [p for p in re.split(r"[\\/]", rest) if p]
            return self.sep.join([target, *parts]) if parts else target
        return None

    def translate_slug(self, slug: str) -> str | None:
        """Slug-level prefix swap on a folder name (result may exceed SLUG_MAX).

        Slugs turn "\\" and "-" alike into "-", so a sibling such as
        "...Client-Archive" can match a "...Client" map. Default maps
        (home, Documents) are safe; take care with narrow --map prefixes.
        """
        for rule in self.rules:
            s_src = project_slug(rule.source.rstrip("\\/"))
            s_dst = project_slug(rule.target.rstrip("\\/") or rule.target)
            if not s_src or not s_dst:
                continue
            if slug.casefold().startswith(s_src.casefold()) and (
                len(slug) == len(s_src) or slug[len(s_src)] == "-"
            ):
                return s_dst + slug[len(s_src):]
        return None


# --- File operations ----------------------------------------------------

@dataclass
class Tally:
    copied: int = 0
    kept: int = 0
    rewritten: int = 0
    parked: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class KeepPolicy:
    """Files where this machine's copy always wins.

    For a covered file that already exists and differs, the backup's copy
    is parked under `park_root` (same relative path) for a manual merge,
    outside ~/.claude/rules and skills so Claude Code never loads it.
    """
    park_root: Path
    covers: Callable[[Path], bool]


def long_path(path: Path) -> Path:
    """Add the \\\\?\\ prefix on Windows so paths over 260 characters work."""
    if os.name != "nt":
        return path
    text = str(path.absolute())
    if text.startswith("\\\\?\\"):
        return path
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)


def is_newer(src: Path, dst: Path) -> bool:
    """True when dst is missing or older than src."""
    if not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime + MTIME_TOLERANCE_S


def copy_file(src: Path, dst: Path, apply: bool, tally: Tally,
              park: Path | None = None) -> None:
    """Newer wins - or, when `park` is given, the existing file wins."""
    if park is not None and dst.exists():
        if filecmp.cmp(src, dst, shallow=False):
            tally.kept += 1
            return
        tally.parked.append(str(park))
        if apply:
            park.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, park)
        return
    if not is_newer(src, dst):
        tally.kept += 1
        return
    tally.copied += 1
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, apply: bool, tally: Tally,
              skip_names: frozenset[str] = frozenset(),
              skip_top: frozenset[str] = frozenset(),
              keep: KeepPolicy | None = None) -> None:
    """Additive copy: nothing at dst is deleted. See copy_file for who wins."""
    src_l, dst_l = long_path(src), long_path(dst)
    for root, dirs, files in os.walk(src_l):
        rel = Path(root).relative_to(src_l)
        if rel == Path("."):
            dirs[:] = [d for d in dirs if d not in skip_top]
        for name in files:
            if name in skip_names or (rel == Path(".") and name in skip_top):
                continue
            rel_file = rel / name
            park = (long_path(keep.park_root) / rel_file
                    if keep is not None and keep.covers(rel_file) else None)
            copy_file(Path(root) / name, dst_l / rel_file, apply, tally, park)


def copy_zip(zip_path: Path, dst: Path, apply: bool, tally: Tally) -> None:
    """Extract a zipped item, adding missing files only.

    Zip times are local clock time with no zone, so "newer wins" is not
    safe across time zones; an existing file is therefore never replaced.
    Drive-letter and ".." parts are dropped so nothing lands outside dst.
    """
    dst_l = long_path(dst)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = [p for p in re.split(r"[\\/]", info.filename)
                     if p not in ("", ".", "..") and not re.match(r"^[A-Za-z]:", p)]
            if not parts:
                continue
            target = dst_l.joinpath(*parts)
            mtime = datetime(*info.date_time).timestamp()
            if target.exists():
                tally.kept += 1
                continue
            tally.copied += 1
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src_fh, target.open("wb") as out_fh:
                    shutil.copyfileobj(src_fh, out_fh)
                os.utime(target, (mtime, mtime))


def copy_item(mirror: Path, name: str, dst: Path, apply: bool, tally: Tally) -> None:
    """Restore a mirror item stored either as a folder or as <name>.zip."""
    if (mirror / f"{name}.zip").is_file():
        copy_zip(mirror / f"{name}.zip", dst, apply, tally)
    if (mirror / name).is_dir():
        copy_tree(mirror / name, dst, apply, tally)


def restore_git_repos(src_root: Path, dst_root: Path, apply: bool, tally: Tally) -> None:
    """Restore .git folders kept outside OneDrive, one repo at a time.

    A repo folder that already exists is left untouched: merging two
    copies of a git folder file by file could mix refs from different
    points in time.
    """
    if not src_root.is_dir():
        LOG.info("  no git_repos in this backup")
        return
    for repo in sorted(p for p in src_root.iterdir() if p.is_dir()):
        dst = dst_root / repo.name
        if dst.exists():
            LOG.info("  %s: already here, left untouched", repo.name)
            tally.notes.append(f"git folder {repo.name} already exists at {dst} - not restored")
            continue
        LOG.info("  %s -> %s", repo.name, dst)
        copy_tree(repo, dst, apply, tally)


def write_text(path: Path, text: str, apply: bool) -> None:
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        with long_path(path).open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


# --- Restore steps ------------------------------------------------------

def session_cwd(project_dir: Path) -> str | None:
    """The `cwd` whose slug is this folder's name; else the first one seen.

    Sessions can cd into sub-folders, and folders can be renamed after a
    reorganisation, so the first cwd is not always the project path.
    """
    files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    first: str | None = None
    for jsonl in files[:5]:
        with long_path(jsonl).open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 200:
                    break
                if '"cwd"' not in line:
                    continue
                try:
                    cwd = json.loads(line).get("cwd")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if not isinstance(cwd, str) or not cwd:
                    continue
                slug = project_slug(cwd)
                if slug and slug.casefold() == project_dir.name.casefold():
                    return cwd
                first = first or cwd
    return first


def plan_project_name(project_dir: Path, mapper: PathMapper) -> tuple[str, str]:
    """(new folder name, how it was decided)."""
    name = project_dir.name
    cwd = session_cwd(project_dir)
    old_slug = project_slug(cwd) if cwd else None
    if cwd and old_slug and old_slug.casefold() == name.casefold():
        new_path = mapper.translate(cwd)
        if new_path is None:
            return name, "unmapped"
        new_slug = project_slug(new_path)
        if new_slug is None:
            return name, "too_long"
        return (name, "same") if new_slug.casefold() == name.casefold() else (new_slug, "renamed")
    # The folder name is what Claude Code looks up, so it wins over a cwd
    # that does not match it (moved sessions, sub-folder cwd, no cwd).
    new_slug = mapper.translate_slug(name)
    if new_slug is not None:
        if len(new_slug) > SLUG_MAX:
            return name, "too_long"
        return (name, "same") if new_slug.casefold() == name.casefold() else (new_slug, "renamed")
    if cwd:
        # A mapped drive (N:) is filed under its UNC path, which no default
        # map covers; rename only when a --map really moves the cwd.
        new_path = mapper.translate(cwd)
        if new_path is not None and new_path.casefold() != cwd.casefold():
            new_slug = project_slug(new_path)
            return (new_slug, "renamed") if new_slug else (name, "too_long")
    return name, "unmapped"


def is_memory_file(rel: Path) -> bool:
    return rel.parts[:1] == ("memory",)


def restore_projects(src_root: Path, dst_root: Path, mapper: PathMapper,
                     apply: bool, tally: Tally, park_root: Path | None) -> None:
    """Session transcripts: newer wins (IDs are unique per session).
    Memory files: this machine wins; differing backup copies are parked."""
    if not src_root.is_dir():
        return
    counts = {"same": 0, "renamed": 0, "unmapped": 0, "too_long": 0}
    for project in sorted(p for p in src_root.iterdir() if p.is_dir()):
        new_name, how = plan_project_name(project, mapper)
        counts[how] += 1
        if how == "renamed":
            LOG.info("    %s\n      -> %s", project.name, new_name)
        elif how in ("unmapped", "too_long"):
            tally.notes.append(f"{src_root.name}/{project.name}: {how}, copied unchanged "
                               f"(fine if that path is the same here; else add --map)")
        keep = KeepPolicy(park_root / new_name, is_memory_file) if park_root else None
        copy_tree(project, dst_root / new_name, apply, tally, keep=keep)
    LOG.info("    folders: %d unchanged, %d renamed, %d unmapped, %d too long",
             counts["same"], counts["renamed"], counts["unmapped"], counts["too_long"])


def restore_desktop_sessions(src_root: Path, dst_root: Path, mapper: PathMapper,
                             apply: bool, tally: Tally) -> None:
    """Copy Desktop session records, rewriting their project paths."""
    if not src_root.is_dir():
        return
    src_l, dst_l = long_path(src_root), long_path(dst_root)
    for root, _dirs, files in os.walk(src_l):
        rel = Path(root).relative_to(src_l)
        for name in files:
            src, dst = Path(root) / name, dst_l / rel / name
            if not name.endswith(".json"):
                copy_file(src, dst, apply, tally)
                continue
            if not is_newer(src, dst):
                tally.kept += 1
                continue
            text = src.read_text(encoding="utf-8", errors="replace")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                copy_file(src, dst, apply, tally)
                continue
            changed = False
            if isinstance(data, dict):
                for key in DESKTOP_PATH_KEYS:
                    value = data.get(key)
                    new = mapper.translate(value) if isinstance(value, str) else None
                    if new and new != value:
                        data[key] = new
                        changed = True
            if changed:
                tally.rewritten += 1
                write_text(dst, json.dumps(data, ensure_ascii=False, separators=(",", ":")), apply)
            else:
                copy_file(src, dst, apply, tally)


def latest_snapshot_file(backup: Path, name: str) -> Path | None:
    snaps = backup / "config_snapshots"
    if not snaps.is_dir():
        return None
    for snap in sorted((p for p in snaps.iterdir() if p.is_dir()), reverse=True):
        candidate = snap / name
        if candidate.is_file():
            return candidate
    return None


def merge_history(src: Path, dst: Path, mapper: PathMapper, apply: bool) -> int:
    """Merge prompt history, translating each entry's project path."""
    entries: dict[str, dict] = {}

    def add(line: str, translate: bool) -> None:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(obj, dict):
            return
        project = obj.get("project")
        if translate and isinstance(project, str):
            new = mapper.translate(project)
            if new:
                obj["project"] = new
        entries.setdefault(f"{obj.get('timestamp')}|{obj.get('display')}", obj)

    before = 0
    if dst.is_file():
        with dst.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                add(line, translate=False)
        before = len(entries)
    with src.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            add(line, translate=True)
    ordered = sorted(entries.values(), key=lambda o: o.get("timestamp") or 0)
    write_text(dst, "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in ordered), apply)
    return len(entries) - before


def check_settings(config_dir: Path, target_os: str, tally: Tally) -> None:
    settings = config_dir / "settings.json"
    if not settings.is_file():
        return
    text = settings.read_text(encoding="utf-8", errors="replace")
    markers = WINDOWS_MARKERS if target_os == "macos" else MACOS_MARKERS
    hits = sorted({m.group(0) for m in markers.finditer(text)})
    if hits:
        tally.notes.append(f"{config_dir.name}/settings.json has other-OS entries "
                           f"({', '.join(hits[:5])}) - review hooks and paths by hand")


def mcp_report(backup: Path, mapper: PathMapper) -> dict:
    """Collect MCP server definitions for manual re-adding."""
    report: dict = {}
    for label, fname in (("personal", "personal_dot_claude.json"), ("work", "work_dot_claude.json")):
        snap = latest_snapshot_file(backup, fname)
        if not snap:
            continue
        try:
            data = json.loads(snap.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        user_level = data.get("mcpServers") or {}
        per_project = {}
        for path, cfg in (data.get("projects") or {}).items():
            servers = (cfg or {}).get("mcpServers") or {}
            if servers:
                per_project[mapper.translate(path) or path] = servers
        if user_level or per_project:
            report[label] = {"user_scope": user_level, "project_scope": per_project}
    desktop = latest_snapshot_file(backup, "claude_desktop_config.json")
    if desktop:
        try:
            servers = json.loads(desktop.read_text(encoding="utf-8-sig")).get("mcpServers") or {}
        except json.JSONDecodeError:
            servers = {}
        if servers:
            report["desktop_app"] = servers
    return report


# --- Target machine -----------------------------------------------------

def detect_os() -> str:
    return "windows" if os.name == "nt" else "macos"


def default_documents(target_os: str, home: str) -> str:
    if target_os == "windows":
        return home.rstrip("\\") + "\\OneDrive - priorpartners.com\\Documents"
    cloud = Path(home) / "Library" / "CloudStorage"
    if cloud.is_dir():
        for candidate in sorted(cloud.glob("OneDrive-*priorpartners*")):
            return f"{candidate.as_posix()}/Documents"
    return f"{home.rstrip('/')}/Library/CloudStorage/OneDrive-priorpartners.com/Documents"


def desktop_dir(target_os: str, install_home: Path) -> Path:
    if target_os == "macos":
        return install_home / "Library" / "Application Support" / "Claude"
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for pkg in sorted(Path(local, "Packages").glob("Claude_*")):
            cache = pkg / "LocalCache" / "Roaming" / "Claude"
            if cache.is_dir():
                return cache
    return Path(os.environ.get("APPDATA", str(install_home / "AppData" / "Roaming")), "Claude")


# --- Main ---------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Restore a Claude Code backup onto this machine.")
    ap.add_argument("backup", type=Path, help="machine folder, e.g. .../claude_backups/win_priorplap180")
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    ap.add_argument("--target-os", choices=("windows", "macos"), default=detect_os())
    ap.add_argument("--home", help="home folder on the target machine (default: yours)")
    ap.add_argument("--documents", help="OneDrive Documents folder on the target machine")
    ap.add_argument("--map", action="append", default=[], metavar="FROM=TO",
                    help="extra path prefix to translate, e.g. \"N:\\=/Volumes/PP_Team_Nas\"")
    ap.add_argument("--install-root", type=Path,
                    help="write everything under this folder instead of the real home (testing)")
    ap.add_argument("--include-documents", action="store_true",
                    help="also copy the Documents mirror (only if OneDrive is NOT restoring it)")
    ap.add_argument("--include-git-repos", action="store_true",
                    help="also restore the .git folders kept outside OneDrive (C:\\git); "
                         "a repo folder that already exists is left untouched")
    ap.add_argument("--git-root", help="where to restore them (default: C:\\git; Windows only)")
    ap.add_argument("--skip-desktop", action="store_true", help="leave Desktop app data alone")
    ap.add_argument("--prefer-backup", action="store_true",
                    help="let newer backup copies replace this machine's config and memory "
                         "(default: this machine's copy wins; the backup's is parked for review)")
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    backup = args.backup.expanduser()
    manifest_path = backup / "last_backup_manifest.json"
    if not manifest_path.is_file():
        found = sorted(p.parent.name for p in backup.glob("*/last_backup_manifest.json"))
        LOG.error("No last_backup_manifest.json in %s", backup)
        if found:
            LOG.error("Pick one machine folder: %s", ", ".join(found))
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

    target_os = args.target_os
    same_os = target_os == detect_os()
    if not same_os and not args.install_root:
        LOG.error("--target-os %s differs from this machine: add --install-root to stage the files.",
                  target_os)
        return 1
    home = args.home or str(Path.home())
    documents = args.documents or default_documents(target_os, home)
    install_home = args.install_root / "home" if args.install_root else Path(home)
    desk = (args.install_root / "desktop_app" if args.install_root
            else desktop_dir(target_os, install_home))

    rules = [PrefixRule(manifest["source_home"], home)]
    if manifest.get("source_documents"):
        rules.append(PrefixRule(manifest["source_documents"], documents))
    for item in args.map:
        if "=" not in item:
            LOG.error("--map needs FROM=TO, got %r", item)
            return 1
        src, dst = item.split("=", 1)
        rules.append(PrefixRule(src, dst))
    mapper = PathMapper(rules, target_os)

    mode = "APPLY" if args.apply else "DRY RUN - nothing is written (add --apply)"
    LOG.info("Restore: %s", mode)
    LOG.info("  backup   %s (%s, %s, taken %s)", backup, manifest.get("source_os"),
             manifest.get("machine"), manifest.get("backup_completed_at"))
    if not manifest.get("complete", True):
        LOG.warning("  WARNING: that backup run was marked incomplete - see its log.")
    LOG.info("  target   %s -> home %s", target_os, install_home)
    for rule in mapper.rules:
        LOG.info("  map      %s  =>  %s", rule.source, rule.target)
    if args.apply and not args.skip_desktop:
        LOG.info("  Close the Claude Desktop app before continuing, or it may overwrite restored files.")

    mirror = backup / "mirror"
    tally = Tally()
    report_dir = install_home / ".claude" / "restore_reports"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    conflicts = report_dir / f"conflicts_{stamp}"

    for account, dirname in ACCOUNTS:
        cfg_dir = install_home / dirname
        if not (mirror / f"{account}_projects").is_dir() and not (mirror / f"{account}_config").is_dir():
            continue
        LOG.info("\n[%s] %s", account, cfg_dir)
        if (mirror / f"{account}_config").is_dir():
            LOG.info("  config (rules, skills, references, tools, settings)")
            skip_top = {"history.jsonl"}
            if (cfg_dir / ".git").exists():
                skip_top.add(".git")        # this machine's clone stays as it is
            keep = None if args.prefer_backup else KeepPolicy(conflicts / dirname, lambda _rel: True)
            copy_tree(mirror / f"{account}_config", cfg_dir, args.apply, tally,
                      skip_names=SECRET_NAMES, skip_top=frozenset(skip_top), keep=keep)
            if not same_os or args.install_root:
                check_settings(mirror / f"{account}_config", target_os, tally)
        LOG.info("  sessions and memory")
        park = None if args.prefer_backup else conflicts / dirname / "projects"
        restore_projects(mirror / f"{account}_projects", cfg_dir / "projects", mapper,
                         args.apply, tally, park)
        if (mirror / f"{account}_file_history").is_dir():
            LOG.info("  file history (rewind checkpoints)")
            copy_tree(mirror / f"{account}_file_history", cfg_dir / "file-history", args.apply, tally)
        if account == "personal" and (mirror / "personal_session_backup_premove").is_dir():
            copy_tree(mirror / "personal_session_backup_premove",
                      cfg_dir / "_session_backup_premove", args.apply, tally)
        hist = latest_snapshot_file(backup, f"{account}_history.jsonl")
        if hist:
            added = merge_history(hist, cfg_dir / "history.jsonl", mapper, args.apply)
            LOG.info("  prompt history: %d entries added", added)

    if not args.skip_desktop:
        LOG.info("\n[desktop app] %s", desk)
        restore_desktop_sessions(mirror / "desktop_code_sessions", desk / "claude-code-sessions",
                                 mapper, args.apply, tally)
        copy_item(mirror, "desktop_agent_mode_sessions", desk / "local-agent-mode-sessions",
                  args.apply, tally)
        mcp_src = latest_snapshot_file(backup, "claude_desktop_config.json")
        mcp_dst = desk / "claude_desktop_config.json"
        if mcp_src and same_os and not mcp_dst.exists():
            LOG.info("  MCP config: restored claude_desktop_config.json")
            copy_file(mcp_src, mcp_dst, args.apply, tally)
        elif mcp_src:
            tally.notes.append("Desktop MCP config not copied (exists already, or other OS) - "
                               "see mcp_servers_from_backup.json in the report folder")

    if args.include_documents:
        docs_src = backup / "documents"
        if docs_src.is_dir():
            docs_dst = (args.install_root / "documents") if args.install_root else Path(documents)
            LOG.info("\n[documents] %s", docs_dst)
            copy_tree(docs_src, docs_dst, args.apply, tally)

    if args.include_git_repos:
        if target_os != "windows" and not (args.git_root or args.install_root):
            LOG.info("\n[git repos] skipped: OneDrive working folders point to C:/git, which "
                     "exists on Windows only. On a Mac, clone from GitHub instead.")
        else:
            git_root = (args.install_root / "git_repos" if args.install_root
                        else Path(args.git_root or "C:\\git"))
            LOG.info("\n[git repos] %s", git_root)
            restore_git_repos(mirror / "git_repos", git_root, args.apply, tally)

    mcp = mcp_report(backup, mapper)
    if mcp:
        write_text(report_dir / f"mcp_servers_from_backup_{stamp}.json",
                   json.dumps(mcp, indent=2, ensure_ascii=False), args.apply)

    LOG.info("\nSummary: %d files to add, %d rewritten for new paths, "
             "%d already here (kept), %d conflicts set aside",
             tally.copied, tally.rewritten, tally.kept, len(tally.parked))
    if tally.parked:
        LOG.info("  Conflicts: this machine's copy was KEPT. The backup's copy %s in\n  %s",
                 "is" if args.apply else "would be put", conflicts)
        for path in tally.parked[:25]:
            LOG.info("    %s", Path(path).relative_to(long_path(conflicts)))
        if len(tally.parked) > 25:
            LOG.info("    ... and %d more (full list in the report)", len(tally.parked) - 25)
    for note in tally.notes:
        LOG.info("  NOTE: %s", note)
    summary = {"when": stamp, "applied": args.apply, "backup": str(backup), "target_os": target_os,
               "home": str(install_home), "copied": tally.copied, "rewritten": tally.rewritten,
               "kept": tally.kept, "conflicts_dir": str(conflicts), "conflicts": tally.parked,
               "notes": tally.notes, "maps": [[r.source, r.target] for r in mapper.rules]}
    write_text(report_dir / f"restore_{stamp}.json", json.dumps(summary, indent=2), args.apply)
    if args.apply:
        LOG.info("Report: %s", report_dir)
        LOG.info("Next: sign in, open a project folder, run `claude --resume`.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
