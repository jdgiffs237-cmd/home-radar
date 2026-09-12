"""
Reference solution for radar/track.py.

Same deal as detect_solution.py: copy the bodies in, don't replace the file.
"""

from __future__ import annotations

import math

from radar import config
from radar.scan import Detection, Track


def alpha_beta_update(
    track: Track,
    meas_x: float,
    meas_y: float,
    dt: float,
    alpha: float = config.TRACK_ALPHA,
    beta: float = config.TRACK_BETA,
) -> None:
    if dt <= 0:
        raise ValueError(f"dt must be > 0, got {dt}")

    # predict
    px = track.x + track.vx * dt
    py = track.y + track.vy * dt

    # innovation: how wrong the prediction was
    rx = meas_x - px
    ry = meas_y - py

    # correct (beta/dt, not beta: the residual is a distance, velocity is per-time)
    track.x = px + alpha * rx
    track.y = py + alpha * ry
    track.vx += (beta / dt) * rx
    track.vy += (beta / dt) * ry

    track.history.append((track.x, track.y))


def associate(
    tracks: list[Track],
    detections: list[Detection],
    dt: float,
    gate_m: float = config.TRACK_GATE_M,
):
    pairs = []
    for ti, tr in enumerate(tracks):
        px, py = tr.predict(dt)  # gate around the PREDICTION
        for di, d in enumerate(detections):
            dx, dy = d.to_xy()
            dist = math.hypot(dx - px, dy - py)
            if dist <= gate_m:
                pairs.append((dist, ti, di))

    pairs.sort()  # closest first; ties break deterministically on indices

    assignments: dict[int, int] = {}
    used_tracks: set[int] = set()
    used_dets: set[int] = set()
    for _dist, ti, di in pairs:
        if ti in used_tracks or di in used_dets:
            continue
        assignments[ti] = di
        used_tracks.add(ti)
        used_dets.add(di)

    unassigned = sorted(i for i in range(len(detections)) if i not in used_dets)
    return assignments, unassigned


class Tracker:
    def __init__(
        self,
        gate_m: float = config.TRACK_GATE_M,
        init_hits: int = config.TRACK_INIT_HITS,
        drop_misses: int = config.TRACK_DROP_MISSES,
    ):
        self.gate_m = gate_m
        self.init_hits = init_hits
        self.drop_misses = drop_misses
        self.tracks: list[Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection], dt: float) -> list[Track]:
        assignments, unassigned = associate(self.tracks, detections, dt, self.gate_m)

        for ti, tr in enumerate(self.tracks):
            if ti in assignments:
                dx, dy = detections[assignments[ti]].to_xy()
                alpha_beta_update(tr, dx, dy, dt)
                tr.hits += 1
                tr.misses = 0
                if tr.hits >= self.init_hits:
                    tr.confirmed = True
            else:
                tr.misses += 1
                # coast position through a dropout; don't touch velocity
                tr.x += tr.vx * dt
                tr.y += tr.vy * dt

        # delete before birth, or a dying track can adopt a fresh detection
        self.tracks = [t for t in self.tracks if t.misses < self.drop_misses]

        for di in unassigned:
            self.tracks.append(self._new_track(detections[di]))

        return self.tracks

    @property
    def confirmed(self) -> list[Track]:
        return [t for t in self.tracks if t.confirmed]

    def _new_track(self, det: Detection) -> Track:
        x, y = det.to_xy()
        tr = Track(
            track_id=self._next_id,
            x=x, y=y, vx=0.0, vy=0.0,
            hits=1, misses=0,
            confirmed=self.init_hits <= 1,
            history=[(x, y)],
        )
        self._next_id += 1
        return tr


def track_quality(track: Track) -> float:
    hit_score = min(track.hits / 10.0, 1.0)
    miss_penalty = 1.0 - min(track.misses / 3.0, 1.0)
    plausible = 1.0 if 0.0 <= track.speed_ms <= 3.0 else 0.3
    return hit_score * miss_penalty * plausible


# Gotchas, in one line each:
# 1. pairs.sort() breaks distance ties deterministically -- otherwise track IDs swap at random.
# 2. beta/dt, not beta, or the filter changes behaviour when the frame time changes.
# 3. On a miss, coast position but leave velocity alone -- a miss carries no velocity info.
# 4. Two crossing targets will swap IDs; greedy matching can't fix that (GNN/JPDA/MHT can).
