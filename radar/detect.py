"""
Detection: turning a sweep of ranges into a list of plots.

>>> THIS FILE IS THE EXERCISE. <<<

Five functions are stubbed out with `raise NotImplementedError`. Each
docstring tells you exactly what the function has to do and why. Run
`pytest tests/test_detect.py -q` to grade yourself. Reference solutions are
in docs/solutions/detect_solution.py if you want to unblock -- but read the
test failures first, they're more informative.

Do them in this order:
    1. range_to_intensity   (warm-up, 3 lines)
    2. cfar_alpha           (one formula)
    3. ca_cfar              (the real one)
    4. cluster_detections   (fiddly, not hard)
    5. ClutterMap.update / .is_foreground

Background
----------
A sweep gives you range vs angle. That's a 1-D signal across angle, and the
whole detection problem is "which cells in this signal are targets?"

Two independent attacks, and you want both:

  * CFAR (spatial): a target is a cell that stands out from its immediate
    angular neighbours *right now*. Catches anything with an edge. Blind to
    a wide target that fills the training window.

  * Clutter map (temporal): learn what each bearing normally reads over many
    frames -- the wall, the desk, the doorframe -- then flag anything that
    reads significantly closer than usual. Catches wide targets. Blind to
    anything that has been sitting still since you started.

Real radars run both. So will yours.
"""

from __future__ import annotations

import numpy as np

from . import config
from .scan import Detection, Sweep

# ---------------------------------------------------------------------------
# 1. Intensity
# ---------------------------------------------------------------------------


def range_to_intensity(ranges: np.ndarray, max_range: float = config.MAX_RANGE_M) -> np.ndarray:
    """
    Convert ranges into something CFAR can threshold.

    CFAR wants an intensity where *bigger means more target-like*. A cheap
    rangefinder gives you the opposite: a strong nearby target produces a
    *small* number. So flip it -- a target is a cell that's unusually close.

        intensity = max_range - range

    Rules:
      * A miss (range < 0) is not a weak target, it's an absence of anything.
        It must map to intensity 0.0, not to `max_range`.
      * Ranges beyond max_range clamp to intensity 0.0.
      * Result must be float64, same shape as the input.

    Args:
        ranges: 1-D array of ranges in metres. -1.0 marks a miss.
        max_range: sensor ceiling.

    Returns:
        1-D float array of non-negative intensities.

    Example:
        >>> range_to_intensity(np.array([-1.0, 0.5, 3.5]), max_range=4.0)
        array([0. , 3.5, 0.5])
    """
    ranges = np.asarray(ranges, dtype=np.float64)
    bad = (ranges < 0) | (ranges > max_range)
    return np.where(bad, 0.0, max_range - ranges)


# ---------------------------------------------------------------------------
# 2. The CFAR scale factor
# ---------------------------------------------------------------------------


def cfar_alpha(n_train: int, pfa: float = config.CFAR_PFA) -> float:
    """
    Scale factor for cell-averaging CFAR.

    The noise estimate is the mean of `n_train` training cells. Because that
    estimate is itself noisy, you can't just multiply by "a bit more than 1"
    -- the required factor depends on how many cells you averaged. For
    exponentially-distributed noise power, the exact result is

        alpha = n * (P_fa ** (-1/n) - 1)

    Sanity checks to convince yourself the formula is doing real work:
      * n=16, pfa=1e-3  ->  ~8.3   (about 9.2 dB above the local floor)
      * n=8,  pfa=1e-3  ->  ~12.6  (fewer training cells, noisier estimate,
                                    so you have to demand more headroom)
      * lower pfa always gives a larger alpha

    Args:
        n_train: total number of training cells actually used (both sides).
        pfa: desired probability of false alarm per cell.

    Returns:
        Multiplicative threshold factor. Must be > 0.

    Raises:
        ValueError: if n_train < 1, or pfa is not in (0, 1).
    """
    raise NotImplementedError("exercise 2: see docstring")


# ---------------------------------------------------------------------------
# 3. CA-CFAR
# ---------------------------------------------------------------------------


