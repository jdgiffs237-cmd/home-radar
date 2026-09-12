"""
PPI scope -- the round sweep display.

Radar at the origin, range as radius, bearing as angle. Raw returns fade
over a few frames so you can see motion; detections get rings; tracks get an
ID, a history tail, and a velocity vector.

    scope = PPIScope()
    scope.update(sweep, detections, tracks)

Uses matplotlib in interactive mode, so it works the same from a plain
python run or from VS Code. Close the window to stop.
"""

from __future__ import annotations

import math
from collections import deque

import matplotlib.pyplot as plt
import numpy as np

from . import config
from .scan import Detection, Sweep, Track


class PPIScope:
    def __init__(self, max_range: float = config.MAX_RANGE_M, title: str = "home-radar"):
        self.max_range = max_range
        self.trail: deque[Sweep] = deque(maxlen=config.PPI_TRAIL_FRAMES)
        self._closed = False

        plt.ion()
        self.fig, self.ax = plt.subplots(
            figsize=(9, 5.2), subplot_kw={"projection": "polar"}
        )
        # a 180-degree polar axes only fills the top half of its box, so
        # stretch the box past the figure to use the space
        self.fig.subplots_adjust(left=0.04, right=0.96, bottom=-0.28, top=1.14)
        self.fig.canvas.manager.set_window_title(title)
        self.fig.canvas.mpl_connect("close_event", self._on_close)

        self.ax.set_theta_zero_location("E")
        self.ax.set_theta_direction(1)
        self.ax.set_thetamin(config.FOV_MIN_DEG)
        self.ax.set_thetamax(config.FOV_MAX_DEG)
        self.ax.set_rmax(max_range)
        self.ax.set_rticks(np.arange(1.0, max_range + 0.01, 1.0))
        self.ax.set_rlabel_position(90)
        self.ax.grid(True, color="#2f7d4f", alpha=0.35, linewidth=0.6)
        self.ax.set_facecolor("#04140a")
        self.fig.patch.set_facecolor("#04140a")
        self.ax.tick_params(colors="#7fdca4", labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color("#2f7d4f")

        self._status = self.fig.text(
            0.015, 0.965, "", color="#7fdca4", fontsize=9, family="monospace"
        )

    def _on_close(self, _event: object) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    def update(
        self,
        sweep: Sweep,
        detections: list[Detection] | None = None,
        tracks: list[Track] | None = None,
    ) -> None:
        if self._closed:
            return

        detections = detections or []
        tracks = tracks or []
        self.trail.append(sweep)

        # redraw from scratch each frame: at 0.5 Hz this is free, and it
        # avoids a pile of artist-management bugs
        self.ax.cla()
        self._style_axes()

        # raw returns, oldest faintest
        n = len(self.trail)
        for age, old in enumerate(self.trail):
            alpha = 0.15 + 0.55 * (age + 1) / n
            hits = [r for r in old.returns if not r.is_miss]
            if not hits:
                continue
            self.ax.scatter(
                [math.radians(r.angle_deg) for r in hits],
                [r.range_m for r in hits],
                s=14,
                c="#37e07a",
                alpha=alpha,
                edgecolors="none",
                zorder=2,
            )

        # detections
        if detections:
            self.ax.scatter(
                [math.radians(d.angle_deg) for d in detections],
                [d.range_m for d in detections],
                s=140,
                facecolors="none",
                edgecolors="#ffd166",
                linewidths=1.4,
                zorder=3,
            )

        # tracks
        for tr in tracks:
            if not tr.confirmed:
                continue
            th = math.radians(tr.angle_deg)
            self.ax.scatter(
                [th], [tr.range_m], s=70, c="#ff5d8f", marker="s", zorder=4
            )
            self.ax.text(
                th,
                tr.range_m + 0.12,
                f"T{tr.track_id}  {tr.speed_ms:.2f} m/s",
                color="#ff9ec0",
                fontsize=7,
                family="monospace",
                zorder=5,
            )
            if len(tr.history) > 1:
                hs = tr.history[-12:]
                self.ax.plot(
                    [math.atan2(y, x) for x, y in hs],
                    [math.hypot(x, y) for x, y in hs],
                    color="#ff5d8f",
                    alpha=0.5,
                    linewidth=1.0,
                    zorder=3,
                )
            # velocity vector, 2 s of travel ahead
            if tr.speed_ms > 0.02:
                px, py = tr.predict(2.0)
                self.ax.plot(
                    [th, math.atan2(py, px)],
                    [tr.range_m, math.hypot(px, py)],
                    color="#ff5d8f",
                    alpha=0.8,
                    linewidth=1.2,
                    zorder=4,
                )

        hits = sum(1 for r in sweep.returns if not r.is_miss)
        self._status.set_text(
            f"frame {sweep.frame:<5d} returns {hits:>2d}/{len(sweep.returns):<3d} "
            f"plots {len(detections):<3d} tracks {sum(t.confirmed for t in tracks):<3d}"
        )

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.001)

    def _style_axes(self) -> None:
        self.ax.set_theta_zero_location("E")
        self.ax.set_theta_direction(1)
        self.ax.set_thetamin(config.FOV_MIN_DEG)
        self.ax.set_thetamax(config.FOV_MAX_DEG)
        self.ax.set_rmax(self.max_range)
        self.ax.set_rticks(np.arange(1.0, self.max_range + 0.01, 1.0))
        self.ax.set_rlabel_position(90)
        self.ax.grid(True, color="#2f7d4f", alpha=0.35, linewidth=0.6)
        self.ax.set_facecolor("#04140a")
        self.ax.tick_params(colors="#7fdca4", labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color("#2f7d4f")

    def hold(self) -> None:
        """Keep the window open after the data runs out."""
        plt.ioff()
        plt.show()


def print_ascii(sweep: Sweep, detections: list[Detection] | None = None) -> None:
    """
    Text scope, for when matplotlib is a nuisance (SSH, a quick sanity check,
    or debugging a headless run).
    """
    det_angles = {round(d.angle_deg) for d in (detections or [])}
    print(f"--- frame {sweep.frame} ---")
    for r in sweep.sorted_by_angle():
        if r.is_miss:
            bar = "."
        else:
            width = int(40 * (1 - r.range_m / config.MAX_RANGE_M))
            bar = "#" * max(1, width)
        mark = " <=" if round(r.angle_deg) in det_angles else ""
        rng = "  --  " if r.is_miss else f"{r.range_m:5.2f}m"
        print(f"{r.angle_deg:5.0f}  {rng}  {bar}{mark}")
