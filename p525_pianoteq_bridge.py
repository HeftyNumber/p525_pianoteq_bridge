#!/usr/bin/env python3

# MIT License - Copyright (c) 2024-2026
# See LICENSE file for details.

"""
Yamaha P-525 Polytouch Intercept & Resolution Driver Bridge.

This production utility operates as a real-time virtual MIDI interface layer
running between the physical keyboard chassis engine and host audio components
(such as Modartt Pianoteq).

It continuously captures custom Yamaha polyphonic key release tags, tracks structural
millisecond-precision time differentials during structural liftoff frames, and
references a precomputed array structure to scale real-time dynamic release velocity
across a comprehensive range of MIDI 1.0 values. It also filters out redundant
or unused controller messages like CC 19 acceleration tracking data.
"""

import time
import rtmidi
import signal
import sys
import math
from wakepy import keep  # Integrated to natively handle DBus inhibition on Arch Linux (KDE)

# ==============================================================================
#                      TUNABLE PERFORMANCE PROFILE VARIABLES
# ==============================================================================

# --- 1. Note-Off Velocity Curve Configuration ---
# Controls the exponential scaling behavior of structural finger releases.
# Higher settings require more aggressive, snappy key movement profiles to trigger
# high velocity outputs, while lower parameters soften the overall calculation range.
RELEASE_CURVE_MULTIPLIER = 60.0

# --- 2. Fallback Safety Baseline Velocity ---
# The default release velocity mapped down the line if an active note-off event is
# triggered without a corresponding polyphonic hardware timing tracker token.
FALLBACK_RELEASE_VELOCITY = 64

# --- 3. Proactive System Memory Management ---
# The maximum duration (in seconds) the script is allowed to preserve a key-release
# tracker state inside the system cache before clearing it out. Protects against
# memory leaks and orphaned array states during complex polyphonic passages.
STALE_TIMEOUT_SEC = 1.0

# ==============================================================================
#                     PRECOMPUTED LOOKUP TABLES (LUT)
# ==============================================================================
# Yamaha P-525 hardware liftoff differentials generally fall within a 2ms to 100ms
# window frame. To maintain optimal timing stability under dense polyphonic conditions,
# dynamic runtime math blocks are replaced by a high-resolution array lookup table.
#
# Values are calculated down to individual millisecond resolution bands (0 to 1,000ms),
# dropping execution complexity down to a simple integer array index access.

MAX_LUT_MS = int(STALE_TIMEOUT_SEC * 1000)
RELEASE_VELOCITY_LUT = [0] * (MAX_LUT_MS + 1)

def precompute_release_lut():
    """
    Builds the structural lookup table structure during script boot sequences.
    Applies the mathematical exponential decay function across all millisecond increments
    and maps the results directly into valid MIDI velocity bounds.
    """
    for ms in range(MAX_LUT_MS + 1):
        delta_time = ms / 1000.0

        # Calculate raw exponential value matching physical decay properties
        calculated_velocity = int(127 * math.exp(-RELEASE_CURVE_MULTIPLIER * delta_time))

        # --- Transparent Passthrough Clamping Boundary ---
        # Caps the top range at the absolute MIDI maximum of 127.
        # Enforces a minimum velocity floor of 1 instead of 0. This is done because the
        # MIDI specification treats note-off 0 as an undefined state, causing hosts like
        # Pianoteq to automatically overwrite it back up to 64. A value of 1 keeps the
        # signal path valid and allows full calibration control within host software graphs.
        if calculated_velocity > 127:
            val = 127
        elif calculated_velocity < 1:
            val = 1
        else:
            val = calculated_velocity

        RELEASE_VELOCITY_LUT[ms] = val

# Pre-populate the look-up table array space before spawning background hardware threads
precompute_release_lut()

# ==============================================================================
#                     CORE RENDERING ENGINE & INTERCEPT LOOPS
# ==============================================================================

# Initialize virtual system MIDI inputs and outputs
midi_in = rtmidi.MidiIn()
midi_out = rtmidi.MidiOut()

# Configure the driver client identification name block for system subsystem frameworks
midi_in.set_client_name("P525_FixO")
midi_out.set_client_name("P525_FixO")

# Open clean, low-latency target virtual connection ports
midi_in.open_virtual_port("P525_Fix_In")
midi_out.open_virtual_port("P525_Fix_Out")

# --- Performance Matrix Arrays ---
# Allocation of fixed 128-slot flat arrays mirroring all possible MIDI Note Numbers.
# Using flat lists avoids dictionary allocations, key lookups, and garbage collection
# loops within the high-priority callback thread.
release_tracking = [0.0] * 128
note_states = [False] * 128

# Extract method references directly into local namespace pointers to bypass dynamic
# global table evaluation steps inside fast looping scenarios.
send_message = midi_out.send_message
get_time = time.perf_counter

