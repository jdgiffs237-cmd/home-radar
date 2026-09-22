# Radar fundamentals: the parts that matter for this build

Enough theory to write the code. No more.

## Cheat sheet: every symbol used below

| Symbol | Means | In plain words |
|---|---|---|
| `R` | range | distance to the object, in meters |
| `c` | wave speed | how fast the ping travels: 343 m/s for sound, 3×10⁸ m/s for radio |
| `t` | time | how long the echo took to come back |
| `τ` (tau) | pulse duration | how long one ping lasts |
| `ΔR` | range resolution | closest two objects can be (in depth) and still show as two |
| `ΔX` | cross-range resolution | closest two objects can be (side by side) and still show as two |
| `B` | bandwidth | how wide a band of frequencies the radar sweeps through |
| `T` | chirp time | how long one frequency sweep takes |
| `θ` (theta) | beamwidth | how wide the beam spreads, as an angle |
| `λ` (lambda) | wavelength | physical length of one wave |
| `D` | aperture | size of the antenna/dish |
| `α` (alpha) | CFAR threshold factor | "how many times the background noise" a return must be to count |
| `N` | training cells | how many neighboring cells you average to measure that background |
| `P_fa` | false-alarm probability | how often you accept being fooled by noise (1e-3 = once in 1000) |
| `f_beat` | beat frequency | the tone whose pitch tells you range in FMCW radar |
| `f0` | start frequency | where the chirp's sweep begins |
| `P_t`, `P_r` | transmit / received power | what you send out vs. the tiny bit that comes back |
| `G` | antenna gain | how well the antenna focuses energy in one direction |
| `σ` (sigma) | radar cross section | how strongly a target reflects (shape matters more than size) |

| Acronym | Stands for | In plain words |
|---|---|---|
| RF | radio frequency | radio waves — what real radar uses (yours uses sound) |
| ToF | time of flight | the echo's round-trip travel time |
| FMCW | frequency-modulated continuous wave | the trick that lets cheap radar measure range (§6) |
| CFAR | constant false alarm rate | a smart threshold that adapts to the surroundings (§5) |
| FFT | fast Fourier transform | math that splits a signal into its frequencies |
| TX / RX | transmit / receive | the outgoing signal / the returning echo |
| PPI | plan position indicator | the round green sweep display |
| HC-SR04 | (part number) | the $3 ultrasonic sensor this project uses |
| mmWave | millimeter wave | very high-frequency radar, like in cars |

More terms are in `glossary.md`.

---

## 1. Range is time

You emit a pulse, it hits something, it comes back. The round trip took `t`
seconds. The thing is at

```
R = c · t / 2
```

The `/2` is the round trip. For sound, `c ≈ 343 m/s` at 20 °C (68 °F) — and it
drifts ~0.6 m/s per °C (~0.3 m/s per °F), worth remembering when your ranges
seem 3 % off on a cold night. For RF, `c = 3×10⁸ m/s`.

**Consequence:** ultrasonic ToF at 1 m is ~5.8 ms. RF ToF at 1 m is ~6.7 ns.
This is the entire reason cheap radar is hard and cheap sonar is easy: sonar
needs a microcontroller, radar needs a GHz-rate clock or a clever trick (FMCW —
see §6).

## 2. Range resolution is pulse width

Two targets separated by less than half the pulse length merge into one blob:

```
ΔR = c · τ / 2          τ = pulse duration
```

HC-SR04 emits an 8-cycle burst at 40 kHz → τ = 200 µs → ΔR ≈ 3.4 cm. That's your
floor. Nothing in software beats it; a nearer and a farther target 2 cm apart are
one detection, forever.

Real radar plays the same game in bandwidth terms: `ΔR = c / (2B)`. A 4 GHz-wide
mmWave chirp gives 3.75 cm. Same number, wildly different hardware.

## 3. Angular resolution is beamwidth

Your "beam" is however wide the transducer radiates. HC-SR04 is roughly ±15°.
Two targets at the same range 10° apart are **one target**. This is why the PPI
plot smears objects into arcs, and it's the single biggest difference between
your scope and the clean radar displays in movies.

Cross-range resolution at range R:

```
ΔX ≈ R · θ_beamwidth(radians)
```

At 2 m with a 30° beam: 1.05 m. Your radar cannot tell two people standing
shoulder to shoulder at 2 m apart from one wide person.

