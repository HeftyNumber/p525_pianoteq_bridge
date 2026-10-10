# P525 Pianoteq Bridge - Agent Guide

## Project Overview
A Python MIDI bridge that captures P525 keyboard polytouch release velocity and converts it to MIDI for Pianoteq. Uses `rtmidi` for MIDI I/O and `wakepy` for system power management inhibition on Linux (KDE/DBus). Includes `mido` for MIDI file playback (testing only).

## Key Files
- **`p525_pianoteq_bridge.py`** - Main daemon. Runs as background process.
- **`midi_test_player.py`** - Test utility to play MIDI files into the bridge.

## Dependencies
- `rtmidi` - MIDI I/O
- `mido` - MIDI file playback (testing only)
- `wakepy` - System sleep/screen lock inhibition (Linux KDE/DBus)

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
Selects a `.mid` file and routes playback to `MIDI_Test_Player_Out` → connect to `P525_Fix_In` via patchbay (e.g., qpwgraph, Carla, RaySession, or `aconnect`).

**Note on testing:** The included MIDI test file is a practice recording from the P-525 with typical polytouch output. To properly test the bridge:
1. Start the bridge: `python3 p525_pianoteq_bridge.py`
2. In your patchbay (qpwgraph/Carla/RaySession), connect:
   - `MIDI_Test_Player_Out` → `P525_Fix_In`
   - `P525_Fix_Out` → Pianoteq MIDI input
3. Start Pianoteq and open its MIDI monitor window
4. Run the test player: `python3 midi_test_player.py` and select the test MIDI file
5. Watch the Pianoteq MIDI monitor to verify note-off velocities are being modified (you should see varying release velocities instead of all 64)

## Critical Tunable Parameters (`p525_pianoteq_bridge.py`)

```python
RELEASE_CURVE_MULTIPLIER = 60.0    # Exponential decay factor for release velocity curve
FALLBACK_RELEASE_VELOCITY = 64     # Used if polytouch start flag is missed
STALE_TIMEOUT_SEC = 1.0            # Key-release timestamp cache expiry (seconds)
```

### How Velocity Calculation Works
1. **Note-On** (0x90, velocity > 0): Note state marked active, tracking array cleared
2. **Polytouch Release Flag** (0xA0, value 18): Timestamp captured at exact key liftoff moment (swallowed, not forwarded)
3. **Note-Off** (0x80 or 0x90 velocity=0): Delta time calculated from polytouch timestamp
4. **Velocity** = `127 * exp(-RELEASE_CURVE_MULTIPLIER * delta_time_seconds)` via precomputed LUT
5. **Clamped** to 1-127 (minimum 1, not 0, because MIDI note-off velocity 0 is undefined and hosts like Pianoteq reset it to 64)
6. **Fallback** to `FALLBACK_RELEASE_VELOCITY` (64) if timestamp expired (>1s) or missed

### Lookup Table (LUT)
- Precomputed at startup for millisecond precision (0 to `STALE_TIMEOUT_SEC * 1000` ms)
- Replaces runtime math with O(1) array index access in the real-time callback
- `MAX_LUT_MS = int(STALE_TIMEOUT_SEC * 1000)` = 1000 entries by default

## Common Pitfalls

1. **Port connection**: Bridge uses virtual ports. Physical patchbay (qpwgraph, Carla, `aconnect`) required to connect `P525_Fix_Out` to Pianoteq's MIDI input.
2. **Signal handling**: Uses `SIGINT`/`SIGTERM` for clean shutdown. Don't kill forcefully.
3. **Yamaha polytouch tags**: The release flag (0xA0, val=18) is detected for timing but NOT sent to Pianoteq—swallowed by the bridge.
4. **CC 19 filtering**: Continuous Controller 19 (acceleration tracking) is explicitly blocked and not forwarded.
5. **Memory management**: Release timestamps expire after `STALE_TIMEOUT_SEC` to prevent leaks during complex polyphonic passages.
6. **Performance optimization**: Uses pre-allocated lists `[0.0] * 128` for 128 MIDI notes to avoid dict/hashing overhead in the interrupt callback.
7. **Minimum velocity of 1**: Note-off velocity 0 is treated as undefined by MIDI spec; Pianoteq and other hosts auto-correct it to 64. The bridge clamps minimum to 1.

## System Integration (Linux/KDE)
The bridge uses `wakepy.keep.presenting()` to inhibit:
- Screen saver (`org.freedesktop.ScreenSaver`)
- Power management (`org.freedesktop.PowerManagement`)
This prevents sleep/screen lock during performance. You'll see console messages:
```
KDE Desktop Lock State: Sleep and Screen Locking are now BLOCKED.
```
On clean exit:
```
KDE Desktop Lock State: Sleep and Screen Locking are now UNBLOCKED.
```

## Testing
```bash
# Terminal 1: Run bridge
python3 p525_pianoteq_bridge.py

# Terminal 2: In patchbay, connect MIDI_Test_Player_Out -> P525_Fix_In -> P525_Fix_Out -> Pianoteq
# Open Pianoteq MIDI monitor window

# Terminal 2: Play MIDI into P525_Fix_In
python3 midi_test_player.py
# Select the test MIDI file when prompted
# Watch Pianoteq MIDI monitor for varying note-off velocities
```
