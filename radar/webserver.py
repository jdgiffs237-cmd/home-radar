"""
Serves the PPI scope to a browser: plain HTTP for the page, Server-Sent
Events for the frames. Standard library only -- no Flask, no websockets.

The acquisition thread runs the exact same chain run_sim.py / run_live.py
run, then publishes each frame as one JSON blob to every connected browser.
A slow browser drops frames rather than lagging behind the radar.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class Broadcaster:
    """Fan one stream of frames out to any number of SSE clients."""

    def __init__(self):
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()
        self.last_frame: str | None = None  # so a new client gets a picture at once

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=8)
        with self._lock:
            self._clients.append(q)
        if self.last_frame is not None:
            q.put_nowait(self.last_frame)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, payload: dict) -> None:
        data = json.dumps(payload)
        self.last_frame = data
        with self._lock:
            for q in self._clients:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    # drop the oldest frame; live view beats complete view
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    q.put_nowait(data)


def frame_payload(sweep, detections, tracks, *, source: str, warning: str | None) -> dict:
    return {
        "frame": sweep.frame,
        "source": source,
        "warning": warning,
        "returns": [
            {"a": r.angle_deg, "r": r.range_m} for r in sweep.sorted_by_angle()
        ],
        "detections": [
            {"a": d.angle_deg, "r": d.range_m, "s": d.strength} for d in detections
        ],
        "tracks": [
            {
                "id": t.track_id,
                "x": t.x, "y": t.y,
                "range": t.range_m, "angle": t.angle_deg, "speed": t.speed_ms,
                "confirmed": t.confirmed,
                "history": t.history[-30:],
            }
            for t in tracks
        ],
        "cfg": {
            "max_range": config.MAX_RANGE_M,
            "fov_min": config.FOV_MIN_DEG,
            "fov_max": config.FOV_MAX_DEG,
            "step": config.STEP_DEG,
            "trail": config.PPI_TRAIL_FRAMES,
        },
    }


def acquisition_loop(
    source,
    bc: Broadcaster,
    *,
    label: str,
    delay: float = 0.0,
    use_clutter_map: bool = True,
) -> None:
    """Run the processing chain over `source` (an iterable of Sweeps) forever."""
    from .detect import ClutterMap, find_targets
    from .track import Tracker

    clutter = ClutterMap() if use_clutter_map else None
    tracker = Tracker()
    warning: str | None = None
    last_t = time.time()

    for sweep in source:
        now = time.time()
        dt = max(now - last_t, 1e-3)
        last_t = now

        detections: list = []
        tracks: list = []
        try:
            if clutter is not None:
                clutter.update(sweep)
            detections = find_targets(sweep, clutter)
            tracks = tracker.update(detections, dt if label != "sim" else config.FRAME_TIME_S)
            warning = None
        except NotImplementedError:
            warning = ("showing raw returns only -- do the exercises in "
                       "radar/detect.py and radar/track.py, then restart")

        bc.publish(frame_payload(sweep, detections, tracks, source=label, warning=warning))

        if delay > 0:
            time.sleep(delay)

    bc.publish({"frame": -1, "source": label, "warning": "source ended",
                "returns": [], "detections": [], "tracks": [], "cfg": {}})


class RadarHandler(BaseHTTPRequestHandler):
    broadcaster: Broadcaster  # set by serve()

    def do_GET(self):  # noqa: N802 -- BaseHTTPRequestHandler's spelling
        if self.path in ("/", "/index.html"):
            body = (WEB_DIR / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/events":
            self._serve_events()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_events(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        q = self.broadcaster.subscribe()
        try:
            while True:
                try:
                    data = q.get(timeout=15.0)
                    self.wfile.write(f"data: {data}\n\n".encode("ascii"))
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")  # SSE comment, keeps proxies happy
                self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # browser tab closed
        finally:
            self.broadcaster.unsubscribe(q)

    def log_message(self, fmt, *args):
        pass  # keep the console for radar output, not access logs


def serve(source, *, label: str, http_port: int = 8000, delay: float = 0.0,
          use_clutter_map: bool = True) -> ThreadingHTTPServer:
    """Start the acquisition thread and the HTTP server. Blocks forever."""
    bc = Broadcaster()
    RadarHandler.broadcaster = bc

    t = threading.Thread(
        target=acquisition_loop,
        args=(source, bc),
        kwargs={"label": label, "delay": delay, "use_clutter_map": use_clutter_map},
        daemon=True,
    )
    t.start()

    httpd = ThreadingHTTPServer(("127.0.0.1", http_port), RadarHandler)
    httpd.serve_forever()
    return httpd
