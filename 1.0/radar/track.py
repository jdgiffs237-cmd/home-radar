"""
Tracking: turning a pile of per-frame plots into targets with identity and
velocity.

>>> THIS FILE IS THE SECOND EXERCISE. <<<

Do detect.py first -- there is nothing to track until you have plots.
Grade with `pytest tests/test_track.py -q`.

Order:
    1. alpha_beta_update    (the filter, ~8 lines)
    2. associate            (the interesting one)
    3. Tracker.update       (the bookkeeping that makes it usable)

Why tracking is a separate problem from detection
-------------------------------------------------
Detection answers "is something there, right now". It has no memory, so it
cannot tell you a target's velocity, cannot tell you that the blob at 2.1 m
this frame is the same one that was at 2.4 m last frame, and cannot bridge a
frame where the target dropped out.

The whole job is three decisions per frame:

    predict    where should each existing track be now?
    associate  which plot belongs to which track?
    update     blend prediction with measurement; birth and death of tracks

Association is the hard one, and it's hard for a reason that never goes away
at any budget: two targets crossing produce two plots, and picking the wrong
pairing swaps their identities permanently. Nearest-neighbour (what you're
about to write) gets this wrong. Global Nearest Neighbour, JPDA and MHT are
the escalating answers. Write the naive one, then go make it fail on purpose
-- put two sim targets on crossing paths and watch the IDs swap.
"""

from __future__ import annotations

import math

from . import config
from .scan import Detection, Track

# ---------------------------------------------------------------------------
# 1. The filter
# ---------------------------------------------------------------------------


def alpha_beta_update(
    track: Track,
    meas_x: float,
    meas_y: float,
    dt: float,
    alpha: float = config.TRACK_ALPHA,
    beta: float = config.TRACK_BETA,
) -> None:
    """
    Alpha-beta filter: fold one measurement into a track's state, in place.

    This is a fixed-gain Kalman filter for a constant-velocity target. A real
    Kalman filter computes its gains each step from the covariance; here you
    just pick two constants. For this problem that is genuinely fine, and it
    is much easier to reason about when it misbehaves.

    Steps:
        1. Predict:   px = x + vx*dt        py = y + vy*dt
        2. Residual:  rx = meas_x - px      ry = meas_y - py
           (the "innovation" -- how wrong the prediction was)
        3. Correct position:  x = px + alpha*rx      y = py + alpha*ry
        4. Correct velocity:  vx += (beta/dt)*rx     vy += (beta/dt)*ry
        5. Append (x, y) to track.history

    alpha and beta are how much you trust the measurement over the model.
    alpha=1 means "the measurement is the truth, discard the prediction";
    alpha=0 means "ignore measurements entirely". beta does the same for
    velocity, and is smaller because velocity estimated from differences of
    noisy positions is *much* noisier than the positions themselves. Turn
    beta up to 0.8 in config and watch tracks vibrate -- that's worth seeing
    once.

    Args:
        track: modified in place.
        meas_x, meas_y: measured position, metres.
        dt: seconds since this track was last updated. Must be > 0.

    Raises:
        ValueError: if dt <= 0. (Dividing by dt in step 4 is why.)
    """
    raise NotImplementedError("exercise 1: see docstring")


# ---------------------------------------------------------------------------
# 2. Association
# ---------------------------------------------------------------------------


