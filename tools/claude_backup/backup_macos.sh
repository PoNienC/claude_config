#!/bin/bash
# Nightly backup of Claude data (both accounts) and OneDrive Documents - macOS.
#
# Twin of backup_claude_data.ps1 (Windows). Same layout, so
# restore_backup.py restores either one onto Windows or macOS:
#   <BACKUP_DEST>/mac_<hostname>/
#     mirror/                    additive copies of Claude data + config
#     documents/                 additive copy of OneDrive Documents
#     config_snapshots/<stamp>/  small config files, 10 generations
#     logs/
#     last_backup_manifest.json  read by restore_backup.py
#
# Additive, never destructive: rsync runs WITHOUT --delete, so an app
# failure that empties a source cannot wipe the backup the next night.
# --prune opts in to deleting stale backup files (never on a schedule).
#
# Cloud-only (dataless) OneDrive files are skipped, never downloaded.
# That needs an rsync with --files-from; Homebrew rsync is preferred
# (brew install rsync). Without it, Documents is skipped with a warning.
#
# OneDrive will not sync a path longer than 400 characters. Desktop
# agent-mode sessions nest up to ~540, so they are mirrored into a local
# staging folder (BACKUP_STAGING) and only a zip goes to OneDrive,
# rebuilt only when something changed. Other items are checked nightly
# and the log warns if any path goes over the limit.
#
# Secrets are never copied: .credentials.json and .claude.json stay out
# of the mirror (.claude.json is only snapshotted, never restored).
# On macOS the login token lives in the Keychain, not in a file.
#
# Usage:
#   backup_macos.sh [--skip-documents | --documents-only | --config-only] [--prune]
# Environment overrides:
#   BACKUP_DEST       default ~/Library/CloudStorage/OneDrive-Personal/claude_backups
#   DOCUMENTS_SOURCE  default ~/Library/CloudStorage/OneDrive-priorpartners.com/Documents
#   BACKUP_STAGING    default ~/.backup_staging (local, for zipped items)
#
# Schedule it with install_schedule_macos.sh (22:00 daily, launchd).
# Written for the stock /bin/bash 3.2 - no bash 4 features.

MODE="full"
PRUNE=0
for arg in "$@"; do
    case "$arg" in
        --skip-documents) MODE="claude_data_only" ;;
        --documents-only) MODE="documents_only" ;;
        --config-only)    MODE="config_only" ;;
        --prune)          PRUNE=1 ;;
        *) echo "Unknown option: $arg"; exit 64 ;;
    esac
done

STARTED=$(date +%s)
STAMP=$(date +%Y%m%d_%H%M%S)
KEEP_SNAPSHOTS=10
KEEP_LOGS=30
SHRINK_RATIO_PCT=50

# --- Destination: must already exist (a missing OneDrive must not turn
# into a plain local folder that syncs nowhere) ------------------------
DEST="${BACKUP_DEST:-}"
if [ -z "$DEST" ]; then
    for c in "$HOME/Library/CloudStorage/OneDrive-Personal/claude_backups" \
             "$HOME"/Library/CloudStorage/OneDrive-Personal*/claude_backups; do
        if [ -d "$c" ]; then DEST="$c"; break; fi
    done
fi
if [ -z "$DEST" ] || [ ! -d "$DEST" ]; then
    echo "Destination not found: ${DEST:-~/Library/CloudStorage/OneDrive-Personal/claude_backups}"
    echo "Is the backup OneDrive signed in, with a claude_backups folder? Nothing was copied."
    exit 1
fi

DOCS_SRC="${DOCUMENTS_SOURCE:-}"
if [ -z "$DOCS_SRC" ]; then
    for c in "$HOME/Library/CloudStorage/OneDrive-priorpartners.com/Documents" \
             "$HOME"/Library/CloudStorage/OneDrive-*priorpartners*/Documents; do
        if [ -d "$c" ]; then DOCS_SRC="$c"; break; fi
    done
fi

HOST=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
MACHINE="mac_$(printf '%s' "$HOST" | tr 'A-Z' 'a-z' | sed 's/[^a-z0-9]/_/g')"
MROOT="$DEST/$MACHINE"
MIRROR="$MROOT/mirror"
SNAPROOT="$MROOT/config_snapshots"
LOGDIR="$MROOT/logs"
LOG="$LOGDIR/backup_$STAMP.log"
mkdir -p "$MIRROR" "$SNAPROOT" "$LOGDIR"

PERSONAL="$HOME/.claude"
WORK="$HOME/.claude-work"
DESKTOP="$HOME/Library/Application Support/Claude"
STAGING="${BACKUP_STAGING:-$HOME/.backup_staging}"
ONEDRIVE_ROOT=$(dirname "$DEST")
PATH_LIMIT=400
mkdir -p "$STAGING"

