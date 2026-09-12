# Phase 2: actual RF

Read this after Phase 1 works. The point of Phase 1 was to write detection and
tracking code against a sensor you understand. All of it survives the swap —
`detect.py` and `track.py` don't know or care what produced the ranges.

Three directions, cheapest first.

---

## A. Receive-only: RTL-SDR (~$30)

A $30 USB dongle that hands you raw IQ samples from 24 MHz to 1.7 GHz. No
transmit, so no regulatory questions at all.

**ADS-B (1090 MHz).** Aircraft broadcast position, altitude, velocity, and ID in
the clear. Decode with `dump1090` and you have a live air picture over Atlanta
within an evening. Not radar — it's cooperative, the targets are telling you
where they are — but it's a superb source of real, messy, multi-target track data
to feed your tracker. Feed ADS-B plots into `track.py` and watch it handle
crossing targets, dropouts, and maneuvers.

**Passive radar.** This is the real prize. Use a broadcast FM station as your
illuminator: one dongle on the direct signal from the tower, one on a directional
antenna pointed away from it. Cross-correlate the two and you get range-Doppler
returns from aircraft that happen to reflect that station's signal. You transmit
nothing. Atlanta has strong FM transmitters and Hartsfield-Jackson overhead, so
you have both an illuminator and a steady supply of targets — genuinely good
geography for this.

It's hard: you need two coherent receivers (a dual-tuner "coherent" RTL-SDR is
~$50, or clock-mod two dongles), careful direct-signal cancellation, and a
cross-ambiguity function you'll write yourself. Look at the open-source
`PassiveRadar` and KrakenSDR projects. Budget a month of evenings, not a weekend.

## B. Short-range active: mmWave modules ($15–80)

FCC-certified sensors that do real FMCW and give you range *and* Doppler.

- **HLK-LD2410 / LD2450 (~$8–15).** 24 GHz presence sensors. Output processed
  target range/angle over UART. Easy, immediate, but they hide the signal
  processing from you — you get targets, not IQ.
- **AWR1642 / IWR6843 BoostXL eval boards (~$100–300).** TI's automotive radar
  chips. These give you raw ADC data, and you write the whole range-FFT →
  Doppler-FFT → CFAR → clustering → tracking chain — which is exactly the chain
  you'll have already written. Over your current budget, but this is the one that
  makes the project *real*.
- **HB100 (~$8).** 10.5 GHz CW Doppler. Velocity only, no range, and its output
  needs ~60 dB of gain before an ADC sees it. Cheap, instructive, limited.

## C. Build the chirp yourself: coffee-can radar (~$150 in parts)

MIT's 22.S103 course: two coffee cans as horn antennas, a Mini-Circuits VCO,
splitter and mixer, and a laptop soundcard for the ADC. Produces range plots,
Doppler plots, and — walking it down a road — real SAR imagery. Every schematic
and lab handout is free online. It is the single best "I built a radar" project
that exists at hobby scale.

---

## What to reuse from Phase 1

| Phase 1 file | Phase 2 fate |
|---|---|
| `scan.py` | unchanged — `Return`/`Detection`/`Track` are sensor-agnostic |
| `detect.py` | unchanged for 1-D CFAR; extend to 2-D for range-Doppler |
| `track.py` | unchanged, and it gets *easier* — Doppler makes association trivial |
| `display.py` | add a range-Doppler heatmap alongside the PPI |
| `sim.py` | already has an FMCW mode; use it to validate before hardware |
| firmware | dead. RF sensors talk USB/SPI, not a servo. |

## Given where you work

You coordinate production on hardware that does this for a living. Two things
worth being deliberate about:

- **Keep it clean.** Build this entirely from public sources — MIT OCW, TI app
  notes, open-source SDR projects. Never let anything you learned at work, or any
  Anduril document, drawing, or process, touch this repo. That boundary is worth
  more than any shortcut it could buy you, and "I built it from public sources"
  is the only version of this project you can actually talk about.
- **The intuition is the payoff.** Writing your own CFAR and then arguing about
  false-alarm rates, or fighting your own tracker through a crossing-target
  problem, changes how the specs you handle at work read. That's the real return
  on this, more than the hardware.
