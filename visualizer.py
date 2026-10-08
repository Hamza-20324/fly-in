from __future__ import annotations

from collections import defaultdict
from typing import Optional

from graph import DroneGraph
from models import DronePlan, SimulationResult, Zone


class TerminalVisualizer:
    """Render zone state after every simulation turn using ANSI colors."""

    _ANSI = {  # noqa: RUF012
        "black": "30",
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "cyan": "36",
        "white": "37",
        "gray": "90",
        "grey": "90",
    }

    def __init__(self, graph: DroneGraph) -> None:
        """Create a visualizer for one graph."""
        self.graph = graph

    def render(self, result: SimulationResult) -> str:
        """Return a complete colored human-readable visualization."""
        start = self.graph.start
        end = self.graph.end
        if start is None or end is None:
            return ""
        chunks: list[str] = []
        for turn in range(1, result.total_turns + 1):
            chunks.append(f"--- Turn {turn} ---")
            occupancy: defaultdict[str, list[str]] = defaultdict(list)
            transit: list[str] = []
            for plan in result.plans:
                zone, connection = self._state_at(plan, turn, start, end)
                if zone is not None and not zone.is_end:
                    occupancy[zone.name].append(f"D{plan.drone_id}")
                elif connection is not None:
                    transit.append(f"D{plan.drone_id}@{connection}")
            for zone in self.graph.zones.values():
                drones = ",".join(occupancy.get(zone.name, [])) or "-"
                chunks.append(
                    f"{self._paint(zone.name, zone.color):>20}: {drones}"
                )
            if transit:
                chunks.append("in_transit: " + " ".join(transit))
            moves = " ".join(result.turns[turn - 1]) or "-"
            chunks.append("moves: " + moves)
        return "\n".join(chunks)

    def _paint(self, text: str, color: Optional[str]) -> str:  # noqa: UP045
        """Apply a known ANSI color, or bold text for unknown color names."""
        if color is None:
            return text
        code = self._ANSI.get(color.lower())
        if code is None:
            return f"\033[1m{text}\033[0m"
        return f"\033[{code}m{text}\033[0m"

    @staticmethod
    def _state_at(
        plan: DronePlan,
        time: int,
        start: Zone,
        end: Zone,
    ) -> tuple[Optional[Zone], Optional[str]]:  # noqa: UP045
        """Return zone or in-transit connection at a given time."""
        current = start
        delivered_time: Optional[int] = None  # noqa: UP045
        for move in plan.moves:
            if time < move.depart_turn:
                break
            if move.depart_turn < time < move.arrival_turn:
                return None, move.connection.name
            if time >= move.arrival_turn:
                current = move.destination
                if current is end:
                    delivered_time = move.arrival_turn
        if delivered_time is not None and time >= delivered_time:
            return None, None
        return current, None
