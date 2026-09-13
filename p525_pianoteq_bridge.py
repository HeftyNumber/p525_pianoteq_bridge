#!/usr/bin/env python3
import time
import rtmidi
import signal
import sys

# ==============================================================================
#                      TUNABLE PERFORMANCE PROFILE VARIABLES
# ==============================================================================

# --- 1. Note-Off Velocity Curve Configuration ---
# Dictates how fast or slow finger releases scale down into MIDI values (0-127).
# Higher values (e.g., 450-600) compress the response curve, meaning your
# releases must be incredibly slow to hit quiet damper values. Lower values
# require your finger to snap off the key aggressively to get high values.
RELEASE_CURVE_MULTIPLIER = 450

# --- 2. Fallback Safety Baseline Velocity ---
# The default release velocity applied if a note-off command is detected
# but the initial hardware polytouch sensor start flag was missed or skipped.
FALLBACK_RELEASE_VELOCITY = 64

# --- 3. Proactive System Memory Management ---
# Strict timeframe (in seconds) to retain a key-release timestamp in cache.
# Prevents memory leaks and corrupted next-strikes if a hardware message drops.
STALE_TIMEOUT_SEC = 1.0

# ==============================================================================
#                     CORE RENDERING ENGINE & INTERCEPT LOOPS
# ==============================================================================

# Initialize virtual system MIDI inputs and outputs
midi_in = rtmidi.MidiIn()
midi_out = rtmidi.MidiOut()

# Configure the driver client identification name block for ALSA/JACK/PipeWire frameworks
midi_in.set_client_name("P525_FixO")
midi_out.set_client_name("P525_FixO")

# Expose clean, low-latency target virtual connection ports
midi_in.open_virtual_port("P525_Fix_In")
midi_out.open_virtual_port("P525_Fix_Out")

# --- Performance Matrix Setup ---
# Allocation of a fixed 128-slot tracking structure mirroring every possible MIDI Note Number.
# Elements track: [Last Struck Timestamp (float)] where 0.0 represents an inactive state.
#
# PERFORMANCE MECHANICS EXPLAINED:
# Pre-allocating this flat list structure fully circumvents runtime dictionary allocations,
# key hash collisions, and Python garbage collection cycles. Index lookups execute in O(1)
# constant time directly from continuous memory blocks during dense polyphonic performance.
release_tracking = [0.0] * 128

# --- Dynamic Local Cache Strategy ---
# Extracting core external methods directly into the local namespace boundary.
# This prevents costly dynamic global lookups inside the time-critical event cycle.
send_message = midi_out.send_message
get_time = time.perf_counter

def process_midi_event(event_data, data=None):
    """
    High-frequency interrupt callback running inside a high-priority hardware thread.
    Calculates dynamic note-off release velocity based on Yamaha polytouch tags.
    """
    # Unpack the native rtmidi payload containing the event byte list and delta time
    raw_bytes, timestamp = event_data
    
    # Fast-drop condition: Terminate execution instantly if the byte array is corrupt or incomplete
    if not raw_bytes or len(raw_bytes) < 3:
        return

    # Query system clock instantly to preserve the exact entry window frame
    current_time = get_time()
    
    # Extract fundamental MIDI protocol variables using low-overhead index pointers
    status = raw_bytes[0]
    cmd = status & 0xF0        # Bitwise AND masks out the channel bits to extract the core command
    channel = status & 0x0F    # Bitwise AND isolates the active MIDI channel (0-15)
    note = raw_bytes[1]
    velocity = raw_bytes[2]

    # --- 1. Catch Note-On to Reset Memory Registers (Command 0x90 with velocity > 0) ---
    if cmd == 0x90 and velocity > 0:
        release_tracking[note] = 0.0  # Instantly wipe stale release timers on restrike
        send_message(raw_bytes)       # Route the original un-altered Note On payload down the wire
        return

    # --- 2. Catch Yamaha Polyphonic Aftertouch Release Flag (Command 0xA0, Value 18) ---
    elif cmd == 0xA0 and velocity == 18:
        # If no timer is currently active for this note, log the release initiation timestamp
        if release_tracking[note] == 0.0:
            release_tracking[note] = current_time
        return # Yamaha specific physical hardware tag. Swallow and drop; do not route to Pianoteq.

    # --- 3. Intercept and Modify the Note-Off Command (0x80 OR 0x90 running status zero flag) ---
    elif cmd == 0x80 or (cmd == 0x90 and velocity == 0):
        start_time = release_tracking[note]
        release_tracking[note] = 0.0  # Consume token immediately to reset state safely

        # Enforce clean standard 0x80 note_off status byte across legacy MIDI engines
        out_status = 0x80 | channel

        # Evaluate timestamp integrity against customizable safety expiration thresholds
        if start_time > 0.0 and (current_time - start_time) <= STALE_TIMEOUT_SEC:
            delta_time = current_time - start_time
            
            # Evaluates against customizable release curve math
            calculated_velocity = int(127 - (delta_time * RELEASE_CURVE_MULTIPLIER))
            
            # Low-latency structural conditional clamping structure.
            # Avoids calling Python's expensive max() / min() stack layer changes.
            if calculated_velocity > 127:
                out_vel = 127
            elif calculated_velocity < 0:
                out_vel = 0
            else:
                out_vel = calculated_velocity
        else:
            # Force standard baseline velocity fallback for expired or missed timing elements
            out_vel = FALLBACK_RELEASE_VELOCITY

        # Generate a fresh valid mutable byte list package securely rather than mutating raw tuples
        send_message([out_status, note, out_vel])
        return

    # --- 4. Pure Data Pass-Through Channel ---
    # Route all unaffected controller streams (CC, Pitch Bends, Aftertouch, SysEx) with zero delay.
    send_message(raw_bytes)

# Inject the streamlined intercept hook straight into the active virtual input engine
midi_in.set_callback(process_midi_event)

print("--- Fast Optimized Lean Realism Bridge Active ---")
print("Routing setup: [Input Engine] -> P525_Fix_In")
print("Routing setup: P525_Fix_Out   -> [Pianoteq]")

# --- Graceful RaySession Infrastructure Termination Handling ---
def clean_exit(signum, frame):
    print("\nClosing optimized ports cleanly and releasing OS MIDI resources...")
    midi_in.close_port()
    midi_out.close_port()
    sys.exit(0)

# Bind system signals to termination handling mechanism to prevent lingering ghost port states
signal.signal(signal.SIGTERM, clean_exit)
signal.signal(signal.SIGINT, clean_exit)

# Secure the background parent process thread with nominal power usage parameters
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    clean_exit(None, None)

