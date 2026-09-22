# Glossary

Terms in the order you'll trip over them.

**Azimuth** — Horizontal bearing angle. Your servo position. By convention 0° is
straight ahead or due north; pick one and stay consistent (this project uses 0°
= right, 90° = straight ahead, matching servo travel).

**Beamwidth** — Angular width of the transmitted energy, usually quoted where
power falls to half (−3 dB). Sets cross-range resolution. ~30° here, ~2° for a
VL53L0X, <1° for a real dish.

**Bin / cell** — One discrete sample slot. A *range bin* is one range step; a
*range-Doppler cell* is one (range, velocity) pair. "Cell under test" in CFAR
means the bin you're currently deciding about.

**CFAR (Constant False Alarm Rate)** — Adaptive detection: compare each cell to
an estimate of the noise floor built from nearby cells, so the false alarm rate
stays fixed as the environment changes. Cell-Averaging CFAR (CA-CFAR) is the
simple version; Ordered-Statistic (OS-CFAR) is more robust when targets sit close
together.

**Chirp** — A pulse whose frequency sweeps linearly. The basis of FMCW.

**Clutter** — Real returns from things you don't care about. Walls, ground,
furniture, rain, your own desk. Distinct from noise: clutter is a genuine echo,
it's just uninteresting, and it's often *stronger* than your target.

**Doppler shift** — Frequency shift from radial motion. Gives velocity directly.
Only radial motion shows up — a target crossing perpendicular to you has zero
Doppler and is invisible to a Doppler-only sensor.

**FMCW (Frequency-Modulated Continuous Wave)** — Transmit a chirp continuously,
mix the echo with what you're transmitting, and the beat frequency is
proportional to range. Lets you measure nanosecond delays with audio-rate
sampling. How nearly all cheap modern radar works.

**Gate** — A region you search for something. A *range gate* accepts returns in a
range window; a *track gate* is the region around a track's predicted position
where you'll accept a new detection as belonging to it. Too small: you lose the
track. Too large: you grab the wrong target.

**Ghost** — A false detection from multipath, an echo from a previous pulse, or a
processing artifact. Ghosts are stable and repeatable, which is what makes them
so convincing.

**Guard cells** — Bins immediately around the cell under test, excluded from the
CFAR noise estimate so that a target's own energy doesn't raise the threshold
against itself.

**MTI (Moving Target Indication)** — Suppress stationary clutter by subtracting
successive frames or high-pass filtering across them. Only what moves survives.
Cheap and effective; the poor man's version is `frame_n − frame_n-1`.

**Multipath** — Signal reaching the target (or you) by more than one route,
bouncing off floors and walls. Creates ghosts at longer ranges than the true
target and causes returns to fade in and out as paths add or cancel.

**Plot** — One detection, at one time, from one sensor. What comes out of
`detect.py`. Not yet associated with anything.

**PPI (Plan Position Indicator)** — The circular sweep display. Radar at the
center, range as radius, azimuth as angle. What `display.py` draws.

**PRF (Pulse Repetition Frequency)** — Pulses per second. Its inverse sets the
*maximum unambiguous range*: if an echo arrives after you've already sent the
next pulse, you can't tell which pulse it belongs to, and a far target masquerades
as a near one.

**Range resolution** — Minimum separation at which two targets stay distinct.
`c·τ/2` for a pulse, `c/2B` for FMCW.

**RCS (Radar Cross Section, σ)** — How much a target reflects back toward you,
in m². Not physical size — shape, material, and aspect angle dominate. A corner
reflector the size of your hand can outshine a car.

**Revisit time** — How long between successive looks at the same angle. Your
frame time. Sets the maximum target speed your tracker can follow.

**Track** — A target's estimated state (position, velocity) maintained across
frames, built by associating plots over time. The output of `track.py`.

**Track association** — Deciding which plot belongs to which existing track.
Nearest-neighbor is the simple approach; the real answers are Global Nearest
Neighbor, JPDA, and MHT, in increasing order of ambition.

**Time of flight (ToF)** — Round-trip travel time. Range = c·t/2.
