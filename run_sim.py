#!/usr/bin/env python3
"""
Simulated radar. No hardware required -- start here.

    python run_sim.py                 live PPI scope
    python run_sim.py --ascii         text scope, no matplotlib
    python run_sim.py --frames 20     run 20 frames and stop
    python run_sim.py --seed 7        reproducible world
    python run_sim.py --truth         print ground truth each frame

Runs the same chain run_live.py runs, against synthetic returns. Anything
that works here works against the Arduino unchanged.

Before you've done the exercises, detect.py and track.py raise
NotImplementedError -- that's expected. This script catches that and keeps
running with raw returns only, so you can still watch the scope.
"""

from __future__ import annotations

import argparse
import sys

from radar import config
from radar.detect import ClutterMap, find_targets
from radar.display import PPIScope, print_ascii
from radar.sim import SimRadar, default_world
from radar.track import Tracker


def main() -> int:
    p = argparse.ArgumentParser(description="Simulated scanning radar")
    p.add_argument("--frames", type=int, default=0, help="0 = run until closed")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--ascii", action="store_true", help="text scope")
    p.add_argument("--truth", action="store_true", help="print ground truth")
    p.add_argument("--no-clutter-map", action="store_true")
    p.add_argument("--delay", type=float, default=0.35, help="seconds between frames")
    args = p.parse_args()

    sim = SimRadar(default_world(), seed=args.seed)
    clutter = None if args.no_clutter_map else ClutterMap()
    tracker = Tracker()
    scope = None if args.ascii else PPIScope(title="home-radar (sim)")

    warned = False
    frame = 0

    print("simulated radar running.  ctrl-c to stop.")
    print(f"frame time {config.FRAME_TIME_S}s, {config.N_CELLS} cells, "
          f"{config.STEP_DEG} deg steps\n")

    try:
        while args.frames == 0 or frame < args.frames:
            sweep = sim.sweep()

            detections: list = []
            tracks: list = []
            try:
                if clutter is not None:
                    clutter.update(sweep)
                detections = find_targets(sweep, clutter)
                tracks = tracker.update(detections, config.FRAME_TIME_S)
            except NotImplementedError as exc:
                if not warned:
                    print(f"[!] {exc}")
                    print("[!] showing raw returns only. do the exercises in "
                          "radar/detect.py and radar/track.py, then rerun.\n")
                    warned = True

            if args.truth:
                truth = ", ".join(
                    f"{t.label}@{t.range_m:.2f}m/{t.angle_deg:.0f}deg"
                    for t in sim.truth()
                )
                print(f"truth: {truth}")

            if scope is not None:
                scope.update(sweep, detections, tracks)
                if scope.closed:
                    break
                import time
                time.sleep(args.delay)
            else:
                print_ascii(sweep, detections)
                for tr in tracks:
                    if tr.confirmed:
                        print(f"  T{tr.track_id}  r={tr.range_m:.2f}m  "
                              f"az={tr.angle_deg:.0f}deg  v={tr.speed_ms:.2f}m/s")
                print()

            frame += 1
    except KeyboardInterrupt:
        print("\nstopped.")

    if scope is not None and not scope.closed:
        print("done. close the window to exit.")
        scope.hold()
    return 0


if __name__ == "__main__":
    sys.exit(main())
