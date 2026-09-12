#!/usr/bin/env python3
"""
Live radar, against the Arduino.

    python run_live.py --port COM3
    python run_live.py --port COM3 --record data/kitchen.log
    python run_live.py --replay data/kitchen.log
    python -m serial.tools.list_ports            (find your port)

Close the Arduino IDE's Serial Monitor first -- Windows gives one process
exclusive access to a COM port, and you'll get "access is denied" otherwise.
"""

from __future__ import annotations

import argparse
import sys
import time

from radar import config
from radar.detect import ClutterMap, find_targets
from radar.display import PPIScope, print_ascii
from radar.serial_link import SerialRadar, replay
from radar.track import Tracker


def main() -> int:
    p = argparse.ArgumentParser(description="Live scanning radar")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="serial port, e.g. COM3 or /dev/ttyUSB0")
    src.add_argument("--replay", help="replay a recorded .log instead")
    p.add_argument("--record", help="write raw serial to this file while running")
    p.add_argument("--ascii", action="store_true")
    p.add_argument("--no-clutter-map", action="store_true")
    p.add_argument("--frames", type=int, default=0)
    args = p.parse_args()

    clutter = None if args.no_clutter_map else ClutterMap()
    tracker = Tracker()
    scope = None if args.ascii else PPIScope(title=f"home-radar ({args.port or 'replay'})")

    radar = None
    log = open(args.record, "w", encoding="ascii") if args.record else None

    try:
        if args.replay:
            source = replay(args.replay)
        else:
            radar = SerialRadar(args.port, verbose=True)
            source = radar.sweeps()

        warned = False
        frame = 0
        last_t = time.time()

        for sweep in source:
            now = time.time()
            dt = max(now - last_t, 1e-3)
            last_t = now

            if log is not None:
                log.write(f"S {sweep.frame}\n")
                for r in sweep.returns:
                    log.write(f"R {r.index} {r.angle_deg:.0f} {r.range_m:.3f}\n")
                log.write(f"E {sweep.frame} {len(sweep.returns)}\n")
                log.flush()

            detections: list = []
            tracks: list = []
            try:
                if clutter is not None:
                    clutter.update(sweep)
                detections = find_targets(sweep, clutter)
                tracks = tracker.update(detections, dt)
            except NotImplementedError as exc:
                if not warned:
                    print(f"[!] {exc}  -- raw returns only")
                    warned = True

            if scope is not None:
                scope.update(sweep, detections, tracks)
                if scope.closed:
                    break
            else:
                print_ascii(sweep, detections)

            frame += 1
            if args.frames and frame >= args.frames:
                break

    except KeyboardInterrupt:
        print("\nstopped.")
    except FileNotFoundError:
        print(f"no such replay file: {args.replay}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 -- serial throws a lot of things
        print(f"error: {exc}", file=sys.stderr)
        print("if this is 'access denied', close the Arduino Serial Monitor.",
              file=sys.stderr)
        return 1
    finally:
        if radar is not None:
            radar.close()
        if log is not None:
            log.close()
            print(f"recorded to {args.record}")

    if scope is not None and not scope.closed:
        scope.hold()
    return 0


if __name__ == "__main__":
    sys.exit(main())
