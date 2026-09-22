# Build Log

Newest entries on top.

---

## 2026-09-21 — First soldering attempt

Tried soldering today — it was a struggle! Going to try again tomorrow.

---

## 2026-09-20 — The amp-measuring day (2.0)

Big day. Measured the stepper's current draw with a multimeter: 0.24 A on
Arduino 5V (textbook), only 0.11 A through the power module on the worn 9V
battery — which explained the dim light and buzzing perfectly. Learned the
physics: internal resistance, voltage sag, why torque needs current.
Decision: scrapped the power module, whole 2.0 runs on Arduino/USB power
with a capacitor across the rails and coils released when idle. By evening:
full 2.0 radar firmware written (auto-sweep AND joystick-steered), sensor
wired on D10/D11, run_radar.py viewer with auto port detection. Planned
2.5: 12 V motor on its own supply.

---

## 2026-09-19 — Servo dies, stepper rises (2.0 begins)

Servo was acting broken; wrote debug sketches to prove it (it buzzed but
wouldn't move). Bought a replacement, then decided to upgrade the scan
axis to the kit's 28BYJ-48 stepper + ULN2003 instead — finer steps
(~0.18°/step). Restructured the repo into 1.0/ (servo era) and 2.0/
(stepper era). Got the stepper turning: 8 quarter-turns test, joystick
steering. First hit the weak-battery wall here.
