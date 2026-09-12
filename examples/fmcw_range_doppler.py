#!/usr/bin/env python3
"""
The two-FFT pipeline every modern radar runs, on synthetic FMCW data.

    python examples/fmcw_range_doppler.py

This is Phase 2 in miniature. Nothing here needs hardware -- sim.py
generates the raw beat signal a real chirped radar would produce, and this
script does exactly what the DSP chain in an automotive radar does:

    range FFT (along fast time)  ->  Doppler FFT (along slow time)  ->  map

Run it, then go back to `ca_cfar` in radar/detect.py and convince yourself
that running it down each column of this map is how you get detections out
of a real radar. The 1-D CFAR you wrote is one axis of the 2-D CFAR that
ships in every one of these chips.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.sim import fmcw_beat_signal  # noqa: E402

C = 299_792_458.0
BANDWIDTH = 4e9
CHIRP_TIME = 40e-6
SAMPLE_RATE = 6.4e6
CARRIER = 77e9
N_SAMPLES = 256
N_CHIRPS = 128

# ground truth: (range_m, radial_velocity_ms)
TARGETS = [(3.0, 0.0), (7.5, 2.0), (5.2, -1.5)]


def main() -> None:
    lam = C / CARRIER
    range_res = C * CHIRP_TIME * SAMPLE_RATE / (2 * BANDWIDTH * N_SAMPLES)
    vel_res = lam / (2 * N_CHIRPS * CHIRP_TIME)

    cube = fmcw_beat_signal(
        TARGETS,
        n_chirps=N_CHIRPS,
        n_samples=N_SAMPLES,
        bandwidth_hz=BANDWIDTH,
        chirp_time_s=CHIRP_TIME,
        carrier_hz=CARRIER,
        sample_rate_hz=SAMPLE_RATE,
        seed=1,
    )

    # 1. range FFT: along fast time. each bin is a range.
    range_fft = np.fft.fft(cube, axis=1)
    # 2. Doppler FFT: along slow time, per range bin. each bin is a velocity.
    rd = np.fft.fftshift(np.fft.fft(range_fft, axis=0), axes=0)
    mag = np.abs(rd)

    print(f"range resolution   {range_res*100:5.2f} cm")
    print(f"velocity resolution {vel_res:5.2f} m/s")
    print(f"max range          {N_SAMPLES * range_res:5.2f} m")
    print(f"max |velocity|     {N_CHIRPS/2 * vel_res:5.2f} m/s\n")

    print("truth:")
    for r, v in TARGETS:
        print(f"  R={r:5.2f} m  v={v:+5.2f} m/s")

    print("\ndetected peaks:")
    order = np.argsort(mag.ravel())[::-1]
    found: list[tuple[float, float]] = []
    for flat in order:
        d, r = np.unravel_index(flat, mag.shape)
        rng = r * range_res
        vel = (d - N_CHIRPS // 2) * vel_res
        # sim.py produces a complex (IQ) beat signal, so all N_SAMPLES range
        # bins are unambiguous. A real receiver that samples the mixer output
        # with a single real ADC only gets the lower half -- the upper half is
        # its mirror image, and you'd discard it here.
        if any(abs(rng - a) < 0.4 and abs(vel - b) < 0.8 for a, b in found):
            continue    # same peak, adjacent bin
        found.append((rng, vel))
        print(f"  R={rng:5.2f} m  v={vel:+5.2f} m/s")
        if len(found) == len(TARGETS):
            break

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    db = 20 * np.log10(mag + 1e-12)
    im = ax.imshow(
        db,
        aspect="auto",
        origin="lower",
        cmap="magma",
        extent=[
            0,
            N_SAMPLES * range_res,
            -N_CHIRPS / 2 * vel_res,
            N_CHIRPS / 2 * vel_res,
        ],
    )
    ax.set_xlabel("range (m)")
    ax.set_ylabel("radial velocity (m/s)")
    ax.set_title("range-Doppler map (synthetic FMCW)")
    fig.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    out = "range_doppler.png"
    fig.savefig(out, dpi=120)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
