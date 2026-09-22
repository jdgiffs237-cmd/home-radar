"""
Grades radar/detect.py.

    pytest tests/test_detect.py -q          all of it
    pytest tests/test_detect.py -q -k cfar  just the CFAR exercise

Every test names the exercise it grades. Read the failure message before
reading the solution.
"""

import math

import numpy as np
import pytest

from radar import config
from radar.detect import (
    ClutterMap,
    ca_cfar,
    cfar_alpha,
    cluster_detections,
    find_targets,
    range_to_intensity,
)
from radar.scan import Detection, Return, Sweep


# --- exercise 1: range_to_intensity ------------------------------------


def test_intensity_inverts_range():
    out = range_to_intensity(np.array([0.5, 2.0, 3.5]), max_range=4.0)
    assert np.allclose(out, [3.5, 2.0, 0.5])


def test_intensity_misses_are_zero_not_max():
    # the trap: -1.0 naively gives 4 - (-1) = 5.0, making a miss the
    # strongest return in the sweep
    out = range_to_intensity(np.array([-1.0, 1.0]), max_range=4.0)
    assert out[0] == 0.0
    assert out[1] == 3.0


def test_intensity_never_negative():
    out = range_to_intensity(np.array([0.1, 4.0, 9.0]), max_range=4.0)
    assert (out >= 0).all()


def test_intensity_shape_and_dtype():
    src = np.array([1.0, 2.0, 3.0])
    out = range_to_intensity(src)
    assert out.shape == src.shape
    assert out.dtype == np.float64


# --- exercise 2: cfar_alpha --------------------------------------------


@pytest.mark.parametrize(
    "n,pfa,expected",
    [
        (16, 1e-3, 16 * (1e-3 ** (-1 / 16) - 1)),
        (8, 1e-3, 8 * (1e-3 ** (-1 / 8) - 1)),
        (32, 1e-6, 32 * (1e-6 ** (-1 / 32) - 1)),
    ],
)
def test_alpha_matches_formula(n, pfa, expected):
    assert cfar_alpha(n, pfa) == pytest.approx(expected, rel=1e-9)


def test_alpha_ballpark():
    # sanity: 16 training cells at pfa 1e-3 wants roughly 9 dB of headroom
    a = cfar_alpha(16, 1e-3)
    assert 7.5 < a < 9.5


def test_alpha_fewer_training_cells_demands_more_headroom():
    assert cfar_alpha(4, 1e-3) > cfar_alpha(16, 1e-3)


def test_alpha_lower_pfa_raises_threshold():
    assert cfar_alpha(16, 1e-6) > cfar_alpha(16, 1e-3)


def test_alpha_rejects_bad_input():
    with pytest.raises(ValueError):
        cfar_alpha(0, 1e-3)
    with pytest.raises(ValueError):
        cfar_alpha(16, 0.0)
    with pytest.raises(ValueError):
        cfar_alpha(16, 1.0)


# --- exercise 3: ca_cfar -----------------------------------------------


def test_cfar_finds_isolated_spike():
    x = np.ones(40) * 1.0
    x[20] = 50.0
    hits, thr = ca_cfar(x, n_guard=2, n_train=8, pfa=1e-3)
    assert hits[20], "the spike should be detected"
    assert hits.sum() == 1, f"only the spike, got {hits.sum()} detections"
    assert thr.shape == x.shape


def test_cfar_ignores_uniform_field():
    x = np.ones(40) * 7.0
    hits, _ = ca_cfar(x, n_guard=2, n_train=8, pfa=1e-3)
    assert hits.sum() == 0, "a flat field has no targets, however bright"


def test_cfar_adapts_to_a_step_in_the_floor():
    # left half quiet, right half loud. a fixed threshold flags the whole
    # right half; CFAR should flag at most the edge cells.
    x = np.concatenate([np.ones(20) * 1.0, np.ones(20) * 20.0])
    hits, _ = ca_cfar(x, n_guard=1, n_train=6, pfa=1e-3)
    assert hits.sum() <= 3, f"CFAR should ride the step, got {hits.sum()} hits"