def associate(
    tracks: list[Track],
    detections: list[Detection],
    dt: float,
    gate_m: float = config.TRACK_GATE_M,
) -> tuple[dict[int, int], list[int]]:
    """
    Decide which detection belongs to which track. Greedy nearest neighbour.

    Algorithm:
        1. For every (track, detection) pair, compute the distance from the
           detection to the track's *predicted* position at dt
           (`track.predict(dt)`), not its last known position. Predicting
           first is the entire reason a tracker beats frame-by-frame
           matching on a moving target.
        2. Discard pairs further apart than `gate_m`. That's the gate: a
           detection outside it is assumed to be a different object, and no
           amount of being "closest" should change that.
        3. Sort surviving pairs by distance, ascending.
        4. Walk that list, accepting a pair only if neither its track nor its
           detection has already been claimed. One track gets at most one
           detection; one detection updates at most one track.

    Args:
        tracks: current tracks, in list order.
        detections: this frame's plots, in list order.
        dt: seconds since the last update.
        gate_m: association gate radius, metres.

    Returns:
        (assignments, unassigned_detection_indices)
          assignments: {track_index: detection_index}
          unassigned_detection_indices: indices into `detections` that were
              claimed by nobody, sorted ascending. These become new tracks.

    Tracks that got nothing simply don't appear as keys in `assignments`.

    Note on step 3: greedy-by-distance is *not* the same as minimising total
    assignment cost. The optimal answer is the Hungarian algorithm
    (scipy.optimize.linear_sum_assignment). Greedy is a good first
    implementation and a useful thing to have seen fail.
    """
    raise NotImplementedError("exercise 2: see docstring")


# ---------------------------------------------------------------------------
# 3. The tracker
# ---------------------------------------------------------------------------


class Tracker:
    """
    Maintains the track list across frames: birth, update, coast, death.

    Track lifecycle, and why it exists: a single detection is not a target,
    it's usually a false alarm. A single miss is not a target leaving, it's
    usually a dropout. So tracks are born *tentative*, get promoted after
    TRACK_INIT_HITS updates, and survive TRACK_DROP_MISSES consecutive misses
    before deletion. This is called M-of-N logic and every real radar does
    some version of it.

    Attributes:
        tracks: all tracks, tentative and confirmed.
    """

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
        """
        Advance the tracker one frame.

        Steps:
            1. `associate(self.tracks, detections, dt, self.gate_m)`
            2. For each assigned track:
                 - alpha_beta_update() with the detection's x, y
                 - hits += 1, misses = 0
                 - confirm it (confirmed = True) once hits >= init_hits
            3. For each unassigned track:
                 - misses += 1
                 - *coast* it: move it along its own velocity
                   (x += vx*dt, y += vy*dt) so the prediction stays valid
                   through a dropout. Don't touch its velocity.
            4. Delete tracks whose misses >= drop_misses.
            5. Birth a new Track for every unassigned detection: position
               from the detection, zero velocity, hits=1, misses=0,
               confirmed = (init_hits <= 1), history seeded with its position.
               IDs come from self._next_id and increment.
            6. Return self.tracks.

        Order matters: birth new tracks *after* deleting dead ones, or a
        detection can be adopted by a track that's about to be removed.

        Args:
            detections: this frame's plots.
            dt: seconds since the last call.

        Returns:
            The current track list (same object as self.tracks).
        """
        raise NotImplementedError("exercise 3: see docstring")

    @property
    def confirmed(self) -> list[Track]:
        return [t for t in self.tracks if t.confirmed]

    def _new_track(self, det: Detection) -> Track:
        """Helper: build a fresh track from a detection. Already written."""
        x, y = det.to_xy()
        tr = Track(
            track_id=self._next_id,
            x=x,
            y=y,
            vx=0.0,
            vy=0.0,
            hits=1,
            misses=0,
            confirmed=self.init_hits <= 1,
            history=[(x, y)],
        )
        self._next_id += 1
        return tr


# ---------------------------------------------------------------------------
# Bonus, once the above works
# ---------------------------------------------------------------------------


def track_quality(track: Track) -> float:
    """
    Optional: a 0-1 confidence score for a track.

    No test grades this one -- it's here because once you have tracks you
    will immediately want to rank them, and deciding what makes a track
    trustworthy is a genuinely interesting design question. Reasonable
    ingredients: hit count, recent miss count, how consistent the velocity
    has been across history, whether the speed is physically plausible for
    whatever you're trying to detect.
    """
    hit_score = min(track.hits / 10.0, 1.0)
    miss_penalty = 1.0 - min(track.misses / 3.0, 1.0)
    plausible = 1.0 if 0.0 <= track.speed_ms <= 3.0 else 0.3
    return hit_score * miss_penalty * plausible


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)
