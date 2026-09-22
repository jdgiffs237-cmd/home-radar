"""
Data structures shared by every stage of the chain.

    Return    one raw measurement at one angle
    Sweep     one full scan across the FOV
    Detection something detect.py decided was a target ("a plot")
    Track     something track.py has been following across frames

Nothing in here knows whether the data came from an ultrasonic sensor, an
FMCW module, or the simulator. That is the whole point -- when you swap the
hardware in Phase 2, these do not change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Return:
    """One measurement cell: 'at this bearing, something was at this range'."""

    index: int
    angle_deg: float
    range_m: float          # -1.0 means no echo came back
    amplitude: float = 1.0  # echo strength if the sensor reports it

    @property
    def is_miss(self) -> bool:
        return self.range_m < 0

    def to_xy(self) -> tuple[float, float]:
        """Cartesian, metres, radar at the origin, 90 deg = straight ahead."""
        r = math.radians(self.angle_deg)
        return self.range_m * math.cos(r), self.range_m * math.sin(r)


@dataclass
class Sweep:
    """One frame: all returns from one pass across the field of view."""

    frame: int
    returns: list[Return] = field(default_factory=list)
    timestamp: float = 0.0

    def sorted_by_angle(self) -> list[Return]:
        """
        Returns in ascending angle order.

        The firmware sweeps back and forth, so every other frame arrives
        with angles descending. CFAR cares about neighbours, so normalise
        before doing anything spatial.
        """
        return sorted(self.returns, key=lambda r: r.angle_deg)

    def ranges(self) -> list[float]:
        """Range per cell, angle-ordered. Misses stay as -1.0."""
        return [r.range_m for r in self.sorted_by_angle()]

    def __len__(self) -> int:
        return len(self.returns)


@dataclass
class Detection:
    """
    A plot: one target declared at one instant. No history, no identity.

    `strength` is however far above the local threshold the detection was --
    useful for ranking when two plots compete for the same track.
    """

    angle_deg: float
    range_m: float
    strength: float = 1.0
    frame: int = 0

    def to_xy(self) -> tuple[float, float]:
        r = math.radians(self.angle_deg)
        return self.range_m * math.cos(r), self.range_m * math.sin(r)

    def distance_to(self, x: float, y: float) -> float:
        dx, dy = self.to_xy()
        return math.hypot(dx - x, dy - y)


@dataclass
class Track:
    """
    A target followed across frames.

    State is Cartesian (x, y, vx, vy) rather than polar, because constant
    velocity is a straight line in Cartesian space and an ugly curve in
    polar space. Converting once at the input is much cheaper than fighting
    that geometry in the filter.
    """

    track_id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    hits: int = 1
    misses: int = 0
    confirmed: bool = False
    history: list[tuple[float, float]] = field(default_factory=list)

    @property
    def range_m(self) -> float:
        return math.hypot(self.x, self.y)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.y, self.x))

    @property
    def speed_ms(self) -> float:
        return math.hypot(self.vx, self.vy)

    def predict(self, dt: float) -> tuple[float, float]:
        """Where this track should be dt seconds from its last update."""
        return self.x + self.vx * dt, self.y + self.vy * dt