def process_midi_event(event_data, data=None):
    """
    High-frequency interrupt callback operating inside the host audio framework's
    real-time execution context. Resolves high-resolution key release values using
    fast integer conversion and index lookups, while explicitly suppressing CC 19 logs.
    """
    # Unpack the native rtmidi payload containing the event byte list and delta time
    raw_bytes, timestamp = event_data

    # Fast-drop protection: terminate execution if the packet is corrupt or fragmented
    if not raw_bytes or len(raw_bytes) < 3:
        return

    # Capture the exact clock cycle time at the absolute entry point of the loop
    current_time = get_time()

    # Isolate MIDI values using bitwise operators
    status = raw_bytes[0]
    cmd = status & 0xF0        # Extract core command structure
    channel = status & 0x0F    # Isolate active channel lane
    note = raw_bytes[1]
    velocity = raw_bytes[2]

    # --- 1. Catch Note-On Events (Command 0x90 with velocity > 0) ---
    if cmd == 0x90 and velocity > 0:
        release_tracking[note] = 0.0  # Clear out stale timing entries on restrike frames
        note_states[note] = True      # Mark the note index state as physically active
        send_message(raw_bytes)       # Route the unmodified note-on data forward immediately
        return

    # --- 2. Catch Yamaha Polyphonic Aftertouch Release Flag (0xA0, Value 18) ---
    # The P-525 triggers this specific status byte sequence at the exact millisecond
    # a key leaves the keybed bottom and begins its upward structural transit.
    if cmd == 0xA0 and velocity == 18:
        if note_states[note] and release_tracking[note] == 0.0:
            release_tracking[note] = current_time
        return # Swallow the specialized hardware timing packet from the driver stream

    # --- 3. Intercept and Modify the Note-Off Command (0x80 OR 0x90 running status zero flag) ---
    elif cmd == 0x80 or (cmd == 0x90 and velocity == 0):
        # Drop redundant duplicate note-off messages to safeguard restrike phases
        if not note_states[note]:
            return

        start_time = release_tracking[note]
        release_tracking[note] = 0.0  # Reset state tracking array registers
        note_states[note] = False     # Reset structural key down flag

        out_status = 0x80 | channel

        # Evaluate timestamp validity against configured timeout boundaries
        if start_time > 0.0:
            # Convert elapsed duration into a millisecond integer array index pointer
            delta_ms = int((current_time - start_time) * 1000)

            # Map valid timeframes to the precomputed look-up array
            if delta_ms <= MAX_LUT_MS:
                out_vel = RELEASE_VELOCITY_LUT[delta_ms]
            else:
                out_vel = FALLBACK_RELEASE_VELOCITY
        else:
            # Fall back to baseline configuration defaults if the initial keybed frame was missed
            out_vel = FALLBACK_RELEASE_VELOCITY

        # Assemble new high-resolution MIDI note-off sequence packet and dispatch
        send_message([out_status, note, out_vel])
        return

    # --- 4. Pure Data Pass-Through Channel ---
    # Intercept and block Continuous Controller 19 (Acceleration Tracking) data streams.
    # Command 0xB0 identifies Control Change data; byte 1 (note index variable slot) contains the CC ID.
    if cmd == 0xB0 and note == 19:
        return

    # Forward all other unaffected data streams (Sustain pedals, Pitch Bend, SysEx) with zero delay
    send_message(raw_bytes)

# Register the callback function within the virtual MIDI device engine
midi_in.set_callback(process_midi_event)

print("--- Fast Optimized Lean Realism Bridge Active ---")
print("Routing setup: [Input Engine] -> P525_Fix_In")
print("Routing setup: P525_Fix_Out   -> [Pianoteq]")

# ==============================================================================
#               GRACEFUL INFRASTRUCTURE TERMINATION HANDLING
# ==============================================================================
def clean_exit(signum, frame):
    """
    Maintains clean state transitions across system architecture frameworks,
    ensuring virtual drivers drop cleanly without creating orphaned configurations.
    """
    print("\nClosing optimized ports cleanly and releasing OS MIDI resources...")
    midi_in.close_port()
    midi_out.close_port()
    print("KDE Desktop Lock State: Sleep and Screen Locking are now UNBLOCKED.")
    sys.exit(0)

# Bind system signals to clean termination routines
signal.signal(signal.SIGTERM, clean_exit)
signal.signal(signal.SIGINT, clean_exit)

# ==============================================================================
#             PRODUCTION OS POWER PROFILES INHIBITION BLOCK
# ==============================================================================
# Interacts with the local freedesktop DBus desktop framework to guarantee high-
# priority performance stability. Instantiating this layer stops automated energy-
# saving suspension states, monitors screen dimming parameters, and halts system
# lockouts while dense automated live tracking sequences are active.
print("Initializing system environment permissions...")

# The wakepy 'keep.presenting()' configuration generates a contextual lock mode.
# When active, it communicates over the desktop user session bus to suppress
# 'org.freedesktop.ScreenSaver' and 'org.freedesktop.PowerManagement' timeouts.
with keep.presenting():
    print("KDE Desktop Lock State: Sleep and Screen Locking are now BLOCKED.")
    print("--- Fast Optimized Lean Realism Bridge Active ---")
    print("Routing setup: [Input Engine] -> P525_Fix_In")
    print("Routing setup: P525_Fix_Out   -> [Pianoteq]")

    # Hold parent thread execution path with minimal background processor utilization.
    # Using an extended thread suspend delay prevents polling loops from robbing CPU
    # cycles away from the high-frequency asynchronous rtmidi event thread.
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        # Intercept manual shell interrupts to cleanly process global hardware unlinking
        clean_exit(None, None)
