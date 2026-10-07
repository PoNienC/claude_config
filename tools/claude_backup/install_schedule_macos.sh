#!/bin/bash
# Install (or re-install) the nightly 22:00 backup on macOS via launchd.
# Twin of the Windows scheduled task claude_data_backup.
#
# launchd runs a missed 22:00 job when the Mac next wakes, like the
# Windows task's "start when available".
#
# Usage: bash ~/.claude/tools/claude_backup/install_schedule_macos.sh

LABEL="local.ponien.nightly_backup"
SCRIPT="$HOME/.claude/tools/claude_backup/backup_macos.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
OUT="$HOME/Library/Logs/nightly_backup.log"

if [ ! -f "$SCRIPT" ]; then
    echo "Backup script not found: $SCRIPT"
    exit 1
fi
chmod +x "$SCRIPT"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$OUT</string>
    <key>StandardErrorPath</key>
    <string>$OUT</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST" || exit 1
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" || exit 1

echo "Installed $LABEL - runs daily at 22:00."
echo "Run it now:   launchctl kickstart gui/$(id -u)/$LABEL"
echo "Output log:   $OUT"
echo "If the log shows 'Operation not permitted', add /bin/bash under"
echo "System Settings > Privacy & Security > Full Disk Access, then run it again."
