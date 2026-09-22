#!/usr/bin/env python3
"""
Home Radar 2.0 — see the pings.

    python run_radar.py                 finds the Arduino, opens the scope
    python run_radar.py --port COM3     pick the port yourself
    python run_radar.py --http-port 9000
    python run_radar.py --record data.log

Runs 1.0's proven display pipeline (browser scope at http://localhost:8000)
against the stepper firmware — same protocol, same software, new motor.
Close the Arduino Serial Monitor first; only one program gets the port.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

# All the radar software lives in 1.0 -- reuse it rather than copy it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "1.0"))

from radar.serial_link import SerialRadar          # noqa: E402
from radar.webserver import serve                  # noqa: E402


def find_arduino() -> str | None:
    """Pick the serial port that looks like our board (CH340/Arduino/USB)."""
    from serial.tools import list_ports
    candidates = []
    for p in list_ports.comports():
        desc = (p.description or "").lower()
        if any(tag in desc for tag in ("ch340", "arduino", "usb-serial", "usb serial")):
            candidates.append(p.device)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        print(f"several boards found: {', '.join(candidates)} -- using {candidates[0]}")
        return candidates[0]
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Home Radar 2.0 web scope")
    p.add_argument("--port", help="serial port; omit to auto-detect")
    p.add_argument("--http-port", type=int, default=8000)
    p.add_argument("--record", help="also save raw sweeps to this log file")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    port = args.port or find_arduino()
    if port is None:
        print("no Arduino found. Is it plugged in? Try:", file=sys.stderr)
        print("  python -m serial.tools.list_ports", file=sys.stderr)
        print("then: python run_radar.py --port COMx", file=sys.stderr)
        return 1

    radar = None
    log = open(args.record, "w", encoding="ascii") if args.record else None
    try:
        radar = SerialRadar(port, verbose=True)
        source = radar.sweeps()

        if log is not None:
            def recording(sweeps, fh):
                for sweep in sweeps:
                    fh.write(f"S {sweep.frame}\n")
                    for r in sweep.returns:
                        fh.write(f"R {r.index} {r.angle_deg:.0f} {r.range_m:.3f}\n")
                    fh.write(f"E {sweep.frame} {len(sweep.returns)}\n")
                    fh.flush()
                    yield sweep
            source = recording(source, log)

        url = f"http://localhost:{args.http_port}"
        print(f"radar 2.0 on {url}  (board on {port})")
        print("remember the centering ritual: point it straight ahead when it resets.")
        print("ctrl-c to stop.")
        if not args.no_browser:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()

        serve(source, label=f"2.0 · {port}", http_port=args.http_port)
    except KeyboardInterrupt:
        print("\nstopped.")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
