# home-radar

A working radar system built from a $50 Arduino kit — and the signal
processing to make sense of what it hears. A motorized ultrasonic sensor
sweeps the room; Python turns the echoes into a live radar scope with
CFAR detection, clustering, and multi-target tracking.

Built as a learn-by-doing project: every algorithm was written against a
physics-based simulator first, then run against real hardware, and every
hardware decision (motor choice, power budget) was made by measuring, not
guessing — multimeter readings and all. The build diary is in
[BUILDLOG.md](BUILDLOG.md).

## Two generations

```
1.0/   servo-scanned    SG90 servo + HC-SR04 ultrasonic, full software stack
2.0/   stepper-scanned  28BYJ-48 stepper (~0.18°/step), same protocol -- the
                        entire 1.0 software stack works against it unchanged
```

The 2.0 hardware swap required **zero Python changes** — the firmware was
designed to speak the same serial protocol, so the display, detection, and
tracking pipeline never knew the motor changed. That protocol stability
was a deliberate design goal.

## What's inside

- **Firmware (C++/Arduino)** — auto-sweeping and joystick-steered variants;
  median-of-N ping filtering; search/track ping modes borrowed from how
  real radars split the problem; stepper coil power management
- **Signal processing (Python/NumPy)** — CA-CFAR adaptive detection,
  detection clustering, temporal clutter mapping, alpha-beta tracking
  filter with gating and track lifecycle *(detection/tracking modules are
  structured as exercises — partially complete, by design: this is a
  learning project and the docs explain each algorithm before you write it)*
- **Physics simulator** — synthetic rooms with R⁴ falloff, beamwidth
  smearing, multipath ghosts, and dropouts, so the whole chain runs and
  is testable with no hardware attached
- **Two displays** — a matplotlib PPI scope, and a zero-dependency web
  scope (stdlib HTTP + Server-Sent Events + canvas)
- **Docs** — radar fundamentals written for beginners, glossary, hardware
  build guides, wiring diagrams, and a pytest suite that grades the
  exercises

## Quick start (no hardware needed)

```bash
cd 1.0
pip install -r requirements.txt
python run_sim.py        # simulated radar, matplotlib scope
python run_web.py        # same, in your browser
```

With the hardware built (see `1.0/docs/03-hardware-build.md` or
`2.0/docs/stepper-wiring.html`):

```bash
cd 2.0
python run_radar.py      # auto-detects the Arduino, opens the web scope
```

## Repo map

```
BUILDLOG.md      the build diary -- what happened, in order
1.0/
  radar/         the processing chain: scan -> detect -> track -> display
  firmware/      Arduino sketches (servo sweep, joystick-steered)
  docs/          fundamentals, glossary, build guides, visual explainers
  tests/         pytest suite for the detection/tracking exercises
  run_sim.py     simulator | run_live.py hardware | run_web.py browser
2.0/
  firmware/      stepper sweep + joystick-steered stepper
  debug/         hardware bring-up sketches and current-measurement notes
  run_radar.py   one-command radar: find the board, open the scope
```
