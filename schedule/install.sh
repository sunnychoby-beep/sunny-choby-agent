#!/bin/bash
# Installs the 9 AM / 6 PM schedule on this Mac (runs even after restart).
set -e
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/Library/LaunchAgents/com.sunnychoby.linkedin-agent.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$AGENT_DIR/logs"
sed "s#__AGENT_DIR__#$AGENT_DIR#g" "$AGENT_DIR/schedule/com.sunnychoby.linkedin-agent.plist" > "$TARGET"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
echo "Installed. Runs daily at 9:00 AM and 6:00 PM."
