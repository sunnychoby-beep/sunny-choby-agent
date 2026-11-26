#!/bin/bash
# Runs the agent once: ./run.sh draft  or  ./run.sh check
# Uses your Claude Code subscription login. No API key.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin"
unset ANTHROPIC_API_KEY
mkdir -p logs
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python agent.py "$@" >> "logs/$(date +%Y-%m).log" 2>&1
