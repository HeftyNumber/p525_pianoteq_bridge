# Yamaha P-525 Polytouch Bridge: Architecture & Flow Overview

### **Program Flow Diagram**

```text
[Start: Script Boot Sequence]
               │
               ▼
┌───────────────────────────────┐
│  Precompute Release Velocity  │  (Populates 1,000ms Array via
│     Lookup Table (LUT)        │   Exponential Decay Formula)
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│   Initialize Virtual MIDI     │  (Registers Ports: "P525_Fix_In"
│     & Callback Thread         │   and "P525_Fix_Out")
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│   Inhibit OS Power-Saving     │  (Uses wakepy to prevent system
│  (DBus / Screen Lock Block)   │   sleep during live performance)
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│     Main Sleep Loop           │◄────────────────────────┐
│  (Holds thread open safely)   │                         │
└───────────────────────────────┘                         │
                                                          │
   ================== ASYNCHRONOUS MIDI INTERRUPT LAYER ==│===============
   (Triggers immediately whenever a MIDI event arrives on the input port)
                                                          │
                        [ Incoming MIDI Event ]           │
                                   │                      │
                                   ▼                      │
                        Isolate Status Command            │
                                   │                      │
         ┌─────────────────────────┼──────────────────────┴──┐
         │ Note-On                 │ Poly Aftertouch (0xA0)  │ Note-Off (0x80 or Vol 0)
         ▼                         ▼                         ▼
 ┌───────────────┐         ┌───────────────┐         ┌───────────────────────┐
 │ Mark note as  │         │ If note is    │         │ Calculate duration:   │
 │ active;       │         │ active, cache │         │ current - start_time  │
 │ pass-through  │         │ current time  │         └───────────┬───────────┘
 │ unmodified.   │         │ as liftoff.   │                     │
 └───────┬───────┘         └───────┬───────┘                     ▼
         │                         │                 Mapped to LUT index?
         │                         │                  ├── Yes ➔ Get LUT Vel
         │                         │                  └── No  ➔ Get Fallback Vel
         │                         │                             │
         │                         │                             ▼
         │                         │                 ┌───────────────────────┐
         │                         │                 │ Generate new Note-Off │
         │                         │                 │ with scaled velocity; │
         │                         │                 │ forward to output.    │
         │                         │                 └───────────┬───────────┘
         │                         │                             │
         └─────────────────────────┼─────────────────────────────┘
                                   │
                                   ├─► [CC 19 Message] ──► (Swallowed / Dropped)
                                   │
                                   └─► [Other (Sustain)] ─► (Pass-through unmodified)
```

***

### **Detailed Program Explanation**

This production driver utility acts as a specialized, low-latency **MIDI modifier bridge** positioned between a Yamaha P-525 digital piano and host audio software (like Modartt Pianoteq). Its primary objective is to capture physical key liftoff timing data and translate it into realistic, dynamic **MIDI Note-Off release velocities**.

The program operations break down into three major phases:

#### **1. Boot & Table Initialization**
* **Precomputing Math (`precompute_release_lut`)**: Real-time exponential math calculations can introduce micro-delays that disrupt musical timing stability. To bypass this, the script runs an initialization calculation during boot. It maps physical exponential decay properties across a 1,000-millisecond spectrum directly into an integer array (Lookup Table).
* **MIDI Port Setup**: The script provisions virtual input (`P525_Fix_In`) and output (`P525_Fix_Out`) endpoints using the `rtmidi` framework, allowing external audio engines to route their input cleanly through the script layer.
* **OS Power Invalidation**: Using the `wakepy` module, the program locks system power management states via the desktop DBus engine. This ensures the operating system does not dim the screen or go to sleep during an active performance session.

#### **2. High-Frequency Event Loop (The Callback)**
When the hardware sends a message, `process_midi_event` acts as a real-time hardware interrupt to evaluate incoming commands:
* **Note-On (Key Pressed)**: Marked active inside a flat array layout (`note_states`) and passed along instantly to avoid introducing audible input latency.
* **Polyphonic Aftertouch (`0xA0`)**: The Yamaha P-525 emits a specialized hardware timing packet the exact millisecond a finger begins lifting off a depressed keybed. The script intercepts this event, logs the exact `perf_counter` timestamp into cache memory, and **swallows** the package so it doesn't clutter downstream software.
* **Note-Off (Key Fully Released)**: When the physical key breaks contact completely, the script subtracts the cached liftoff start time from the current time. The resulting millisecond interval is used as an index pointer to pull a precalculated velocity rating from the Lookup Table. A new modified Note-Off MIDI message is then assembled and dispatched to the virtual output.
* **CC 19 and Data Pass-Through**: Continuous Controller 19 acceleration streams are dropped cleanly to conserve system data rates, while vital pedal and pitch data pass through unchanged.

#### **3. Clean Architecture Termination**
* **Signal Handlers**: The utility binds standard termination signals (`SIGINT`, `SIGTERM`) to its teardown routing engine. This guarantees that even if the terminal is killed abruptly, virtual MIDI connection lines unbind safely, OS sleep profiles unlock cleanly, and system resources are freed without creating memory leaks or orphaned hardware flags.
