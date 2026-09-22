"""
Synthetic radar. Lets you write and test the whole processing chain before
any hardware exists, and -- more usefully -- lets you test against a world
where you know the ground truth.

The sensor model deliberately reproduces the annoying parts of the real
thing: beamwidth smearing, an R^4 detection falloff, range-dependent noise,
dropouts on soft targets, multipath ghosts, and a wall that returns a strong
echo every single frame so a fixed threshold can't work.

    world = default_world()
    sim = SimRadar(world)
    sweep = sim.sweep()
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from . import config
from .scan import Return, Sweep


# ---------------------------------------------------------------- world ---

@dataclass
class Target:
    """A point scatterer that moves at constant velocity."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    reflectivity: float = 1.0   # 1.0 = hard flat surface, 0.3 = a person in a coat
    label: str = ""

    def advance(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def range_m(self) -> float:
        return math.hypot(self.x, self.y)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.y, self.x))


@dataclass
class Wall:
    """A line segment of clutter. Returns strongly and never moves."""

    x1: float
    y1: float
    x2: float
    y2: float
    reflectivity: float = 1.0

    def ray_intersection(self, angle_deg: float) -> float | None:
        """
        Range at which a ray from the origin at `angle_deg` crosses this
        segment, or None. Standard ray/segment solve:
            origin + t*d  ==  p1 + u*(p2 - p1),  t >= 0, 0 <= u <= 1
        """
        a = math.radians(angle_deg)
        dx, dy = math.cos(a), math.sin(a)
        sx, sy = self.x2 - self.x1, self.y2 - self.y1

        denom = dx * sy - dy * sx
        if abs(denom) < 1e-12:      # ray parallel to the wall
            return None

        t = (self.x1 * sy - self.y1 * sx) / denom
        u = (self.x1 * dy - self.y1 * dx) / denom
        if t < 0 or not (0.0 <= u <= 1.0):
            return None
        return t


@dataclass
class World:
    """
    Targets and clutter.

    `bounds` is a simulation convenience, not physics: targets that would
    leave the box reverse the offending velocity component instead, so a
    long run keeps something in view. It also gives you free tracking
    trouble -- a target that reverses violates the constant-velocity model
    your filter assumes, and you will watch it overshoot the turn. Set
    bounds=None to let targets leave and never come back.
    """

    targets: list[Target] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)
    bounds: tuple[float, float, float, float] | None = (-1.9, 1.9, 0.5, 2.3)

    def advance(self, dt: float) -> None:
        for t in self.targets:
            t.advance(dt)
            if self.bounds is None:
                continue
            xmin, xmax, ymin, ymax = self.bounds
            if t.x < xmin or t.x > xmax:
                t.vx = -t.vx
                t.x = min(max(t.x, xmin), xmax)
            if t.y < ymin or t.y > ymax:
                t.vy = -t.vy
                t.y = min(max(t.y, ymin), ymax)


def default_world() -> World:
    """
    A corner of a room -- back wall and two side walls, all inside sensor
    range so every bearing returns something. In front of them: one target
    crossing the field of view, one closing on the radar, and one static
    object that a naive detector will happily report as a target forever.

    Note the crosser only moves at 0.12 m/s. At a 2 s frame time, an actual
    walking person (~1.4 m/s) covers 2.8 m between looks -- further than the
    whole scene, and completely untrackable. That is a real constraint, not
    a simulation shortcut: if you want to track people, you need a coarser
    angular step and a faster frame. Try STEP_DEG = 15 in config.py and see.
    """
    return World(
        targets=[
            Target(x=-1.5, y=1.90, vx=0.120, vy=0.000, reflectivity=0.45, label="crosser"),
            Target(x=1.5, y=0.85, vx=-0.030, vy=-0.012, reflectivity=0.70, label="closer"),
            Target(x=-1.0, y=0.75, vx=0.0, vy=0.0, reflectivity=0.90, label="chair"),
        ],
        walls=[
            Wall(-2.2, 2.6, 2.2, 2.6, reflectivity=1.0),    # back wall
            Wall(2.2, 0.0, 2.2, 2.6, reflectivity=0.9),     # right wall
            Wall(-2.2, 0.0, -2.2, 2.6, reflectivity=0.9),   # left wall
        ],
    )


# --------------------------------------------------------------- sensor ---