**Beamwidth is aperture:** `θ ≈ λ / D`. Bigger aperture, tighter beam. This is
why real radars are large and why phased arrays exist — the same physics that
makes a big dish sharp makes an array of small elements sharp when you sum them
with the right phases.

## 4. Scan pattern and revisit time

You sweep 0→180° in steps. Two numbers fall out:

- **Frame time** = steps × time-per-step. With 1° steps and a 25 ms servo settle
  + 30 ms max ping wait, that's 180 × 55 ms ≈ **10 seconds per frame**. Way too
  slow to track a walking person.
- **Revisit time** = frame time. It's how long a target is invisible between
  looks, and it sets how far a target can move between frames — which is exactly
  the gate size your tracker needs.

The tradeoff you'll actually feel: coarse steps (5°) → 2 s frames, fast enough to
track, but you'll skip narrow targets. This tension is real radar's tension too;
it's why big radars run separate search and track modes.

## 5. Detection: threshold, false alarm, CFAR

A return is a number. Is it a target?

Fixed threshold ("anything closer than 2 m is a target") fails immediately,
because a wall at 1.8 m lights up every sweep. What you want is: **is this cell
unusual compared to its neighbors?**

That's CFAR — Constant False Alarm Rate. For the cell under test:

1. Skip a couple of **guard cells** either side (so the target doesn't inflate
   its own noise estimate).
2. Average N **training cells** beyond the guards → that's the local noise/clutter
   floor.
3. Declare a detection if `cell > α · noise_estimate`.

α is set from your acceptable false-alarm probability. In a cell-averaging CFAR
with N training cells:

```
α = N · (P_fa^(-1/N) − 1)
```

For N = 16 and P_fa = 1e-3: α ≈ 8.3, i.e. ~9.2 dB above the local floor.

The point of CFAR: the threshold *moves* with the environment. Drive through
rain, walk past a wall, the false alarm rate stays put. You'll implement this in
`radar/detect.py`.

## 6. FMCW — how real cheap radar actually works

You can't time 6.7 ns with an Arduino. So don't. Instead, transmit a tone that
sweeps linearly in frequency (a *chirp*) from `f0` to `f0 + B` over `T` seconds.
The echo arrives delayed by `t`, so at any instant the received frequency differs
from the transmitted one by a constant **beat frequency**:

```
f_beat = (B / T) · t = (B / T) · (2R / c)
      ⟹  R = c · T · f_beat / (2B)
```

Mix TX with RX, low-pass, and you get an audio-frequency tone whose *pitch is
range*. FFT it and each peak is a target. A soundcard can sample it. That's the
whole trick, and it's why a $30 module plus an FFT is a working radar.

Doppler comes free: run many chirps in a burst, FFT *across* chirps at each range
bin, and the second FFT axis is velocity. That's a **range-Doppler map**, the
thing every automotive radar produces.

`radar/sim.py --mode fmcw` generates synthetic beat signals so you can write the
two-FFT pipeline now.

## 7. The radar equation (know it exists, don't sweat it)

```
P_r = (P_t · G² · λ² · σ) / ((4π)³ · R⁴)
```

The only term you need to internalize: **R⁴**. Double the range, received power
drops 16×. This is why radar range specs are so hard-won, why targets vanish
abruptly rather than fading, and why σ (radar cross section — how much a target
reflects, not how big it is) dominates stealth design. A flat plate facing you
and the same plate at 30° differ by orders of magnitude.

Your ultrasonic sensor obeys the same R⁴ law. You'll see it: soft, angled, or
small objects drop out at a specific range and nothing you do in software brings
them back.

---

## Numbers for this build

| Quantity | Value |
|---|---|
| Speed of sound (20 °C / 68 °F) | 343 m/s |
| HC-SR04 pulse | 8 cycles @ 40 kHz = 200 µs |
| Range resolution | ~3.4 cm |
| Beamwidth | ~30° total |
| Usable range | 0.03 – 4 m |
| Min ping interval | 60 ms (else you hear your own last echo) |
| Frame time @ 5° steps | ~2 s |

## Where to go deeper

- Skolnik, *Introduction to Radar Systems* — the standard text
- MIT OpenCourseWare 22.S103 "Build a Small Radar" — coffee-can FMCW, free
- Richards, *Fundamentals of Radar Signal Processing* — for when CFAR and
  tracking stop feeling like magic and start feeling like statistics
