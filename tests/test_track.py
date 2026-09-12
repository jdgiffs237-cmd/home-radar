"""
Grades radar/track.py. Do test_detect.py first.

    pytest tests/test_track.py -q
"""

import math

import pytest

from radar.scan import Detection, Track
from radar.track import Tracker, alpha_beta_update, associate


def det(angle_deg, range_m, strength=1.0, frame=0):
    return Detection(angle_deg=angle_deg, range_m=range_m, strength=strength, frame=frame)


def xy_det(x, y):
    """Detection specified in Cartesian, for readability."""
    return Detection(angle_deg=math.degrees(math.atan2(y, x)), range_m=math.hypot(x, y))


# --- exercise 1: alpha_beta_update -------------------------------------


def test_alpha_beta_moves_position_toward_measurement():
    tr = Track(track_id=1, x=0.0, y=0.0, vx=0.0, vy=0.0)
    alpha_beta_update(tr, 1.0, 0.0, dt=1.0, alpha=0.5, beta=0.2)
    assert tr.x == pytest.approx(0.5)
    assert tr.y == pytest.approx(0.0)


def test_alpha_beta_updates_velocity():
    tr = Track(track_id=1, x=0.0, y=0.0, vx=0.0, vy=0.0)
    alpha_beta_update(tr, 1.0, 0.0, dt=1.0, alpha=0.5, beta=0.2)
    assert tr.vx == pytest.approx(0.2)
    assert tr.vy == pytest.approx(0.0)


def test_alpha_beta_uses_the_prediction_not_the_last_position():
    # track already knows it's moving; the measurement lands exactly where
    # it predicted, so nothing should change but time
    tr = Track(track_id=1, x=0.0, y=0.0, vx=1.0, vy=0.0)
    alpha_beta_update(tr, 1.0, 0.0, dt=1.0, alpha=0.5, beta=0.2)
    assert tr.x == pytest.approx(1.0)
    assert tr.vx == pytest.approx(1.0), "a perfect prediction shouldn't change v"


def test_alpha_beta_velocity_gain_scales_with_dt():
    a = Track(track_id=1, x=0.0, y=0.0)
    b = Track(track_id=2, x=0.0, y=0.0)
    alpha_beta_update(a, 1.0, 0.0, dt=1.0, alpha=0.5, beta=0.2)
    alpha_beta_update(b, 1.0, 0.0, dt=2.0, alpha=0.5, beta=0.2)
    # same residual over twice the time implies half the velocity correction
    assert b.vx == pytest.approx(a.vx / 2.0)


def test_alpha_beta_appends_history():
    tr = Track(track_id=1, x=0.0, y=0.0)
    alpha_beta_update(tr, 1.0, 0.0, dt=1.0)
    alpha_beta_update(tr, 2.0, 0.0, dt=1.0)
    assert len(tr.history) == 2
    assert tr.history[-1] == (pytest.approx(tr.x), pytest.approx(tr.y))


def test_alpha_beta_rejects_zero_dt():
    tr = Track(track_id=1, x=0.0, y=0.0)
    with pytest.raises(ValueError):
        alpha_beta_update(tr, 1.0, 0.0, dt=0.0)


def test_alpha_beta_converges_on_a_constant_velocity_target():
    tr = Track(track_id=1, x=0.0, y=0.0)
    truth_v = 0.25
    for k in range(1, 30):
        alpha_beta_update(tr, truth_v * k, 0.0, dt=1.0, alpha=0.5, beta=0.2)
    assert tr.vx == pytest.approx(truth_v, abs=0.03)
    assert tr.x == pytest.approx(truth_v * 29, abs=0.1)


# --- exercise 2: associate ---------------------------------------------


def test_associate_matches_a_nearby_detection():
    tr = Track(track_id=1, x=1.0, y=0.0)
    assign, unassigned = associate([tr], [xy_det(1.1, 0.0)], dt=1.0, gate_m=0.6)
    assert assign == {0: 0}
    assert unassigned == []


def test_associate_gates_out_a_distant_detection():
    tr = Track(track_id=1, x=1.0, y=0.0)
    assign, unassigned = associate([tr], [xy_det(3.0, 0.0)], dt=1.0, gate_m=0.6)
    assert assign == {}
    assert unassigned == [0]


def test_associate_uses_the_predicted_position():
    # track at (0,1) moving +y at 0.5 m/s. after 1 s it should be at (0,1.5).
    # the detection at 1.5 is the right one even though 1.0 is closer to
    # where the track currently *is*.
    tr = Track(track_id=1, x=0.0, y=1.0, vy=0.5)
    dets = [xy_det(0.0, 1.5), xy_det(0.0, 1.0)]
    assign, unassigned = associate([tr], dets, dt=1.0, gate_m=0.6)
    assert assign == {0: 0}, "association must gate around the prediction"
    assert unassigned == [1]


def test_associate_is_one_to_one():
    tracks = [Track(track_id=1, x=1.0, y=0.0), Track(track_id=2, x=1.05, y=0.0)]
    dets = [xy_det(1.02, 0.0)]
    assign, _ = associate(tracks, dets, dt=1.0, gate_m=0.6)
    assert len(assign) == 1
    assert list(assign.values()) == [0]


