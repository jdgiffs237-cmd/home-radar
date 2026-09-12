"""
Reads sweeps off the Arduino.

Protocol (see firmware/radar_sweep/radar_sweep.ino):
    # comment
    S <frame>
    R <index> <angle_deg> <range_m>
    E <frame> <count>

Usage:
    with SerialRadar("COM3") as radar:
        for sweep in radar.sweeps():
            ...

The parser is deliberately forgiving: serial from a board that just reset is
full of half-lines and garbage bytes, and a radar that dies on the first
malformed line is useless.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from . import config
from .scan import Return, Sweep


class SerialRadar:
    def __init__(self, port: str, baud: int = config.BAUD, verbose: bool = False):
        try:
            import serial  # noqa: PLC0415  -- optional dep, sim doesn't need it
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "pyserial is not installed. `pip install pyserial`, or use "
                "run_sim.py if you don't have hardware yet."
            ) from exc

        self.port = port
        self.verbose = verbose
        self._ser = serial.Serial(port, baud, timeout=config.SERIAL_TIMEOUT_S)
        # An Arduino resets when the port opens. Give the bootloader a moment
        # or you'll parse the tail of the previous session's output.
        time.sleep(2.0)
        self._ser.reset_input_buffer()

    def __enter__(self) -> SerialRadar:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    def sweeps(self) -> Iterator[Sweep]:
        """Yield complete Sweeps. Partial sweeps at start-up are discarded."""
        current: Sweep | None = None

        while True:
            raw = self._ser.readline()
            if not raw:
                continue
            try:
                line = raw.decode("ascii", errors="replace").strip()
            except Exception:
                continue
            if not line or line.startswith("#"):
                if self.verbose and line:
                    print(line)
                continue

            parts = line.split()
            tag = parts[0]

            if tag == "S" and len(parts) >= 2:
                try:
                    current = Sweep(frame=int(parts[1]), timestamp=time.time())
                except ValueError:
                    current = None

            elif tag == "R" and current is not None and len(parts) >= 4:
                try:
                    current.returns.append(
                        Return(
                            index=int(parts[1]),
                            angle_deg=float(parts[2]),
                            range_m=float(parts[3]),
                        )
                    )
                except ValueError:
                    continue    # mangled line; drop the cell, keep the sweep

            elif tag == "E" and current is not None:
                if current.returns:
                    yield current
                current = None


def replay(path: str) -> Iterator[Sweep]:
    """
    Replay a captured log through the same parser. Record one with:

        python run_live.py --port COM3 --record data/session.log

    Recorded sessions are the fastest way to iterate on detect.py against
    real returns without standing in front of the sensor for an hour.
    """
    current: Sweep | None = None
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            tag = parts[0]
            if tag == "S" and len(parts) >= 2:
                current = Sweep(frame=int(parts[1]))
            elif tag == "R" and current is not None and len(parts) >= 4:
                current.returns.append(
                    Return(
                        index=int(parts[1]),
                        angle_deg=float(parts[2]),
                        range_m=float(parts[3]),
                    )
                )
            elif tag == "E" and current is not None:
                if current.returns:
                    yield current
                current = None