def ca_cfar(
    intensity: np.ndarray,
    n_guard: int = config.CFAR_GUARD_CELLS,
    n_train: int = config.CFAR_TRAIN_CELLS,
    pfa: float = config.CFAR_PFA,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cell-Averaging CFAR over a 1-D intensity array.

    For each cell i (the "cell under test", CUT):

      1. Skip `n_guard` cells either side. These may contain the target's own
         energy spilling over -- a target that inflates its own noise
         estimate hides from you.
      2. Take the next `n_train` cells either side. Average them. That's your
         local noise/clutter floor estimate.
      3. threshold[i] = cfar_alpha(n_used, pfa) * noise_estimate
      4. Detection if intensity[i] > threshold[i]  (strictly greater)

    Edges: near the array ends there aren't `n_train` cells on both sides.
    Use however many exist (clip to bounds) and compute alpha from that
    actual count -- this is why cfar_alpha takes n_train as an argument
    rather than reading it from config. If a cell has zero training cells
    available, it cannot be a detection.

    Degenerate case: if the noise estimate is 0.0 (every training cell was a
    miss), any positive intensity is a detection. Handle it without dividing
    by zero.

    Args:
        intensity: 1-D array, bigger = more target-like.
        n_guard: guard cells per side.
        n_train: training cells per side.
        pfa: probability of false alarm.

    Returns:
        (detections, thresholds)
          detections: bool array, same length as `intensity`
          thresholds: float array of the threshold used at each cell
                      (0.0 where no decision was possible)

    Hint: the obvious Python loop is completely fine here -- 37 cells. Get it
    correct first. If you want the vectorised version afterwards, look up
    np.cumsum for sliding-window sums.
    """
    raise NotImplementedError("exercise 3: see docstring")


# ---------------------------------------------------------------------------
# 4. Clustering
# ---------------------------------------------------------------------------


def cluster_detections(dets: list[Detection]) -> list[Detection]:
    """
    Merge detections that are really one target into one plot.

    Your beam is ~30 deg wide, so one person lights up 5-7 adjacent cells.
    Handing all of them to the tracker creates seven tracks for one person.

    Algorithm (simple single-link clustering, and that's genuinely enough
    here -- don't reach for sklearn):

      1. Sort detections by angle.
      2. Walk the list. Start a new cluster whenever the current detection is
         further than CLUSTER_ANGLE_DEG in bearing OR further than
         CLUSTER_RANGE_M in range from the *previous* detection.
      3. Each cluster collapses to one Detection whose angle and range are
         the strength-weighted means of its members, and whose strength is
         the max of its members'.
      4. `frame` comes from the first member.

    Both thresholds live in config.

    Args:
        dets: raw per-cell detections, any order.

    Returns:
        One Detection per cluster, in ascending angle order. Empty input
        gives empty output.

    Worth thinking about once it works: strength-weighted centroiding is why
    your angular accuracy can beat your 5 deg step size, even though your
    angular *resolution* can't beat the 30 deg beamwidth. Accuracy and
    resolution are different things, and radar people are precise about it.
    """
    raise NotImplementedError("exercise 4: see docstring")


# ---------------------------------------------------------------------------
# 5. Clutter map
# ---------------------------------------------------------------------------


class ClutterMap:
    """
    Learns the static background at each bearing so you can subtract it.

    The wall at 3.2 m returns every single frame. CFAR handles it only if it
    has an edge; a wall filling the whole FOV doesn't. So learn it.

    Keeps a running estimate of the "normal" range at each angle, updated
    with an exponential moving average:

        estimate = (1 - learn_rate) * estimate + learn_rate * observed

    An EMA rather than a plain mean because the background genuinely drifts
    -- temperature changes the speed of sound, someone moves a chair -- and a
    plain mean would take forever to forget.

    Attributes:
        learn_rate: EMA weight for new observations. 0.05 is a reasonable
            start: ~20 frames to adapt, slow enough that a person walking
            through doesn't get absorbed into the background.
        margin_m: how much closer than the learned background a return must
            be before it counts as foreground.
    """

    def __init__(self, learn_rate: float = 0.05, margin_m: float = 0.30):
        self.learn_rate = learn_rate
        self.margin_m = margin_m
        self._bg: dict[float, float] = {}   # angle_deg -> learned range

    def update(self, sweep: Sweep) -> None:
        """
        Fold one sweep into the background estimate.

        Rules:
          * Misses (range < 0) teach you nothing about the background range.
            Skip them entirely -- do not let a miss drag the estimate around.
          * A bearing seen for the first time takes the observed range
            directly as its initial estimate (no EMA to blend with yet).
          * Otherwise apply the EMA above.

        Exercise 5a.
        """
        raise NotImplementedError("exercise 5a: see docstring")

    def is_foreground(self, angle_deg: float, range_m: float) -> bool:
        """
        True if this return is closer than the learned background by more
        than `margin_m` -- i.e. something is standing in front of the wall.

        Rules:
          * A miss (range < 0) is never foreground.
          * An unlearned bearing -- nothing in the map yet -- is treated as
            foreground. You have no background to rule it out, and missing a
            real target is worse than one extra plot.

        Exercise 5b.
        """
        raise NotImplementedError("exercise 5b: see docstring")

    @property
    def learned_bearings(self) -> int:
        return len(self._bg)

    def background(self, angle_deg: float) -> float | None:
        return self._bg.get(angle_deg)


# ---------------------------------------------------------------------------
# Pipeline -- already written. It works as soon as the pieces above do.
# ---------------------------------------------------------------------------


def find_targets(
    sweep: Sweep,
    clutter_map: ClutterMap | None = None,
    *,
    use_cfar: bool = True,
) -> list[Detection]:
    """
    Full detection chain: sweep in, plots out.

    CFAR and the clutter map are ORed, not ANDed -- each is blind to
    something the other catches, so requiring both agree loses targets.
    """
    ordered = sweep.sorted_by_angle()
    if not ordered:
        return []

    angles = np.array([r.angle_deg for r in ordered])
    ranges = np.array([r.range_m for r in ordered])
    intensity = range_to_intensity(ranges)

    flags = np.zeros(len(ordered), dtype=bool)
    strength = np.zeros(len(ordered))

    if use_cfar:
        cfar_hits, thresholds = ca_cfar(intensity)
        flags |= cfar_hits
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(thresholds > 0, intensity / thresholds, 0.0)
        strength = np.maximum(strength, np.nan_to_num(ratio))

    if clutter_map is not None:
        cm_hits = np.array(
            [clutter_map.is_foreground(a, r) for a, r in zip(angles, ranges)]
        )
        flags |= cm_hits
        strength = np.maximum(strength, cm_hits.astype(float) * 1.5)

    flags &= ranges > 0     # a miss is never a target, whatever the logic said

    raw = [
        Detection(
            angle_deg=float(angles[i]),
            range_m=float(ranges[i]),
            strength=float(max(strength[i], 1e-6)),
            frame=sweep.frame,
        )
        for i in np.flatnonzero(flags)
    ]
    return cluster_detections(raw)
