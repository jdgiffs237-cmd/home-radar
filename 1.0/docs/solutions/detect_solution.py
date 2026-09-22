"""
Reference solution for radar/detect.py.

To use: copy the five function/method bodies over the
`raise NotImplementedError` lines in radar/detect.py.
Don't replace the whole file.
"""

from __future__ import annotations

import numpy as np

from radar import config
from radar.scan import Detection, Sweep


def range_to_intensity(ranges, max_range=config.MAX_RANGE_M):
    r = np.asarray(ranges, dtype=np.float64)
    # misses (range < 0) must become 0 intensity, not max brightness
    intensity = np.where(r < 0, 0.0, max_range - r)
    return np.clip(intensity, 0.0, None)


def cfar_alpha(n_train: int, pfa: float = config.CFAR_PFA) -> float:
    if n_train < 1:
        raise ValueError(f"n_train must be >= 1, got {n_train}")
    if not (0.0 < pfa < 1.0):
        raise ValueError(f"pfa must be in (0, 1), got {pfa}")
    return n_train * (pfa ** (-1.0 / n_train) - 1.0)


def ca_cfar(
    intensity,
    n_guard: int = config.CFAR_GUARD_CELLS,
    n_train: int = config.CFAR_TRAIN_CELLS,
    pfa: float = config.CFAR_PFA,
):
    x = np.asarray(intensity, dtype=np.float64)
    n = len(x)
    detections = np.zeros(n, dtype=bool)
    thresholds = np.zeros(n, dtype=np.float64)

    for i in range(n):
        # training windows: skip the CUT and its guards, clip at the edges
        lo_hi = i - n_guard
        lo_lo = max(0, lo_hi - n_train)
        hi_lo = i + n_guard + 1
        hi_hi = min(n, hi_lo + n_train)

        left = x[lo_lo:max(lo_lo, lo_hi)]
        right = x[min(n, hi_lo):hi_hi]
        train = np.concatenate([left, right])

        if train.size == 0:
            continue

        noise = float(train.mean())
        # use the ACTUAL training count -- edge cells need a higher threshold
        alpha = cfar_alpha(train.size, pfa)

        if noise <= 0.0:
            thresholds[i] = 0.0
            detections[i] = x[i] > 0.0
            continue

        thr = alpha * noise
        thresholds[i] = thr
        detections[i] = x[i] > thr

    return detections, thresholds


def cluster_detections(dets: list[Detection]) -> list[Detection]:
    if not dets:
        return []

    ordered = sorted(dets, key=lambda d: d.angle_deg)

    clusters: list[list[Detection]] = [[ordered[0]]]
    for prev, cur in zip(ordered, ordered[1:]):
        same = (
            abs(cur.angle_deg - prev.angle_deg) <= config.CLUSTER_ANGLE_DEG
            and abs(cur.range_m - prev.range_m) <= config.CLUSTER_RANGE_M
        )
        if same:
            clusters[-1].append(cur)
        else:
            clusters.append([cur])

    out = []
    for group in clusters:
        # floor the weights so a zero-strength cluster can't divide by zero
        w = np.array([max(d.strength, 1e-9) for d in group])
        angles = np.array([d.angle_deg for d in group])
        ranges = np.array([d.range_m for d in group])
        out.append(
            Detection(
                angle_deg=float((angles * w).sum() / w.sum()),
                range_m=float((ranges * w).sum() / w.sum()),
                strength=float(max(d.strength for d in group)),
                frame=group[0].frame,
            )
        )
    return out


class ClutterMap:
    def __init__(self, learn_rate: float = 0.05, margin_m: float = 0.30):
        self.learn_rate = learn_rate
        self.margin_m = margin_m
        self._bg: dict[float, float] = {}

    def update(self, sweep: Sweep) -> None:
        for r in sweep.returns:
            if r.is_miss:
                continue  # a miss is not a range estimate
            prev = self._bg.get(r.angle_deg)
            if prev is None:
                self._bg[r.angle_deg] = r.range_m  # seed, don't blend
            else:
                a = self.learn_rate
                self._bg[r.angle_deg] = (1 - a) * prev + a * r.range_m

    def is_foreground(self, angle_deg: float, range_m: float) -> bool:
        if range_m < 0:
            return False
        bg = self._bg.get(angle_deg)
        if bg is None:
            return True  # unknown bearing: don't suppress
        return range_m < bg - self.margin_m

    @property
    def learned_bearings(self) -> int:
        return len(self._bg)

    def background(self, angle_deg: float):
        return self._bg.get(angle_deg)


# Gotchas, in one line each:
# 1. Misses must map to 0 intensity, or every dropout looks like a target.
# 2. cfar_alpha gets the actual training count, or the sweep edges spray false alarms.
# 3. CFAR misses a target sitting close in front of a wall; the clutter map catches it -- run both.
# 4. Clustering merges targets closer together than the beamwidth; only a narrower beam fixes that.