RSYNC=""
for r in /opt/homebrew/bin/rsync /usr/local/bin/rsync /usr/bin/rsync; do
    if [ -x "$r" ]; then RSYNC="$r"; break; fi
done

ITEMS_JSON=""
FAILURES=""
GAPS=""
SHRINKS=""
TOTAL_KB=0

log() {
    printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2" | tee -a "$LOG"
}

json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

json_list() {
    # space-separated words -> JSON array of strings
    out=""
    for w in $1; do
        [ -n "$out" ] && out="$out, "
        out="$out\"$(json_escape "$w")\""
    done
    printf '[%s]' "$out"
}

count_files() {
    if [ -d "$1" ]; then find "$1" -type f 2>/dev/null | wc -l | tr -d ' '; else echo 0; fi
}

size_kb() {
    # Logical size: du would report ~0 for files OneDrive has freed up.
    if [ -d "$1" ]; then
        find "$1" -type f -print0 2>/dev/null | xargs -0 stat -f %z 2>/dev/null |
            awk '{ s += $1 } END { printf "%d", s / 1024 }'
    else
        echo 0
    fi
}

add_item() {
    # name source status files kb
    [ -n "$ITEMS_JSON" ] && ITEMS_JSON="$ITEMS_JSON,"
    mb=$(awk -v k="$5" 'BEGIN { printf "%.1f", k / 1024 }')
    ITEMS_JSON="$ITEMS_JSON
    { \"name\": \"$1\", \"source\": \"$(json_escape "$2")\", \"status\": \"$3\", \"files\": $4, \"mb\": $mb }"
}

shrink_check() {
    src_n=$(count_files "$2")
    dst_n=$(count_files "$3")
    if [ "$dst_n" -gt 0 ] && [ $((src_n * 100)) -lt $((dst_n * SHRINK_RATIO_PCT)) ]; then
        SHRINKS="$SHRINKS $1"
        log WARN "SHRINK GUARD - $1: source has $src_n files, backup has $dst_n"
        log WARN "  Source shrank sharply. Copy still runs (additive, so nothing"
        log WARN "  in the backup is lost), but investigate before trusting the source."
    fi
}

finish_item() {
    # name source dest rsync_exit required(0/1) partial_ok(0/1)
    status="copied"
    case "$4" in
        0|24) status="copied" ;;              # 24 = files vanished mid-copy (live data)
        23|25)
            if [ "$6" = 1 ]; then status="partial"; else status="failed"; fi ;;
        *) status="failed" ;;
    esac
    if [ "$status" = "failed" ]; then
        FAILURES="$FAILURES $1"
        log ERROR "COPY FAILED: $1 rsync exit=$4"
    elif [ "$status" = "partial" ]; then
        log WARN "PARTIAL: $1 rsync exit=$4 - some files could not be copied"
    fi
    n=$(count_files "$3")
    kb=$(size_kb "$3")
    over=$(find "$3" 2>/dev/null | awk -v b=$((${#ONEDRIVE_ROOT} + 1)) -v lim="$PATH_LIMIT" \
        'length($0) - b > lim { c++ } END { print c + 0 }')
    [ "$over" -gt 0 ] && log WARN "$1: $over paths are longer than OneDrive's $PATH_LIMIT-character limit and will not sync"
    TOTAL_KB=$((TOTAL_KB + kb))
    add_item "$1" "$2" "$status" "$n" "$kb"
    log INFO "copied $1: $n files, $((kb / 1024)) MB"
}

# mirror_zip_item name source required(0/1)
# Additive copy into local staging, then a zip into the backup - rebuilt
# only when the staged tree changed, so an unchanged night uploads nothing.
mirror_zip_item() {
    name="$1"; src="$2"; required="$3"
    stage="$STAGING/$name"
    zipf="$MIRROR/$name.zip"
    if [ ! -d "$src" ]; then
        log WARN "source not present, skipped: $src"
        add_item "$name" "$src" "source_missing" 0 0
        [ "$required" = 1 ] && GAPS="$GAPS $name"
        return
    fi
    shrink_check "$name" "$src" "$stage"
    mkdir -p "$stage"
    if [ "$PRUNE" = 1 ]; then
        "$RSYNC" -a --delete "$src/" "$stage/" >>"$LOG" 2>&1
    else
        "$RSYNC" -a "$src/" "$stage/" >>"$LOG" 2>&1
    fi
    code=$?
    status="copied"
    case "$code" in 0|24) ;; *) status="failed"; FAILURES="$FAILURES $name"
        log ERROR "COPY FAILED: $name rsync exit=$code" ;; esac
    n=$(count_files "$stage")
    rebuild=1
    if [ -f "$zipf" ]; then
        changed=$(find "$stage" -newer "$zipf" -type f 2>/dev/null | head -1)
        zipped=$(zipinfo -1 "$zipf" 2>/dev/null | grep -vc '/$')
        [ -z "$changed" ] && [ "$zipped" = "$n" ] && rebuild=0
    fi
    if [ "$status" != "failed" ] && [ "$rebuild" = 1 ]; then
        rm -f "$zipf.partial"
        if (cd "$stage" && zip -qrX "$zipf.partial" .); then
            mv -f "$zipf.partial" "$zipf"
            log INFO "zipped $name -> $zipf"
        else
            FAILURES="$FAILURES $name"; status="failed"
            log ERROR "ZIP FAILED: $name"
        fi
    elif [ "$rebuild" = 0 ]; then
        log INFO "$name: unchanged, zip kept"
    fi
    kb=0
    [ -f "$zipf" ] && kb=$(( $(stat -f %z "$zipf") / 1024 ))
    TOTAL_KB=$((TOTAL_KB + kb))
    add_item "$name" "$src" "$status" "$n" "$kb"
    log INFO "copied $name: $n files, zip $((kb / 1024)) MB"
}

