# Hardware build

Do this after the parts arrive. Until then, `run_sim.py` gives you everything.

## Wiring (Arduino Uno / Nano)

```
SG90 servo                      HC-SR04
  brown/black  → GND              GND  → GND
  red          → 5V               VCC  → 5V
  orange/yellow→ D9               TRIG → D10
                                  ECHO → D11
```

Two notes that will save you an hour:

1. **Power the servo from a separate 5 V supply if you can.** Under load it
   pulls 500 mA+ in spikes. The Uno's regulator sags, the board browns out, and
   you get random resets mid-sweep that look like software bugs. If you're
   running off USB anyway, add a 100–470 µF electrolytic across the servo's
   5V/GND to absorb the spikes. Common ground is mandatory either way.
2. **HC-SR04 is a 5 V part.** Fine on an Uno/Nano. If you ever move this to a Pi
   or an ESP32, the ECHO pin will damage a 3.3 V input — use a divider.

## Mechanical

Tape the ultrasonic module to the servo horn, sensor eyes facing outward, and
tape the servo to something heavy. Seriously — tape is fine for v1. Two things
that matter more than neatness:

- **The sensor's acoustic axis should pass over the servo's rotation axis.** If
  the sensor is offset 4 cm forward of the pivot, every measured range carries a
  4 cm angle-dependent error, and your PPI plot bows.
- **Nothing within 20 cm in front.** Your own desk, the servo body, a cable —
  all of it returns a huge echo that saturates the first range bins.

## Flash the firmware

1. Arduino IDE → open `firmware/radar_sweep/radar_sweep.ino`
2. Tools → Board → Arduino Uno (or Nano; for Nano clones also set
   Processor → "ATmega328P (Old Bootloader)" — most clones need this)
3. Tools → Port → whichever COM port appeared
4. Upload
5. Tools → Serial Monitor, 115200 baud. You should see lines like:

```
# radar_sweep v1 fov=180 step=5 c=343.0
S 0
R 0 5 1.834
R 1 10 1.821
R 2 15 0.412
...
E 0 37
```

`S <frame>` starts a sweep, `R <index> <angle_deg> <range_m>` is one return
(`-1.0` = no echo), `E <frame> <count>` ends it.

**Close the Serial Monitor before running Python.** Windows gives exclusive
access to a COM port; `run_live.py` will fail with "access denied" if the IDE
still has it open. This catches everyone once.

## Run it

```bash
python run_live.py --port COM3
```

Use `python -m serial.tools.list_ports` to find your port.

## Calibration, in the order that matters

1. **Temperature.** Set `SPEED_OF_SOUND` in `radar/config.py` (and the matching
   constant in the sketch). 343 m/s is 20 °C (68 °F); it's 331 at 0 °C (32 °F).
   A 3 % range error is almost always this.
2. **Angle zero.** Servos are not honest about where 0° is. Command 90°, measure
   where the sensor actually points, put the offset in `config.SERVO_ANGLE_OFFSET`.
3. **Settle time.** `SERVO_SETTLE_MS` too low = you ping while the head is still
   moving = returns smeared across angles. Start at 40 ms, walk it down until the
   plot degrades, back off.
4. **Ping interval.** Below ~60 ms you receive the *previous* ping's echo off a
   far wall and report a bogus near target. If you see ghosts at suspiciously
   consistent ranges, this is it.

## Failure modes you will hit

| Symptom | Cause |
|---|---|
| All ranges read 0 or max | TRIG/ECHO swapped |
| Board resets mid-sweep | Servo current — see power note above |
| Ranges 3–5 % off, consistently | Speed of sound / temperature |
| Targets smeared across 20° | Beamwidth (real), or servo settle too short |
| Ghost targets at fixed ranges | Ping interval too short, or multipath off a wall |
| Soft objects invisible | R⁴ and low acoustic reflectivity. Clothing eats ultrasound. Not a bug. |
| Nothing beyond 2 m | Also normal. Spec is 4 m for a flat perpendicular surface. |
