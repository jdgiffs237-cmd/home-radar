# home-radar

A learn-by-building radar project. Phase 1 is a servo-scanned rangefinder on your
desk that behaves like a radar: it sweeps a beam, gates returns by range, plots a
PPI scope, decides what's a target and what's noise, and tracks targets frame to
frame. Phase 2 swaps the sensor for real RF hardware without rewriting the
software.

## Be clear-eyed about what this is

An ultrasonic rangefinder is **not** radar. It's sound, not RF; it's ~340 m/s,
not 3×10⁸; the beam is wide and sloppy; there's no phase, no coherent
integration, no Doppler.

What *does* transfer, and it's most of the hard part:

| Concept | Same in this build | Same in real radar |
|---|---|---|
| Pulse → echo → time-of-flight → range | ✅ | ✅ |
| Range resolution set by pulse width | ✅ | ✅ |
| Angular resolution set by beamwidth | ✅ | ✅ |
| Scan pattern, frame rate, revisit time | ✅ | ✅ |
| Clutter, multipath, ghost returns | ✅ | ✅ |
| Detection thresholding / CFAR | ✅ | ✅ |
| Plot-to-track association, filtering | ✅ | ✅ |
| Doppler / range-Doppler maps | ❌ | ✅ |
| Coherent integration, phase, MTI | ❌ | ✅ |

The included simulator (`radar/sim.py`) also has an FMCW mode that fakes Doppler,
so you can write range-Doppler code before you own a radar that produces it.

## You can start right now, with no hardware

```bash
pip install -r requirements.txt
python run_sim.py            # synthetic targets, live PPI scope
python run_web.py            # same thing, but the scope is a browser page
pytest -q                    # the exercises. they fail. that's the point.
```

`run_sim.py` generates a world of moving targets and feeds your code the same
data structures the Arduino will feed it later. Everything you write against the
sim works unchanged against hardware.

## Layout

```
docs/           read these in order
firmware/       Arduino sketch: sweep the servo, ping, print CSV
radar/
  config.py     one place for every tunable number
  scan.py       Sweep / Return / Detection / Track data structures  [done]
  sim.py        synthetic target world + sensor noise model          [done]
  serial_link.py  read CSV sweeps off the Arduino                    [done]
  display.py    PPI scope (the round green sweep display)            [done]
  webserver.py  streams sweeps to the browser scope                  [done]
  detect.py     thresholding, CFAR, clustering        >>> YOUR JOB <<<
  track.py      association + alpha-beta filter       >>> YOUR JOB <<<
tests/          pytest suite that grades detect.py and track.py
examples/       fmcw_range_doppler.py -- the two-FFT chain real radar runs
web/            the browser scope page run_web.py serves
run_sim.py      simulated radar, no hardware needed
run_live.py     same thing, real sensor
run_web.py      either source, displayed in your browser (also --replay)
```

Infrastructure is written for you. The signal processing is not — those are
exercises with docstrings that spell out the algorithm and tests that tell you
when you got it right. Solutions are in `docs/solutions/` if you want to unblock
yourself, but the tests are more useful.

## Order of operations

1. `docs/01-radar-fundamentals.md` — the five equations you actually need
2. `python run_sim.py` — watch the scope, get a feel for the data
3. `pytest -q` — see what's broken, fix `detect.py`
4. Order parts (`docs/02-bill-of-materials.md`, ~$35)
5. Build it (`docs/03-hardware-build.md`), run `run_live.py`
6. Fix `track.py` — real returns are messy enough to make tracking necessary
7. `docs/04-going-real-rf.md` — where to spend the next $50

## Legal note, since you'll ask eventually

Nothing in Phase 1 transmits RF. When you get to Phase 2: receive-only SDR work
(ADS-B, passive radar off FM broadcast towers) is unrestricted in the US.
Transmitting is not — but the hobby modules people use (HB100, TI IWR/AWR eval
boards, 24 GHz and 60 GHz sensors) ship FCC-certified for exactly this, and
operating one as intended is fine. Don't build your own transmitter and don't
point anything at aircraft.
