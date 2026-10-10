# P525 Pianoteq Bridge - Agent Guide

## Project Overview
A Python MIDI bridge that captures P525 keyboard polytouch release velocity and converts it to MIDI for Pianoteq. Uses `rtmidi` (input) and `mido` (testing) packages.

## Key Files
- **`p525_pianoteq_bridge.py`** - Main daemon. Runs as background process.
- **`midi_test_player.py`** - Test utility to play MIDI files into the bridge.

## Dependencies
- `rtmidi` - MIDI I/O
- `mido` - MIDI file playback (testing only)

## Execution Flow

### Starting the Bridge
```bash
python3 p525_pianoteq_bridge.py
```
Creates virtual ports:
- Input: `P525_Fix_In`
- Output: `P525_Fix_Out` → connects to Pianoteq

### Testing with MIDI File
```bash
python3 midi_test_player.py
```
Selects a `.mid` file and routes playback to `MIDI_Test_Player_Out` → connect to `P525_Fix_In` via patchbay.

## Critical Tunable Parameters (`p525_pianoteq_bridge.py`)

```python
RELEASE_CURVE_MULTIPLIER = 450    # Higher = faster decay, requires slower finger releases
FALLBACK_RELEASE_VELOCITY = 64    # Used if polytouch start flag is missed
STALE_TIMEOUT_SEC = 1.0           # Key-release timestamp cache expiry
```

### How Velocity Calculation Works
1. Note-Off timestamp is recorded when polytouch "release" flag (cmd 0xA0, value 18) arrives
2. On actual note-off (0x80 or 0x90 with velocity=0), delta time is calculated
3. Velocity = `127 - (delta_time * RELEASE_CURVE_MULTIPLIER)`
4. Clamped to 0-127; fallback to 64 if timestamp expired

## Common Pitfalls

1. **Port connection**: Bridge uses virtual ports. Physical patchbay or RaySession required to connect `P525_Fix_Out` to Pianoteq's MIDI input.
2. **Signal handling**: Uses `SIGINT`/`SIGTERM` for clean shutdown. Don't kill forcefully.
3. **Yamaha polytouch tags**: The release flag (0xA0, val=18) is detected but NOT sent to Pianoteq—only used for timing.
4. **Memory management**: Release timestamps expire after `STALE_TIMEOUT_SEC` to prevent leaks.
5. **Performance optimization**: Uses pre-allocated list `[0.0] * 128` for 128 MIDI notes to avoid dict/hashing overhead in interrupt loop.

## Testing
```bash
# Run bridge
python3 p525_pianoteq_bridge.py
# In another terminal, play MIDI into P525_Fix_In
python3 midi_test_player.py
```
