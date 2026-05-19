#!/bin/bash
# PostToolUse hook — validate file syntax immediately after Edit or Write

PAYLOAD=$(cat)
FILE=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path','') or d.get('tool_input',{}).get('path',''))" 2>/dev/null)

[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0

EXT="${FILE##*.}"

case "$EXT" in
  sh)
    if ! bash -n "$FILE" 2>&1; then
      echo "[post-edit] WARNING: bash syntax error in $FILE" >&2
    fi
    ;;
  json)
    if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$FILE" 2>&1; then
      echo "[post-edit] WARNING: JSON syntax error in $FILE" >&2
    fi
    ;;
  py)
    if ! python3 -m py_compile "$FILE" 2>&1; then
      echo "[post-edit] WARNING: Python syntax error in $FILE" >&2
    fi
    ;;
esac

exit 0
