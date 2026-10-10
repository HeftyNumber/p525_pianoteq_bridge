#!/usr/bin/env python3

# MIT License - Copyright (c) 2024-2026
# See LICENSE file for details.

import sys
import time
import signal
import rtmidi
from mido import MidiFile
import tkinter as tk
from tkinter import filedialog

def choose_midi_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(
        title="Select MIDI File to Play",
        filetypes=[("MIDI Files", "*.mid *.midi")]
    )
    root.destroy()
    return file_path

midi_file_path = choose_midi_file()
if not midi_file_path:
    print("No file selected. Exiting.")
    sys.exit(0)

# Initialize and expose a dedicated Virtual Output Port
midi_out = rtmidi.MidiOut()
midi_out.set_client_name("MIDI_Test_Player")
midi_out.open_virtual_port("MIDI_Test_Player_Out")

print("Exposed virtual port: MIDI_Test_Player_Out")
print("Connect this port to 'P525_Fix_In' using your patchbay or RaySession.")

def clean_exit(signum, frame):
    print("\nStopping... Closing MIDI port.")
    midi_out.close_port()
    sys.exit(0)

signal.signal(signal.SIGTERM, clean_exit)
signal.signal(signal.SIGINT, clean_exit)

try:
    mid = MidiFile(midi_file_path)
    print(f"Loaded: {midi_file_path}. Starting playback...")

    for msg in mid.play():
        if not msg.is_meta:
            # Broadcast straight out of our own virtual port
            midi_out.send_message(msg.bytes())

    print("Playback completed successfully.")
except KeyboardInterrupt:
    print("\nPlayback aborted.")
finally:
    midi_out.close_port()
