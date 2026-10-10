#!/bin/bash
# Wrapper script to run the MIDI test player with the virtual environment activated.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
TEST_SCRIPT="$SCRIPT_DIR/midi_test_player.py"

# Check if virtual environment exists
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "Error: Virtual environment not found at $SCRIPT_DIR/.venv"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install rtmidi mido wakepy"
    exit 1
fi

# Check if test script exists
if [[ ! -f "$TEST_SCRIPT" ]]; then
    echo "Error: Test script not found at $TEST_SCRIPT"
    exit 1
fi

# Execute with venv python
exec "$VENV_PYTHON" "$TEST_SCRIPT"