# mirror_item name source required(0/1) [extra rsync args...]
mirror_item() {
    name="$1"; src="$2"; required="$3"; shift 3
    dst="$MIRROR/$name"
    if [ ! -d "$src" ]; then
        log WARN "source not present, skipped: $src"
        add_item "$name" "$src" "source_missing" 0 0
        [ "$required" = 1 ] && GAPS="$GAPS $name"
        return
    fi
    shrink_check "$name" "$src" "$dst"
    mkdir -p "$dst"
    if [ "$PRUNE" = 1 ]; then
        "$RSYNC" -a --delete "$@" "$src/" "$dst/" >>"$LOG" 2>&1
    else
        "$RSYNC" -a "$@" "$src/" "$dst/" >>"$LOG" 2>&1
    fi
    finish_item "$name" "$src" "$dst" "$?" "$required" 0
}

# Top-level folders left out of a config tree (session data is copied
# separately; the rest is cache or machine state).
config_excludes() {
    for d in projects sessions file-history _session_backup_premove cache debug \
             downloads shell-snapshots session-env statsig telemetry ide backups paste-cache; do
        printf -- '--exclude=/%s\n' "$d"
    done
    printf -- '--exclude=.credentials.json\n--exclude=.claude.json\n--exclude=/history.jsonl\n'
}

documents_item() {
    src="$DOCS_SRC"
    dst="$MROOT/documents"
    if [ -z "$src" ] || [ ! -d "$src" ]; then
        log WARN "OneDrive Documents not found, skipped (set DOCUMENTS_SOURCE)"
        add_item "documents" "$src" "source_missing" 0 0
        return
    fi
    if ! "$RSYNC" --help 2>&1 | grep -q -- '--files-from'; then
        log WARN "$RSYNC has no --files-from, so cloud-only files cannot be skipped."
        log WARN "Documents skipped. Fix: brew install rsync"
        add_item "documents" "$src" "skipped" 0 0
        return
    fi
    [ "$PRUNE" = 1 ] && log WARN "--prune is not applied to Documents (file-list mode)."
    shrink_check "documents" "$src" "$dst"
    mkdir -p "$dst"

    # List local files only. stat %Xf = file flags in hex; bit 0x40000000
    # (SF_DATALESS) marks a cloud-only file. Reading flags never downloads.
    list=$(mktemp -t docs_list)
    (cd "$src" && find . \( -type d \( -name node_modules -o -name .venv -o -name venv \
            -o -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \
            -o -name .ruff_cache -o -name .ipynb_checkpoints -o -name .tox \) \) -prune \
            -o -type f ! -name '~$*' ! -name '*.tmp' ! -name '.DS_Store' -print0 2>/dev/null |
        xargs -0 stat -f '%Xf%t%N' 2>/dev/null) |
        awk -F '\t' '{
            f = $1; while (length(f) < 8) f = "0" f
            if (substr(f, length(f) - 7, 1) ~ /[4567cdefCDEF]/) { cloud++ }
            else { print substr($2, 3) }
        } END { printf "%d\n", cloud > "/dev/stderr" }' >"$list" 2>"$list.cloud"
    cloud=$(cat "$list.cloud" 2>/dev/null)
    [ "${cloud:-0}" -gt 0 ] && log INFO "documents: $cloud cloud-only files skipped (not downloaded)"

    "$RSYNC" -a --files-from="$list" "$src/" "$dst/" >>"$LOG" 2>&1
    code=$?
    rm -f "$list" "$list.cloud"
    finish_item "documents" "$src" "$dst" "$code" 0 1
}

# --- Run -------------------------------------------------------------
log INFO "Backup starting (personal + work accounts + Documents) - mode: $MODE"
log INFO "Destination: $MROOT"
[ "$PRUNE" = 1 ] && log WARN "Mode: PRUNE - stale backup files will be removed"
if [ -z "$RSYNC" ]; then
    log ERROR "rsync not found. Nothing was copied."
    exit 1
