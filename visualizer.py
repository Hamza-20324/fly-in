from __future__ import annotations

import math
import tkinter as tk
from tkinter import TclError

from graph import DroneGraph
from models import DronePlan, SimulationResult, ZoneType

Point = tuple[float, float]


class GraphicalVisualizer:
    """Show the Fly-in graph and animate drones turn by turn."""

    WIDTH = 1200
    HEIGHT = 800

    NODE_RADIUS = 80
    DRONE_RADIUS = 20

    FRAMES = 20
    FRAME_MS = 25

    def __init__(self, graph: DroneGraph) -> None:
        """Create the graphical window."""
        self.graph = graph
        self.result: SimulationResult | None = None

        self.root = tk.Tk()
        self.root.title("Fly-in")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")

        self.canvas = tk.Canvas(
            self.root,
            background="white",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.info = tk.Label(
            self.root,
            text="SPACE = next turn",
            font=("Arial", 13, "bold"),
        )
        self.info.pack(pady=8)

        self.positions: dict[str, Point] = {}
        self.drone_items: dict[int, tuple[int, int]] = {}

        self.current_turn = 0
        self.animating = False
        self._resize_after_id: str | None = None

        self.root.bind("<space>", self._on_space)
        self.root.bind("<Configure>", self._on_resize)

    def show(self, result: SimulationResult) -> None:
        """Draw the graph and start the window loop."""
        self.result = result

        self.root.update_idletasks()
        self._redraw_everything()

        self.root.focus_force()
        self.root.mainloop()

    def _on_resize(self, _event: tk.Event[tk.Misc]) -> None:
        """Redraw graph when the window size changes."""
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)

        self._resize_after_id = self.root.after(
            120,
            self._redraw_everything,
        )

    def _redraw_everything(self) -> None:
        """Recompute layout and redraw graph + current drone state."""
        self.canvas.delete("all")
        self.positions.clear()
        self.drone_items.clear()

        self._compute_positions()
        self._draw_connections()
        self._draw_zones()
        self._draw_drones_at_current_state()
        self._update_info()

    def _compute_positions(self) -> None:
        """Center the graph nicely inside the current canvas."""
        zones = list(self.graph.zones.values())

        if not zones:
            return

        width = max(self.canvas.winfo_width(), self.WIDTH)
        height = max(self.canvas.winfo_height(), self.HEIGHT - 60)

        min_x = min(zone.x for zone in zones)
        max_x = max(zone.x for zone in zones)
        min_y = min(zone.y for zone in zones)
        max_y = max(zone.y for zone in zones)

        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)

        # Keep graph compact and centered even on large windows.
        graph_width = width * 0.95
        graph_height = height * 0.70

        scale = min(
            graph_width / span_x,
            graph_height / span_y,
        )

        real_width = span_x * scale
        real_height = span_y * scale

        left = (width - real_width) / 2
        top = (height - real_height) / 2

        for zone in zones:
            x = left + (zone.x - min_x) * scale
            y = top + real_height - (zone.y - min_y) * scale
            self.positions[zone.name] = (x, y)

    def _draw_connections(self) -> None:
        """Draw all graph links."""
        for connection in self.graph.connections:
            first = self.positions[connection.first.name]
            second = self.positions[connection.second.name]

            self.canvas.create_line(
                first[0],
                first[1],
                second[0],
                second[1],
                fill="#777777",
                width=9,
                arrow=tk.LAST,
                arrowshape=(12, 14, 6),
            )

            if connection.max_link_capacity != 1:
                middle_x = (first[0] + second[0]) / 2
                middle_y = (first[1] + second[1]) / 2

                self.canvas.create_text(
                    middle_x,
                    middle_y - 12,
                    text=f"x{connection.max_link_capacity}",
                    font=("Arial", 10, "bold"),
                    fill="#444444",
                )

    def _draw_zones(self) -> None:
        """Draw all zones as circles."""
        for zone in self.graph.zones.values():
            x, y = self.positions[zone.name]
            color = self._color(zone.color)

            outline = "#111111"
            width = 9

            if zone.is_start or zone.is_end:
                width = 9

            if zone.zone_type is ZoneType.BLOCKED:
                outline = "#555555"
                width = 9

            self.canvas.create_oval(
                x - self.NODE_RADIUS,
                y - self.NODE_RADIUS,
                x + self.NODE_RADIUS,
                y + self.NODE_RADIUS,
                fill=color,
                outline=outline,
                width=width,
            )

            self.canvas.create_text(
                x,
                y,
                text=zone.name,
                font=("Arial", 10, "bold"),
            )

            label = zone.zone_type.value

            if zone.is_start:
                label = "START"
            elif zone.is_end:
                label = "END"

            self.canvas.create_text(
                x,
                y + self.NODE_RADIUS + 16,
                text=label,
                font=("Arial", 10),
                fill="#333333",
            )

            if zone.zone_type is ZoneType.BLOCKED:
                size = self.NODE_RADIUS * 0.65

                self.canvas.create_line(
                    x - size,
                    y - size,
                    x + size,
                    y + size,
                    width=3,
                    fill="#333333",
                )
                self.canvas.create_line(
                    x + size,
                    y - size,
                    x - size,
                    y + size,
                    width=3,
                    fill="#333333",
                )

    def _draw_drones_at_current_state(self) -> None:
        """Draw drones for the current turn."""
        if self.result is None:
            return

        for plan in self.result.plans:
            point = self._point_at(plan, self.current_turn)

            if point is None:
                continue

            self._place_drone(
                plan.drone_id,
                point[0],
                point[1],
            )

    def _on_space(self, _event: tk.Event[tk.Misc]) -> None:
        """Advance exactly one turn."""
        if self.result is None or self.animating:
            return

        if self.current_turn >= self.result.total_turns:
            self._update_info()
            return

        self.animating = True
        self._animate_turn(self.current_turn + 1, 0)

    def _animate_turn(self, target_turn: int, frame: int) -> None:
        """Animate all drones from one turn to the next."""
        if self.result is None:
            return

        progress = frame / self.FRAMES

        for plan in self.result.plans:
            start_point = self._point_at(plan, self.current_turn)
            end_point = self._point_at(plan, target_turn)

            if start_point is None and end_point is None:
                self._hide_drone(plan.drone_id)
                continue

            if start_point is None:
                start_point = end_point

            if end_point is None:
                end_point = start_point

            if start_point is None or end_point is None:
                continue

            x = start_point[0] + (end_point[0] - start_point[0]) * progress
            y = start_point[1] + (end_point[1] - start_point[1]) * progress

            self._place_drone(plan.drone_id, x, y)

        if frame < self.FRAMES:
            self.root.after(
                self.FRAME_MS,
                lambda: self._animate_turn(target_turn, frame + 1),
            )
            return

        self.current_turn = target_turn

        for plan in self.result.plans:
            if plan.delivered_turn == target_turn:
                self._hide_drone(plan.drone_id)

        self.animating = False
        self._update_info()

    def _point_at(self, plan: DronePlan, time: int) -> Point | None:
        """Return drone position at one integer turn."""
        if self.graph.start is None:
            return None

        current = self.graph.start

        for move in plan.moves:
            if time <= move.depart_turn:
                break

            if move.depart_turn < time < move.arrival_turn:
                first = self.positions[move.origin.name]
                second = self.positions[move.destination.name]
                fraction = (
                    (time - move.depart_turn)
                    / (move.arrival_turn - move.depart_turn)
                )

                return (
                    first[0] + (second[0] - first[0]) * fraction,
                    first[1] + (second[1] - first[1]) * fraction,
                )

            if time >= move.arrival_turn:
                current = move.destination

        if current.is_end and time > plan.delivered_turn:
            return None

        point = self.positions[current.name]
        return self._offset(point, plan.drone_id)

    def _place_drone(self, drone_id: int, x: float, y: float) -> None:
        """Create or move one drone marker."""
        item = self.drone_items.get(drone_id)

        if item is None:
            circle = self.canvas.create_oval(
                x - self.DRONE_RADIUS,
                y - self.DRONE_RADIUS,
                x + self.DRONE_RADIUS,
                y + self.DRONE_RADIUS,
                fill="#ff9f1c",
                outline="white",
                width=4,
            )

            label = self.canvas.create_text(
                x,
                y,
                text=f"D{drone_id}",
                font=("Arial", 9, "bold"),
            )

            self.drone_items[drone_id] = (circle, label)
            return

        circle, label = item

        self.canvas.coords(
            circle,
            x - self.DRONE_RADIUS,
            y - self.DRONE_RADIUS,
            x + self.DRONE_RADIUS,
            y + self.DRONE_RADIUS,
        )
        self.canvas.coords(label, x, y)

    def _hide_drone(self, drone_id: int) -> None:
        """Remove a delivered drone."""
        item = self.drone_items.pop(drone_id, None)

        if item is None:
            return

        self.canvas.delete(item[0])
        self.canvas.delete(item[1])

    def _update_info(self) -> None:
        """Refresh the info label."""
        if self.result is None:
            return

        delivered = sum(
            1
            for plan in self.result.plans
            if plan.delivered_turn <= self.current_turn
        )

        if self.current_turn >= self.result.total_turns:
            self.info.config(
                text=(
                    f"Finished | Turn {self.result.total_turns} | "
                    f"Delivered {delivered}/{len(self.result.plans)}"
                )
            )
            return

        move_text = ""
        if self.current_turn > 0:
            move_text = " | " + " ".join(self.result.turns[self.current_turn - 1])

        self.info.config(
            text=(
                f"Turn {self.current_turn}/{self.result.total_turns}"
                f" | Delivered {delivered}/{len(self.result.plans)}"
                f" | SPACE = next turn"
                f"{move_text}"
            )
        )

    def _offset(self, point: Point, drone_id: int) -> Point:
        """Place drones inside the zone circle without overlap."""
        if drone_id == 1:
            return point

        slots = 8
        slot = (drone_id - 2) % slots
        ring = (drone_id - 2) // slots

        angle = slot * (2 * math.pi / slots)

        radius = 12 + ring * 10

        max_radius = self.NODE_RADIUS - self.DRONE_RADIUS - 4
        radius = min(radius, max_radius)

        return (
            point[0] + math.cos(angle) * radius,
            point[1] + math.sin(angle) * radius,
        )

    def _color(self, color: str | None) -> str:
        """Return a valid Tk color."""
        if color is None:
            return "lightgray"

        try:
            self.root.winfo_rgb(color)
        except TclError:
            return "lightgray"

        return color