def test_cfar_guard_cells_protect_a_wide_target():
    # a 3-cell-wide target: without guard cells the target's own shoulders
    # inflate the noise estimate and it hides from itself
    x = np.ones(40)
    x[19:22] = 40.0
    hits_guarded, _ = ca_cfar(x, n_guard=3, n_train=8, pfa=1e-3)
    hits_unguarded, _ = ca_cfar(x, n_guard=0, n_train=8, pfa=1e-3)
    assert hits_guarded[20]
    assert hits_guarded.sum() >= hits_unguarded.sum()


def test_cfar_handles_array_edges():
    x = np.ones(20)
    x[0] = 50.0
    x[-1] = 50.0
    hits, _ = ca_cfar(x, n_guard=1, n_train=6, pfa=1e-3)
    assert hits[0] and hits[-1], "edge cells must still get a decision"


def test_cfar_zero_noise_does_not_divide_by_zero():
    x = np.zeros(20)
    x[10] = 5.0
    hits, _ = ca_cfar(x, n_guard=1, n_train=4, pfa=1e-3)
    assert hits[10]


def test_cfar_returns_thresholds():
    x = np.random.default_rng(0).exponential(1.0, 60)
    hits, thr = ca_cfar(x)
    assert thr.shape == x.shape
    assert (thr >= 0).all()
    assert hits.dtype == bool


def test_cfar_false_alarm_rate_is_roughly_controlled():
    # the whole promise of CFAR: on pure noise, the hit rate tracks pfa.
    # loose bound -- CA-CFAR with few training cells overshoots, and that's
    # expected, but it should not be off by orders of magnitude.
    rng = np.random.default_rng(42)
    noise = rng.exponential(1.0, 20000)
    hits, _ = ca_cfar(noise, n_guard=2, n_train=16, pfa=1e-2)
    rate = hits.mean()
    assert rate < 0.06, f"false alarm rate {rate:.4f} far above pfa=1e-2"


# --- exercise 4: cluster_detections ------------------------------------


def _d(angle, rng, strength=1.0):
    return Detection(angle_deg=angle, range_m=rng, strength=strength, frame=3)


def test_cluster_merges_adjacent_cells():
    dets = [_d(40, 2.00), _d(45, 2.02), _d(50, 1.98)]
    out = cluster_detections(dets)
    assert len(out) == 1
    assert 40 <= out[0].angle_deg <= 50


def test_cluster_keeps_separated_targets_apart():
    dets = [_d(20, 1.0), _d(140, 1.0)]
    assert len(cluster_detections(dets)) == 2


def test_cluster_splits_on_range_even_at_the_same_bearing():
    # same angle, very different range -- two targets, not one
    dets = [_d(90, 1.0), _d(90, 3.0)]
    assert len(cluster_detections(dets)) == 2


def test_cluster_is_strength_weighted():
    dets = [_d(40, 2.0, strength=1.0), _d(45, 2.0, strength=9.0)]
    out = cluster_detections(dets)
    assert len(out) == 1
    # the strong detection should pull the centroid toward 45
    assert out[0].angle_deg > 43.0


def test_cluster_takes_max_strength():
    out = cluster_detections([_d(40, 2.0, 1.0), _d(45, 2.0, 6.0)])
    assert out[0].strength == pytest.approx(6.0)


def test_cluster_output_is_angle_sorted():
    out = cluster_detections([_d(150, 1.0), _d(20, 1.0), _d(90, 1.0)])
    assert [round(d.angle_deg) for d in out] == [20, 90, 150]


def test_cluster_preserves_frame():
    out = cluster_detections([_d(40, 2.0), _d(45, 2.0)])
    assert out[0].frame == 3


def test_cluster_empty_input():
    assert cluster_detections([]) == []


