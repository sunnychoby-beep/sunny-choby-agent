#!/bin/bash
LA="$HOME/Library/LaunchAgents"
for f in com.sunnychoby.linkedin-agent.plist com.sunnychoby.linkedin-agent.draft.plist com.sunnychoby.linkedin-agent.check.plist; do
  launchctl bootout "gui/$(id -u)" "$LA/$f" 2>/dev/null || true
  rm -f "$LA/$f"
done
echo "Schedule removed."