fi

# Config snapshot (always)
SNAP="$SNAPROOT/$STAMP"
mkdir -p "$SNAP"
CFG_COPIED=0
snap() {
    if [ -f "$2" ]; then cp -p "$2" "$SNAP/$1" && CFG_COPIED=$((CFG_COPIED + 1))
    else log WARN "config not present, skipped: $2"; fi
}
snap claude_desktop_config.json   "$DESKTOP/claude_desktop_config.json"
snap desktop_config.json          "$DESKTOP/config.json"
snap personal_dot_claude.json     "$HOME/.claude.json"
snap personal_settings.json       "$PERSONAL/settings.json"
snap personal_settings_local.json "$PERSONAL/settings.local.json"
snap personal_history.jsonl       "$PERSONAL/history.jsonl"
snap work_dot_claude.json         "$WORK/.claude.json"
snap work_settings.json           "$WORK/settings.json"
snap work_history.jsonl           "$WORK/history.jsonl"
snap work_policy_limits.json      "$WORK/policy-limits.json"
log INFO "Config snapshot: $CFG_COPIED files -> $SNAP"

ls -1d "$SNAPROOT"/*/ 2>/dev/null | sort -r | tail -n +$((KEEP_SNAPSHOTS + 1)) |
    while IFS= read -r old; do rm -rf "$old"; log INFO "Pruned old snapshot: $old"; done

if [ "$MODE" != "config_only" ]; then
    if [ "$MODE" != "documents_only" ]; then
        # $(config_excludes) is split into words on purpose: one --exclude each.
        mirror_item personal_projects               "$PERSONAL/projects" 1
        mirror_item personal_file_history           "$PERSONAL/file-history" 0
        mirror_item personal_session_backup_premove "$PERSONAL/_session_backup_premove" 0
        mirror_item personal_config                 "$PERSONAL" 1 $(config_excludes)
        mirror_item work_projects                   "$WORK/projects" 0
        mirror_item work_file_history               "$WORK/file-history" 0
        mirror_item work_config                     "$WORK" 0 $(config_excludes)
        mirror_item desktop_code_sessions           "$DESKTOP/claude-code-sessions" 1
        mirror_zip_item desktop_agent_mode_sessions "$DESKTOP/local-agent-mode-sessions" 1
    fi
    # Documents last, so a slow Documents run never delays Claude data.
    [ "$MODE" != "claude_data_only" ] && documents_item
fi

[ -f "$SNAP/claude_desktop_config.json" ] || GAPS="$GAPS claude_desktop_config.json"
if [ -n "$GAPS" ]; then
    log WARN "INCOMPLETE - these required paths were not found:$GAPS"
fi

ls -1 "$LOGDIR"/backup_*.log 2>/dev/null | sort -r | tail -n +$((KEEP_LOGS + 1)) |
    while IFS= read -r old; do rm -f "$old"; done

# --- Manifest --------------------------------------------------------
ELAPSED=$(( $(date +%s) - STARTED ))
[ "$PRUNE" = 1 ] && MODE="${MODE}_with_prune"
COMPLETE=true
{ [ -n "$FAILURES" ] || [ -n "$GAPS" ]; } && COMPLETE=false
cat >"$MROOT/last_backup_manifest.json" <<EOF
{
  "format_version": 2,
  "backup_completed_at": "$(date +%Y-%m-%dT%H:%M:%S%z)",
  "elapsed_seconds": $ELAPSED,
  "mode": "$MODE",
  "scope": "personal_work_documents",
  "source_os": "macos",
  "machine": "$(json_escape "$HOST")",
  "machine_folder": "$MACHINE",
  "source_home": "$(json_escape "$HOME")",
  "source_documents": "$(json_escape "$DOCS_SRC")",
  "source_desktop_dir": "$(json_escape "$DESKTOP")",
  "destination": "$(json_escape "$MROOT")",
  "mirror_total_mb": $((TOTAL_KB / 1024)),
  "config_snapshot": "$(json_escape "$SNAP")",
  "config_files_copied": $CFG_COPIED,
  "items": [$ITEMS_JSON
  ],
  "failures": $(json_list "$FAILURES"),
  "appdata_gaps": $(json_list "$GAPS"),
  "shrink_warnings": $(json_list "$SHRINKS"),
  "complete": $COMPLETE
}
EOF

log INFO "Done in ${ELAPSED}s. Backup total: $((TOTAL_KB / 1024)) MB"
if [ -n "$FAILURES" ]; then log ERROR "FAILED:$FAILURES"; exit 1; fi
[ -n "$GAPS" ] && exit 2   # incomplete, but not failed
log INFO "Backup complete."
exit 0
