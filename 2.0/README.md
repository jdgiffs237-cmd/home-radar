# Home Radar 2.0

The stepper era. Version 1.0 (in `../1.0/`) scanned with an SG90 servo;
2.0 swaps in the kit's 28BYJ-48 stepper motor + ULN2003 driver for finer,
repeatable steps (~0.18° per step vs the servo's whole-degree commands).
Everything runs from Arduino/USB 5V (~310 mA total, measured) with a
capacitor across the rails and coils released while idle.

## Run the radar

1. Wire it: `docs/stepper-wiring.html` (both diagrams — stepper AND sensor).
2. Upload `firmware/radar_stepper/radar_stepper.ino`.
3. When it prompts (Serial Monitor, 115200): point the sensor straight
   ahead by hand. You get 5 seconds. Then close the Serial Monitor!
4. From the `../1.0/` folder:

   ```
   python run_live.py --port COM3      # matplotlib scope
   python run_web.py  --port COM3      # browser scope
   ```

The firmware speaks the exact same serial protocol as 1.0, so all the
1.0 Python (display, detection, tracking, recording/replay) works
against the stepper unchanged.

## Layout

```
firmware/
  radar_stepper/          auto-sweeping radar: stepper + HC-SR04, 1.0 protocol
  radar_joystick_stepper/ hand-steered radar: YOU aim the beam with the stick
debug/
  stepper_joystick/   drive the stepper with the joystick — hardware test
  current_test/       multimeter diagrams from the amp measurements
docs/
  stepper-wiring.html wiring diagrams — double-click to open in browser
test individual components/
  stepper_90_test/    8 quarter-turns, back to start — wiring go/no-go
```

(The .html diagrams open in any browser; the claude.ai links in their
top-of-file comments are private working copies.)

## Wiring quick reference

| Arduino | Goes to |
|---|---|
| D2–D5 | ULN2003 IN1–IN4 |
| D10 / D11 | HC-SR04 TRIG / ECHO |
| 5V / GND rails | ULN2003 «+»/«−», HC-SR04 VCC/GND, joystick VCC/GND, capacitor (stripe to GND) |
| A0 | joystick VRx (debug sketches only) |

## The thing to remember about steppers

A stepper doesn't know where it's pointing — it only counts steps from
wherever it started. That's why the radar firmware starts with the
centering ritual: you point the sensor straight ahead by hand, the
firmware calls that 90° and keeps count from there. If the scope ever
looks rotated, the centering was off — press RESET and re-center.
