# Audio Optimization Guide: Arch Linux (PipeWire/JACK)

This guide documents the optimization setup for a dual-purpose laptop workflow (Intel i7-9750H / RTX 2060):
1. **General Media / Gaming:** Run natively at **48000 Hz** (Steam, FreeTube, Firefox) to eliminate CPU resampling overhead.
2. **Music Production:** Switch the entire audio graph automatically to an ultra-low latency **44100 Hz @ 64 samples** *only* when RaySession and Pianoteq are running to natively match a Yamaha P525 digital piano.

---

## Step 1: Global PipeWire Configuration (Baseline)

Ensure PipeWire defaults to 48000 Hz for daily usage but allows switching when demanded by production applications.

1. Create a drop-in configuration file:
   ```bash
   sudo mkdir -p /etc/pipewire/pipewire.conf.d/
   sudo nano /etc/pipewire/pipewire.conf.d/44100-rate.conf
   ```
2. Populate it with the following configuration:
   ```text
   context.properties = {
       default.clock.rate          = 48000
       default.clock.allowed-rates = [ 48000 44100 ]
   }
   ```
3. Restart the PipeWire user services:
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```

---

## Step 2: RaySession & Pianoteq Orchestration (The Fix)

Instead of fragile hardware rules, the system graph is controlled using native PipeWire runtime environment variables inside **RaySession**. This forces a sample-rate shift strictly while the piano session is running.

### Application Configuration inside RaySession:
For the **Pianoteq** process entry in RaySession, separate the configuration into its dedicated GUI fields:

* **Executable Block:** `/path/to/Pianoteq` (or your local binary path)
* **Arguments Block:** *(Any normal flags you pass to Pianoteq)*
* **Environment Variables Block:**
  ```env
  PIPEWIRE_LATENCY="64/44100"
  PIPEWIRE_PROPS="{ node.force-rate=44100 }"
  ```

### Why this works:
* **`PIPEWIRE_LATENCY="64/44100"`**: Binds the synchronous process buffer size (Quantum) strictly to 64 samples at a 44100 Hz scale.
* **`PIPEWIRE_PROPS="{ node.force-rate=44100 }"`**: Bypasses device rules by instructing the audio server to temporarily lock the master hardware clock rate to **44100 Hz** for as long as this process remains active.

---

## Step 3: Verification Commands

Use these commands to verify that the rates are scaling properly between workflows:

1. **Verify Live Rates (Static Snapshot):**
   Run the following terminal pipe to print a non-clearing snapshot of active rates:
   ```bash
   pw-top -b -n 2 | tr -d '\f'
   ```
   * *When playing games/FreeTube:* The table will show devices running at `48000`.
   * *When RaySession is open:* Every column—including the physical Yamaha P-Series driver—will flawlessly match at `44100`.

2. **Check Global Core Settings:**
   ```bash
   pw-metadata -n settings 0
   ```

