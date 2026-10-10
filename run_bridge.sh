#!/bin/bash
# Wrapper script to run the bridge with the virtual environment activated.
# Use this script in RaySession / patchbay instead of the .py file directly.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
BRIDGE_SCRIPT="$SCRIPT_DIR/p525_pianoteq_bridge.py"

# Check if virtual environment exists
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "Error: Virtual environment not found at $SCRIPT_DIR/.venv"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install rtmidi mido wakepy"
    exit 1
fi

# Check if bridge script exists
if [[ ! -f "$BRIDGE_SCRIPT" ]]; then
    echo "Error: Bridge script not found at $BRIDGE_SCRIPT"
    exit 1
fi

# Execute with venv python
exec "$VENV_PYTHON" "$BRIDGE_SCRIPT"