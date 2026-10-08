from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FlowEdge:
    """Residual edge used by :class:`MinCostFlow`."""

    to: int
    reverse: int
    capacity: int
    cost: int
    initial_capacity: int
    metadata: Optional[Any] = None  # noqa: UP045
    is_forward: bool = True

    @property
    def flow(self) -> int:
        """Return current positive flow on an original forward edge."""
        if not self.is_forward:
            return 0
        return self.initial_capacity - self.capacity


class MinCostFlow:
    """Successive-shortest-path min-cost max-flow with potentials."""

    def __init__(self) -> None:
        """Create an empty residual network."""
        self.graph: list[list[FlowEdge]] = []

    def add_node(self) -> int:
        """Add one node and return its integer index."""
        self.graph.append([])
        return len(self.graph) - 1

    def add_edge(
        self,
        source: int,
        target: int,
        capacity: int,
        cost: int = 0,
        metadata: Optional[Any] = None,  # noqa: UP045
    ) -> None:
        """Add a directed capacitated edge and its residual reverse edge."""
        if capacity < 0:
            raise ValueError("capacity cannot be negative")
        forward = FlowEdge(
            to=target,
            reverse=len(self.graph[target]),
            capacity=capacity,
            cost=cost,
            initial_capacity=capacity,
            metadata=metadata,
            is_forward=True,
        )
        reverse = FlowEdge(
            to=source,
            reverse=len(self.graph[source]),
            capacity=0,
            cost=-cost,
            initial_capacity=0,
            metadata=None,
            is_forward=False,
        )
        self.graph[source].append(forward)
        self.graph[target].append(reverse)

    def send(
        self,
        source: int,
        sink: int,
        required: int,
    ) -> tuple[int, int]:
        """Send up to *required* units of flow at minimum cost.

        Returns:
            A pair ``(flow, cost)``.
        """
        size = len(self.graph)
        potential = [0] * size
        total_flow = 0
        total_cost = 0
        infinity = 10**30

        while total_flow < required:
            distance = [infinity] * size
            previous_node = [-1] * size
            previous_edge = [-1] * size
            distance[source] = 0
            queue: list[tuple[int, int]] = [(0, source)]
            while queue:
                current_distance, node = heapq.heappop(queue)
                if current_distance != distance[node]:
                    continue
                for edge_index, edge in enumerate(self.graph[node]):
                    if edge.capacity <= 0:
                        continue
                    reduced = edge.cost + potential[node] - potential[edge.to]
                    candidate = current_distance + reduced
                    if candidate < distance[edge.to]:
                        distance[edge.to] = candidate
                        previous_node[edge.to] = node
                        previous_edge[edge.to] = edge_index
                        heapq.heappush(queue, (candidate, edge.to))
            if distance[sink] == infinity:
                break
            for node in range(size):
                if distance[node] < infinity:
                    potential[node] += distance[node]
            pushed = required - total_flow
            node = sink
            while node != source:
                parent = previous_node[node]
                edge_index = previous_edge[node]
                if parent < 0 or edge_index < 0:
                    pushed = 0
                    break
                edge = self.graph[parent][edge_index]
                pushed = min(pushed, edge.capacity)
                node = parent
            if pushed <= 0:
                break
            node = sink
            path_cost = 0
            while node != source:
                parent = previous_node[node]
                edge_index = previous_edge[node]
                edge = self.graph[parent][edge_index]
                path_cost += edge.cost
                edge.capacity -= pushed
                reverse = self.graph[edge.to][edge.reverse]
                reverse.capacity += pushed
                node = parent
            total_flow += pushed
            total_cost += pushed * path_cost
        return total_flow, total_cost
