#!/bin/bash
TARGET="$HOME/Library/LaunchAgents/com.sunnychoby.linkedin-agent.plist"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
rm -f "$TARGET"
echo "Schedule removed."
