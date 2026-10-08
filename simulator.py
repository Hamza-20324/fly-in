from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from errors import SimulationError
from graph import DroneGraph
from models import DronePlan, SimulationResult, Zone, ZoneType
from optimizer import TemporalOptimizer


class Simulator:
    """Produce and independently validate a complete drone simulation."""

    def __init__(self, graph: DroneGraph, drone_count: int) -> None:
        """Create a simulator for one graph and fleet size."""
        self.graph = graph
        self.drone_count = drone_count

    def run(self, max_turns: Optional[int] = None) -> SimulationResult:  # noqa: UP045
        """Optimize, validate, and format the simulation."""
        optimizer = TemporalOptimizer(self.graph, self.drone_count)
        plans = optimizer.solve(max_turns=max_turns)
        self._validate(plans)
        total_turns = max((plan.delivered_turn for plan in plans), default=0)
        turns: list[list[str]] = [[] for _ in range(total_turns)]
        for plan in sorted(plans, key=lambda item: item.drone_id):
            for move in plan.moves:
                if move.duration == 2:
                    turns[move.depart_turn].append(
                        f"D{plan.drone_id}-{move.connection.name}"
                    )
                turns[move.arrival_turn - 1].append(
                    f"D{plan.drone_id}-{move.destination.name}"
                )
        return SimulationResult(
            plans=plans,
            turns=turns,
            total_turns=total_turns,
        )

    def _validate(self, plans: list[DronePlan]) -> None:
        """Check a generated schedule against the subject rules."""
        if len(plans) != self.drone_count:
            raise SimulationError("optimizer did not return every drone")
        start = self.graph.start
        end = self.graph.end
        if start is None or end is None:
            raise SimulationError("graph has no start/end")
        link_use: Counter[tuple[str, int]] = Counter()
        max_time = 0
        for plan in plans:
            current = start
            current_time = 0
            delivered = False
            for move in plan.moves:
                if delivered:
                    raise SimulationError("delivered drone moved again")
                if move.origin is not current:
                    raise SimulationError(
                        f"D{plan.drone_id} has a discontinuous route"
                    )
                if move.depart_turn < current_time:
                    raise SimulationError(
                        f"D{plan.drone_id} has overlapping movements"
                    )
                if move.destination.zone_type is ZoneType.BLOCKED:
                    raise SimulationError("a drone enters a blocked zone")
                expected = move.destination.zone_type.movement_cost
                if move.duration != expected:
                    raise SimulationError("incorrect movement duration")
                attached = {
                    move.connection.first.name,
                    move.connection.second.name,
                }
                if {move.origin.name, move.destination.name} != attached:
                    raise SimulationError("movement uses a wrong connection")
                link_use[(move.connection.name, move.depart_turn)] += 1
                current = move.destination
                current_time = move.arrival_turn
                if current.is_end:
                    delivered = True
            if not delivered:
                raise SimulationError(f"D{plan.drone_id} never reaches the end")
            max_time = max(max_time, current_time)
        connection_by_name = {
            connection.name: connection for connection in self.graph.connections
        }
        for (name, _), count in link_use.items():
            capacity = connection_by_name[name].max_link_capacity
            if count > capacity:
                raise SimulationError(
                    f"connection {name!r} exceeds capacity {capacity}"
                )
        self._validate_zone_occupancy(plans, max_time)

    def _validate_zone_occupancy(
        self,
        plans: list[DronePlan],
        max_time: int,
    ) -> None:
        """Check every integer-time zone occupancy after simultaneous moves."""
        start = self.graph.start
        end = self.graph.end
        if start is None or end is None:
            raise SimulationError("graph has no start/end")
        for time in range(max_time + 1):
            occupancy: defaultdict[str, int] = defaultdict(int)
            for plan in plans:
                zone = self._zone_at_time(plan, time, start, end)
                if zone is not None:
                    occupancy[zone.name] += 1
            for name, count in occupancy.items():
                zone = self.graph.get_zone(name)
                if zone.capacity_is_unlimited:
                    continue
                if count > zone.max_drones:
                    raise SimulationError(
                        f"zone {name!r} exceeds capacity at turn {time}"
                    )

    @staticmethod
    def _zone_at_time(
        plan: DronePlan,
        time: int,
        start: Zone,
        end: Zone,
    ) -> Optional[Zone]:  # noqa: UP045
        """Return the drone's occupied zone at an integer time, or None in transit."""
        current = start
        current_time = 0
        for move in plan.moves:
            if time < move.depart_turn:
                return current
            if time == move.depart_turn:
                return current
            if move.depart_turn < time < move.arrival_turn:
                return None
            current = move.destination
            current_time = move.arrival_turn
            if time == current_time:
                if current is end:
                    return end
                return current
        if current is end and time > current_time:
            return None
        return current