def test_associate_no_detection_used_twice():
    tracks = [Track(track_id=1, x=0.0, y=1.0), Track(track_id=2, x=0.0, y=2.0)]
    dets = [xy_det(0.0, 1.05), xy_det(0.0, 2.05)]
    assign, unassigned = associate(tracks, dets, dt=1.0, gate_m=0.6)
    assert assign == {0: 0, 1: 1}
    assert unassigned == []


def test_associate_greedy_takes_the_closest_pair_first():
    # track 0 is a near-perfect match for det 0; track 1 is also in gate for
    # det 0 but further. greedy must resolve in favour of track 0.
    tracks = [Track(track_id=1, x=0.0, y=1.00), Track(track_id=2, x=0.0, y=1.40)]
    dets = [xy_det(0.0, 1.01)]
    assign, _ = associate(tracks, dets, dt=1.0, gate_m=0.6)
    assert assign == {0: 0}


def test_associate_empty_inputs():
    assert associate([], [], dt=1.0) == ({}, [])
    assign, unassigned = associate([], [xy_det(1.0, 0.0)], dt=1.0)
    assert assign == {} and unassigned == [0]
    assign, unassigned = associate([Track(track_id=1, x=1.0, y=0.0)], [], dt=1.0)
    assert assign == {} and unassigned == []


def test_associate_unassigned_is_sorted():
    tr = Track(track_id=1, x=0.0, y=1.0)
    dets = [xy_det(0.0, 3.0), xy_det(0.0, 1.02), xy_det(2.5, 0.0)]
    _, unassigned = associate([tr], dets, dt=1.0, gate_m=0.6)
    assert unassigned == [0, 2]


# --- exercise 3: Tracker.update ----------------------------------------


def test_tracker_births_a_track():
    t = Tracker()
    tracks = t.update([xy_det(0.0, 1.5)], dt=1.0)
    assert len(tracks) == 1
    assert tracks[0].hits == 1
    assert tracks[0].track_id == 1


def test_tracker_tentative_before_confirmed():
    t = Tracker(init_hits=2)
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    assert t.confirmed == [], "one hit is not a target"
    t.update([xy_det(0.0, 1.52)], dt=1.0)
    assert len(t.confirmed) == 1


def test_tracker_assigns_increasing_ids():
    t = Tracker()
    t.update([xy_det(0.0, 1.0)], dt=1.0)
    t.update([xy_det(0.0, 1.0), xy_det(2.5, 0.0)], dt=1.0)
    assert sorted(tr.track_id for tr in t.tracks) == [1, 2]


def test_tracker_counts_misses_and_drops():
    t = Tracker(init_hits=1, drop_misses=3)
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    t.update([], dt=1.0)
    assert len(t.tracks) == 1 and t.tracks[0].misses == 1
    t.update([], dt=1.0)
    assert len(t.tracks) == 1
    t.update([], dt=1.0)
    assert t.tracks == [], "3 consecutive misses should delete the track"


def test_tracker_coasts_through_a_dropout():
    t = Tracker(init_hits=1, drop_misses=5)
    t.update([xy_det(0.0, 1.0)], dt=1.0)
    t.update([xy_det(0.0, 1.5)], dt=1.0)   # now has velocity
    v_before = t.tracks[0].vy
    y_before = t.tracks[0].y
    t.update([], dt=1.0)                   # dropout
    tr = t.tracks[0]
    assert tr.y == pytest.approx(y_before + v_before), "coast along velocity"
    assert tr.vy == pytest.approx(v_before), "a miss teaches you nothing about v"


def test_tracker_miss_counter_resets_on_a_hit():
    t = Tracker(init_hits=1, drop_misses=3)
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    t.update([], dt=1.0)
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    assert t.tracks[0].misses == 0


def test_tracker_follows_a_moving_target():
    """The whole point: a target walking across the FOV gets one stable ID."""
    t = Tracker(init_hits=2, drop_misses=3)
    x, y, v = -1.0, 1.6, 0.2
    for _ in range(14):
        t.update([xy_det(x, y)], dt=1.0)
        x += v

    conf = t.confirmed
    assert len(conf) == 1, f"one target should give one track, got {len(conf)}"
    tr = conf[0]
    assert tr.track_id == 1, "identity must survive the whole run"
    assert tr.vx == pytest.approx(v, abs=0.05)
    assert tr.speed_ms == pytest.approx(v, abs=0.05)
    assert tr.x == pytest.approx(x - v, abs=0.15)


def test_tracker_separates_two_targets():
    t = Tracker(init_hits=2, drop_misses=3)
    for k in range(8):
        t.update([xy_det(-1.0 + 0.15 * k, 1.2), xy_det(1.0, 2.5 - 0.1 * k)], dt=1.0)
    assert len(t.confirmed) == 2
    assert len({tr.track_id for tr in t.confirmed}) == 2


def test_tracker_handles_an_empty_first_frame():
    t = Tracker()
    assert t.update([], dt=1.0) == []


def test_tracker_births_after_deletion_not_before():
    """
    A detection near a track that is about to be deleted must not be adopted
    by it -- delete first, then birth.
    """
    t = Tracker(init_hits=1, drop_misses=1)
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    first_id = t.tracks[0].track_id
    t.update([], dt=1.0)                       # track dies here
    assert t.tracks == []
    t.update([xy_det(0.0, 1.5)], dt=1.0)
    assert t.tracks[0].track_id != first_id