class SimRadar:
    """
    Simulated scanning rangefinder.

    Each call to sweep() steps every target forward by one frame time and
    returns a Sweep built with the same sensor model quirks the real one has.
    """

    def __init__(
        self,
        world: World | None = None,
        *,
        seed: int | None = None,
        noise_sigma_m: float = 0.012,
        ghost_rate: float = 0.02,
        clutter_only: bool = False,
    ):
        self.world = world if world is not None else default_world()
        self.rng = random.Random(seed)
        self.noise_sigma_m = noise_sigma_m
        self.ghost_rate = ghost_rate
        self.clutter_only = clutter_only
        self.frame = 0
        self.t = 0.0

    # -- the sensor model ------------------------------------------------

    # Range at which a perfect (reflectivity 1.0) target is detected half the
    # time. Everything else follows from the R^4 law relative to this.
    R50_M = 5.5

    def _detection_probability(self, range_m: float, reflectivity: float) -> float:
        """
        R^4 falloff as a detection probability.

            p = 1 / (1 + (R/R50)^4 / reflectivity)

        A hard wall at 3.2 m comes back ~90% of frames; a person in a coat
        (reflectivity ~0.45) at 3 m comes back ~84%; the same person at 4 m
        starts blinking in and out. That abruptness is the R^4 law, and it's
        exactly what you'll see on the real sensor -- targets don't fade,
        they drop out.
        """
        if range_m <= 0 or reflectivity <= 0:
            return 0.0
        loss = (range_m / self.R50_M) ** 4 / reflectivity
        return max(0.0, min(0.995, 1.0 / (1.0 + loss)))

    def _echo_at(self, angle_deg: float) -> tuple[float, float] | None:
        """
        Strongest/nearest echo within the beam at this bearing.

        An amplitude-only sensor like the HC-SR04 reports the *first* echo it
        hears, not the strongest -- so a near soft target masks a far hard
        one. Modelled by taking the minimum range among everything that got
        detected inside the beam.
        """
        half_beam = config.BEAMWIDTH_DEG / 2.0
        candidates: list[tuple[float, float]] = []

        if not self.clutter_only:
            for tgt in self.world.targets:
                dtheta = abs(_wrap180(tgt.angle_deg - angle_deg))
                if dtheta > half_beam:
                    continue
                # off-boresight loss: cos^2 taper across the beam
                taper = math.cos(math.pi * dtheta / (2 * half_beam)) ** 2
                eff = tgt.reflectivity * taper
                if self.rng.random() < self._detection_probability(tgt.range_m, eff):
                    candidates.append((tgt.range_m, eff))

        for wall in self.world.walls:
            r = wall.ray_intersection(angle_deg)
            if r is None or r > config.MAX_RANGE_M:
                continue
            if self.rng.random() < self._detection_probability(r, wall.reflectivity):
                candidates.append((r, wall.reflectivity))

        if not candidates:
            return None
        return min(candidates, key=lambda c: c[0])

    def sweep(self) -> Sweep:
        angles = list(range(config.FOV_MIN_DEG, config.FOV_MAX_DEG + 1, config.STEP_DEG))
        if self.frame % 2 == 1:
            angles.reverse()        # firmware sweeps back and forth; so do we

        returns: list[Return] = []
        for i, ang in enumerate(angles):
            echo = self._echo_at(float(ang))

            if echo is None:
                returns.append(Return(index=i, angle_deg=float(ang), range_m=-1.0))
                continue

            rng_m, amp = echo
            rng_m += self.rng.gauss(0.0, self.noise_sigma_m * (1 + rng_m))
            # quantise to the sensor's actual range resolution
            rng_m = round(rng_m / config.RANGE_RESOLUTION_M) * config.RANGE_RESOLUTION_M

            # multipath ghost: an extra bounce shows up further out
            if self.rng.random() < self.ghost_rate:
                rng_m = min(rng_m * 2.0, config.MAX_RANGE_M)
                amp *= 0.3

            if not (config.MIN_RANGE_M <= rng_m <= config.MAX_RANGE_M):
                returns.append(Return(index=i, angle_deg=float(ang), range_m=-1.0))
                continue

            returns.append(
                Return(index=i, angle_deg=float(ang), range_m=rng_m, amplitude=amp)
            )

        sweep = Sweep(frame=self.frame, returns=returns, timestamp=self.t)
        self.world.advance(config.FRAME_TIME_S)
        self.frame += 1
        self.t += config.FRAME_TIME_S
        return sweep

    def truth(self) -> list[Target]:
        """Ground truth, for scoring your detector against reality."""
        return list(self.world.targets)


def _wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


# ----------------------------------------------------------------- FMCW ---

def fmcw_beat_signal(
    targets: list[tuple[float, float]],
    *,
    n_chirps: int = 128,
    n_samples: int = 256,
    bandwidth_hz: float = 4e9,
    chirp_time_s: float = 40e-6,
    carrier_hz: float = 77e9,
    sample_rate_hz: float = 6.4e6,
    noise_db: float = -25.0,
    seed: int | None = None,
) -> np.ndarray:
    """
    Synthesise the raw beat signal a real FMCW radar produces, so you can
    write the range-FFT -> Doppler-FFT -> CFAR chain before owning one.

    Args:
        targets: list of (range_m, radial_velocity_ms). Positive velocity
            means opening (moving away).

    Returns:
        Complex array, shape (n_chirps, n_samples). FFT along axis 1 for
        range; FFT the result along axis 0 for Doppler. Peaks land at

            range_bin  ~ R * (2 * B) / (c * T * f_s / n_samples)
            dopp_bin   ~ v * (2 * n_chirps * T) / lambda

    Defaults are roughly a TI AWR1642 in a short-range profile:
    ~3.75 cm range resolution, ~1.5 m unambiguous velocity.
    """
    c = 299_792_458.0
    rng = np.random.default_rng(seed)
    lam = c / carrier_hz
    slope = bandwidth_hz / chirp_time_s

    n = np.arange(n_samples)
    m = np.arange(n_chirps)
    t_fast = n / sample_rate_hz                     # within one chirp
    t_slow = m * chirp_time_s                       # chirp to chirp

    cube = np.zeros((n_chirps, n_samples), dtype=complex)
    for r0, v in targets:
        # range walks over the burst; delay -> beat frequency
        r = r0 + v * t_slow[:, None]
        tau = 2.0 * r / c
        phase = 2 * np.pi * (slope * tau * t_fast[None, :] + carrier_hz * tau)
        amp = 1.0 / max(r0, 0.1) ** 2               # R^4 in power, R^2 in amplitude
        cube += amp * np.exp(1j * phase)

    noise_amp = 10 ** (noise_db / 20.0)
    cube += noise_amp * (
        rng.standard_normal(cube.shape) + 1j * rng.standard_normal(cube.shape)
    ) / np.sqrt(2)
    return cube
