#!/bin/bash
# Installs the schedule on this Mac (survives restart):
#   8:30 AM daily  -> draft 2 posts, ask YES / NO on Telegram
#   every 5 min    -> read reply, post at 9 AM and 6 PM after YES
set -e
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LA="$HOME/Library/LaunchAgents"
mkdir -p "$LA" "$AGENT_DIR/logs"
# Remove the older single-job schedule if present.
launchctl bootout "gui/$(id -u)" "$LA/com.sunnychoby.linkedin-agent.plist" 2>/dev/null || true
rm -f "$LA/com.sunnychoby.linkedin-agent.plist"
for job in draft check; do
  TARGET="$LA/com.sunnychoby.linkedin-agent.$job.plist"
  sed "s#__AGENT_DIR__#$AGENT_DIR#g" "$AGENT_DIR/schedule/$job.plist" > "$TARGET"
  launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$TARGET"
done
echo "Installed: drafts at 8:30 AM, replies checked every 5 minutes."
