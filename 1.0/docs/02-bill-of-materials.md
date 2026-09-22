# Bill of materials — Phase 1

Prices are approximate and from the usual sources (Amazon, AliExpress, Adafruit).
Check before you buy; commodity clone prices move.

## Option A: starter kit (recommended)

One purchase, everything included, plus a pile of parts you'll want later.

| Item | ~Price |
|---|---|
| Elegoo (or equivalent) UNO R3 Starter Kit | $30 |

These kits ship an Uno R3 clone, breadboard, jumper wires, an SG90 servo, an
HC-SR04 ultrasonic module, resistors, LEDs, and a USB cable. That is the entire
Phase 1 build in one box, and you'll use the leftovers for the drone project too.

Verify the kit lists **both** "HC-SR04" and "SG90" before ordering. Some cheaper
kits drop one or the other.

**Total: ~$30.** Leaves $20 of headroom below your budget.

## Option B: à la carte

If you already have an Arduino or want the cheaper Nano.

| Item | ~Price | Notes |
|---|---|---|
| Arduino Nano clone (CH340) | $6 | Uno R3 clone is ~$14 if you prefer the bigger board |
| HC-SR04 ultrasonic module | $3 | 5-packs run ~$10; buy the pack, you will kill one |
| SG90 micro servo | $3 | MG90S at $6 has metal gears and less jitter — worth it |
| 400-pt breadboard | $4 | |
| Jumper wire set (M-M, M-F) | $6 | You need male-to-female for the sensor |
| USB cable (A → mini/micro-B for Nano) | $4 | Check which connector your board has |
| **Total** | **~$26** | |

## Worth the remaining budget

Optional, in order of how much they improve the build:

| Item | ~Price | Why |
|---|---|---|
| **VL53L0X ToF lidar module** | $7 | Infrared time-of-flight. ~2° beam vs the HC-SR04's 30°, 2 m range, I²C. This is the single biggest upgrade available: your angular resolution goes from "useless" to "actually resolves two people." Strongly recommended. |
| MG90S metal-gear servo | $6 | The SG90's plastic gears have ~2° of backlash, which shows up as smeared targets |
| Pan-tilt bracket kit | $8 | Saves you taping a servo to a sensor. Enables a second axis later. |
| Small breadboard PSU (5V/3.3V) | $5 | The Uno's 5 V rail browns out under servo stall current and resets the board mid-sweep. Very annoying to debug. |

## Do not buy yet

- **Cheap "24 GHz radar sensor" / RCWL-0516 modules ($2).** These are motion
  switches, not radar. One binary output pin, no range, no velocity. They cannot
  do anything this project needs.
- **HB100 Doppler module ($8).** Real radar, gives velocity — but *no range*, and
  the raw output needs ~60 dB of amplification before a microcontroller can see
  it. Good Phase 2 project, bad first project.
- **RTL-SDR ($30).** You'll want one, but it's a different project (Phase 2).
  Don't split your budget.

## What you already have that matters

You're running Windows. You'll need:

- **Arduino IDE 2.x** (free) — or the VS Code Arduino extension, since you're
  already in VS Code
- **CH340 USB driver** — required for Nano clones and most cheap Unos. Windows
  usually finds it; if the board doesn't show up as a COM port, this is why.
- **Python 3.11+** with `pyserial`, `numpy`, `matplotlib` — see
  `requirements.txt`
