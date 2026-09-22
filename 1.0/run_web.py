#!/usr/bin/env python3
"""
Web scope. Same radar, but the display is a browser page instead of
matplotlib. Standard library only -- nothing new to install.

    python run_web.py                       simulated radar (start here)
    python run_web.py --port COM3           live, against the Arduino
    python run_web.py --replay data/x.log   replay a recording
    python run_web.py --http-port 9000      if 8000 is already taken

Then open http://localhost:8000 -- it opens automatically unless you pass
--no-browser. Ctrl-C here stops the server.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from radar.webserver import serve


def main() -> int:
    p = argparse.ArgumentParser(description="Radar with a web display")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--port", help="serial port, e.g. COM3 or /dev/ttyUSB0")
    src.add_argument("--replay", help="replay a recorded .log instead")
    p.add_argument("--http-port", type=int, default=8000)
    p.add_argument("--seed", type=int, default=None, help="sim only")
    p.add_argument("--delay", type=float, default=0.35, help="sim only: seconds between frames")
    p.add_argument("--no-clutter-map", action="store_true")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    radar = None
    delay = 0.0
    try:
        if args.port:
            from radar.serial_link import SerialRadar
            radar = SerialRadar(args.port, verbose=True)
            source = radar.sweeps()
            label = args.port
        elif args.replay:
            from radar.serial_link import replay
            source = replay(args.replay)
            label = "replay"
        else:
            from radar.sim import SimRadar, default_world
            source = iter(SimRadar(default_world(), seed=args.seed).sweep, None)
            label = "sim"
            delay = args.delay

        url = f"http://localhost:{args.http_port}"
        print(f"radar web scope on {url}  ({label})")
        print("ctrl-c to stop.")
        if not args.no_browser:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()

        serve(
            source,
            label=label,
            http_port=args.http_port,
            delay=delay,
            use_clutter_map=not args.no_clutter_map,
        )
    except KeyboardInterrupt:
        print("\nstopped.")
    except FileNotFoundError:
        print(f"no such replay file: {args.replay}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"if the port is busy, try --http-port {args.http_port + 1}",
              file=sys.stderr)
        return 1
    finally:
        if radar is not None:
            radar.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