# --- exercise 5: ClutterMap --------------------------------------------


def _sweep(pairs, frame=0):
    return Sweep(
        frame=frame,
        returns=[Return(index=i, angle_deg=a, range_m=r) for i, (a, r) in enumerate(pairs)],
    )


def test_clutter_map_learns_a_static_background():
    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    for f in range(10):
        cm.update(_sweep([(90.0, 3.2)], frame=f))
    assert cm.background(90.0) == pytest.approx(3.2, abs=0.05)


def test_clutter_map_first_observation_seeds_directly():
    cm = ClutterMap(learn_rate=0.05)
    cm.update(_sweep([(90.0, 3.2)]))
    # with a 0.05 EMA against an implicit zero start you'd get 0.16 --
    # the first sample has to be taken as-is
    assert cm.background(90.0) == pytest.approx(3.2)


def test_clutter_map_ignores_misses():
    cm = ClutterMap(learn_rate=0.5)
    cm.update(_sweep([(90.0, 3.2)]))
    for _ in range(5):
        cm.update(_sweep([(90.0, -1.0)]))
    assert cm.background(90.0) == pytest.approx(3.2)


def test_clutter_map_flags_something_in_front_of_the_wall():
    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    for f in range(10):
        cm.update(_sweep([(90.0, 3.2)], frame=f))
    assert cm.is_foreground(90.0, 1.5)


def test_clutter_map_does_not_flag_the_wall_itself():
    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    for f in range(10):
        cm.update(_sweep([(90.0, 3.2)], frame=f))
    assert not cm.is_foreground(90.0, 3.19)
    assert not cm.is_foreground(90.0, 3.25)


def test_clutter_map_respects_the_margin():
    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    for f in range(10):
        cm.update(_sweep([(90.0, 3.2)], frame=f))
    assert not cm.is_foreground(90.0, 3.0)   # only 0.2 closer, inside margin
    assert cm.is_foreground(90.0, 2.8)       # 0.4 closer, outside margin


def test_clutter_map_miss_is_never_foreground():
    cm = ClutterMap()
    cm.update(_sweep([(90.0, 3.2)]))
    assert not cm.is_foreground(90.0, -1.0)


def test_clutter_map_unlearned_bearing_is_foreground():
    cm = ClutterMap()
    assert cm.is_foreground(45.0, 1.0)


def test_clutter_map_adapts_when_the_background_moves():
    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    for f in range(10):
        cm.update(_sweep([(90.0, 3.2)], frame=f))
    for f in range(20):
        cm.update(_sweep([(90.0, 2.0)], frame=f))
    assert cm.background(90.0) == pytest.approx(2.0, abs=0.05)
    assert not cm.is_foreground(90.0, 2.0)


# --- integration: the whole chain --------------------------------------


def test_find_targets_on_a_synthetic_sweep():
    """A wall across the whole FOV with one object standing in front of it."""
    pairs = [(float(a), 3.2) for a in range(0, 181, 5)]
    for i, (a, _) in enumerate(pairs):
        if 85 <= a <= 95:
            pairs[i] = (a, 1.4)
    sweep = _sweep(pairs)

    cm = ClutterMap(learn_rate=0.5, margin_m=0.3)
    wall_only = _sweep([(float(a), 3.2) for a in range(0, 181, 5)])
    for _ in range(10):
        cm.update(wall_only)

    dets = find_targets(sweep, cm)
    assert len(dets) >= 1
    near = min(dets, key=lambda d: abs(d.angle_deg - 90))
    assert abs(near.angle_deg - 90) <= 10
    assert near.range_m == pytest.approx(1.4, abs=0.1)


def test_find_targets_empty_sweep():
    assert find_targets(Sweep(frame=0, returns=[])) == []


def test_find_targets_all_misses_yields_nothing():
    sweep = _sweep([(float(a), -1.0) for a in range(0, 181, 5)])
    assert find_targets(sweep) == []
