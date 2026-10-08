from __future__ import annotations

import heapq
from collections import Counter, deque
from dataclasses import dataclass
from typing import Optional

from errors import NoRouteError, SimulationError
from flow import FlowEdge, MinCostFlow
from graph import DroneGraph
from models import Connection, DronePlan, PlannedMove, Zone, ZoneType

DirectionKey = tuple[str, int, str, str]


@dataclass(frozen=True)
class MoveMetadata:
    """Metadata stored on a temporal movement edge."""

    connection: Connection
    origin: Zone
    destination: Zone
    depart_turn: int
    arrival_turn: int


@dataclass
class TemporalSolution:
    """Internal flow result for one horizon."""

    network: MinCostFlow
    source: int
    sink: int
    horizon: int


class TemporalOptimizer:
    """Find a minimal-turn schedule using a time-expanded flow network.

    Zone capacities are represented as node capacities on every time layer.  Waiting
    and movement edges advance time.  Entering a restricted zone advances two turns,
    which naturally models one intermediate turn in flight.
    """

    _WAIT_COST = 4
    _NORMAL_MOVE_COST = 1
    _PRIORITY_MOVE_COST = 0

    def __init__(self, graph: DroneGraph, drone_count: int) -> None:
        """Create an optimizer for one parsed map."""
        if graph.start is None or graph.end is None:
            raise SimulationError("graph has no start or end zone")
        self.graph = graph
        self.drone_count = drone_count
        self._distance_to_end = self._compute_distances_to_end()
        if graph.start.name not in self._distance_to_end:
            raise NoRouteError("no path exists between start_hub and end_hub")

    def solve(self, max_turns: Optional[int] = None) -> list[DronePlan]:  # noqa: UP045
        """Find and return a validated minimal-horizon set of drone plans."""
        start = self.graph.start
        if start is None:
            raise SimulationError("graph has no start zone")
        lower = self._distance_to_end[start.name]
        if lower < 1:  # noqa: PLR1730
            lower = 1
        upper = lower
        solution = self._solve_horizon(upper)
        while solution is None:
            if max_turns is not None and upper >= max_turns:
                raise SimulationError(
                    f"no schedule found within {max_turns} simulation turns"
                )
            upper = max(upper + 1, upper * 2)
            if max_turns is not None:
                upper = min(upper, max_turns)
            solution = self._solve_horizon(upper)
        best = solution
        left = lower
        right = upper
        while left < right:
            middle = (left + right) // 2
            candidate = self._solve_horizon(middle)
            if candidate is None:
                left = middle + 1
            else:
                best = candidate
                right = middle
        if best.horizon != left:
            exact = self._solve_horizon(left)
            if exact is None:
                raise SimulationError("internal horizon search inconsistency")
            best = exact
        return self._decompose(best)

    def _solve_horizon(self, horizon: int) -> Optional[TemporalSolution]:  # noqa: UP045
        """Return a full-flow solution for a fixed number of turns if possible.

        Opposite directions share one physical connection capacity.  A standard
        single-commodity network represents directional movement edges separately,
        so if a candidate uses both directions beyond the shared limit we branch on
        the possible capacity split for that connection/turn and solve again.  This
        keeps the final schedule faithful to the subject's undirected link limit.
        """
        queue: deque[dict[DirectionKey, int]] = deque([{}])
        visited: set[tuple[tuple[DirectionKey, int], ...]] = set()
        while queue:
            limits = queue.popleft()
            signature = tuple(sorted(limits.items()))
            if signature in visited:
                continue
            visited.add(signature)
            solution = self._build_horizon(horizon, limits)
            if solution is None:
                continue
            plans = self._decompose(solution)
            conflict = self._first_link_conflict(plans)
            if conflict is None:
                return solution
            connection, turn, forward_count, reverse_count = conflict
            capacity = connection.max_link_capacity
            splits = list(range(capacity + 1))
            first_distance = self._distance_to_end.get(
                connection.second.name, 10**30
            )
            second_distance = self._distance_to_end.get(
                connection.first.name, 10**30
            )
            if first_distance <= second_distance:
                splits.sort(reverse=True)
            else:
                splits.sort()
            for forward_limit in splits:
                reverse_limit = capacity - forward_limit
                if forward_count > 0 and reverse_count > 0:
                    child = dict(limits)
                    child[(
                        connection.name,
                        turn,
                        connection.first.name,
                        connection.second.name,
                    )] = forward_limit
                    child[(
                        connection.name,
                        turn,
                        connection.second.name,
                        connection.first.name,
                    )] = reverse_limit
                    queue.append(child)
        return None

    def _build_horizon(
        self,
        horizon: int,
        direction_limits: dict[tuple[str, int, str, str], int],
    ) -> Optional[TemporalSolution]:  # noqa: UP045
        """Build and solve one temporal network with direction-capacity cuts."""
        network = MinCostFlow()
        source = network.add_node()
        sink = network.add_node()
        zone_nodes: dict[tuple[str, int], tuple[int, int]] = {}
        usable_zones = [
            zone
            for zone in self.graph.zones.values()
            if zone.zone_type is not ZoneType.BLOCKED
            or zone.is_start
            or zone.is_end
        ]
        for turn in range(horizon + 1):
            for zone in usable_zones:
                node_in = network.add_node()
                node_out = network.add_node()
                zone_nodes[(zone.name, turn)] = (node_in, node_out)
                capacity = (
                    self.drone_count
                    if zone.capacity_is_unlimited
                    else zone.max_drones
                )
                network.add_edge(node_in, node_out, capacity)
        start = self.graph.start
        end = self.graph.end
        if start is None or end is None:
            return None
        network.add_edge(
            source,
            zone_nodes[(start.name, 0)][0],
            self.drone_count,
        )
        for turn in range(horizon + 1):
            network.add_edge(
                zone_nodes[(end.name, turn)][1],
                sink,
                self.drone_count,
            )
        for turn in range(horizon):
            for zone in usable_zones:
                if zone.is_end:
                    continue
                current_out = zone_nodes[(zone.name, turn)][1]
                next_in = zone_nodes[(zone.name, turn + 1)][0]
                capacity = (
                    self.drone_count
                    if zone.capacity_is_unlimited
                    else zone.max_drones
                )
                network.add_edge(
                    current_out,
                    next_in,
                    capacity,
                    self._WAIT_COST,
                )
            for connection in self.graph.connections:
                self._add_direction(
                    network,
                    zone_nodes,
                    connection,
                    connection.first,
                    connection.second,
                    turn,
                    horizon,
                    direction_limits,
                )
                self._add_direction(
                    network,
                    zone_nodes,
                    connection,
                    connection.second,
                    connection.first,
                    turn,
                    horizon,
                    direction_limits,
                )
        flow, _ = network.send(source, sink, self.drone_count)
        if flow != self.drone_count:
            return None
        return TemporalSolution(network, source, sink, horizon)

    def _first_link_conflict(
        self,
        plans: list[DronePlan],
    ) -> Optional[tuple[Connection, int, int, int]]:  # noqa: UP045
        """Return the first shared-link capacity conflict, if one exists."""
        counts: Counter[tuple[str, int, str, str]] = Counter()
        for plan in plans:
            for move in plan.moves:
                counts[(
                    move.connection.name,
                    move.depart_turn,
                    move.origin.name,
                    move.destination.name,
                )] += 1
        for connection in self.graph.connections:
            final_turn = max(
                (plan.delivered_turn for plan in plans), default=0
            )
            for turn in range(final_turn):
                forward = counts[(
                    connection.name,
                    turn,
                    connection.first.name,
                    connection.second.name,
                )]
                reverse = counts[(
                    connection.name,
                    turn,
                    connection.second.name,
                    connection.first.name,
                )]
                if forward + reverse > connection.max_link_capacity:
                    return connection, turn, forward, reverse
        return None

    def _add_direction(
        self,
        network: MinCostFlow,
        zone_nodes: dict[tuple[str, int], tuple[int, int]],
        connection: Connection,
        origin: Zone,
        destination: Zone,
        turn: int,
        horizon: int,
        direction_limits: dict[tuple[str, int, str, str], int],
    ) -> None:
        """Add one direction of one temporal movement."""
        if destination.zone_type is ZoneType.BLOCKED:
            return
        duration = destination.zone_type.movement_cost
        arrival = turn + duration
        if arrival > horizon:
            return
        if (origin.name, turn) not in zone_nodes:
            return
        if (destination.name, arrival) not in zone_nodes:
            return
        move_cost = (
            self._PRIORITY_MOVE_COST
            if destination.zone_type is ZoneType.PRIORITY
            else self._NORMAL_MOVE_COST
        )
        metadata = MoveMetadata(
            connection=connection,
            origin=origin,
            destination=destination,
            depart_turn=turn,
            arrival_turn=arrival,
        )
        direction_key = (
            connection.name, turn, origin.name, destination.name
        )
        capacity = direction_limits.get(
            direction_key, connection.max_link_capacity
        )
        network.add_edge(
            zone_nodes[(origin.name, turn)][1],
            zone_nodes[(destination.name, arrival)][0],
            capacity,
            move_cost,
            metadata,
        )

    def _decompose(self, solution: TemporalSolution) -> list[DronePlan]:
        """Decompose integral flow into individual drone paths."""
        remaining: dict[tuple[int, int], int] = {}
        for node, edges in enumerate(solution.network.graph):
            for index, edge in enumerate(edges):
                if edge.is_forward and edge.flow > 0:
                    remaining[(node, index)] = edge.flow
        plans: list[DronePlan] = []
        for drone_id in range(1, self.drone_count + 1):
            edge_path = self._extract_one_path(
                solution.network,
                solution.source,
                solution.sink,
                remaining,
            )
            moves: list[PlannedMove] = []
            for edge in edge_path:
                if not isinstance(edge.metadata, MoveMetadata):
                    continue
                item = edge.metadata
                moves.append(
                    PlannedMove(
                        connection=item.connection,
                        origin=item.origin,
                        destination=item.destination,
                        depart_turn=item.depart_turn,
                        arrival_turn=item.arrival_turn,
                    )
                )
            moves.sort(key=lambda move: move.depart_turn)
            plans.append(DronePlan(drone_id=drone_id, moves=moves))
        return plans

    def _extract_one_path(
        self,
        network: MinCostFlow,
        source: int,
        sink: int,
        remaining: dict[tuple[int, int], int],
    ) -> list[FlowEdge]:
        """Extract one positive-flow source-to-sink path."""
        parent: dict[int, tuple[int, int]] = {}
        stack = [source]
        visited = {source}
        while stack:
            node = stack.pop()
            if node == sink:
                break
            for index, edge in enumerate(network.graph[node]):
                if not edge.is_forward:
                    continue
                if remaining.get((node, index), 0) <= 0:
                    continue
                if edge.to in visited:
                    continue
                visited.add(edge.to)
                parent[edge.to] = (node, index)
                stack.append(edge.to)
        if sink not in parent:
            raise SimulationError("could not decompose temporal flow")
        path: list[FlowEdge] = []
        node = sink
        while node != source:
            previous, index = parent[node]
            edge = network.graph[previous][index]
            key = (previous, index)
            remaining[key] -= 1
            path.append(edge)
            node = previous
        path.reverse()
        return path

    def _compute_distances_to_end(self) -> dict[str, int]:
        """Compute weighted shortest travel time to the end with Dijkstra."""
        end = self.graph.end
        if end is None:
            return {}
        distance: dict[str, int] = {end.name: 0}
        queue: list[tuple[int, str]] = [(0, end.name)]
        while queue:
            current, name = heapq.heappop(queue)
            if current != distance.get(name):
                continue
            zone = self.graph.get_zone(name)
            for neighbor, _ in self.graph.neighbors(zone):
                if zone.zone_type is ZoneType.BLOCKED and not zone.is_end:
                    continue
                if neighbor.zone_type is ZoneType.BLOCKED and not neighbor.is_start:
                    continue
                # Reverse relaxation: moving neighbor -> zone costs zone's type.
                weight = zone.zone_type.movement_cost
                candidate = current + weight
                if candidate < distance.get(neighbor.name, 10**30):
                    distance[neighbor.name] = candidate
                    heapq.heappush(queue, (candidate, neighbor.name))
        return distance
