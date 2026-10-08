from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ZoneType(str, Enum):
    """Supported zone types from the subject."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def movement_cost(self) -> int:
        """Return the number of turns needed to enter this zone."""
        if self is ZoneType.RESTRICTED:
            return 2
        return 1


@dataclass(eq=False)
class Zone:
    """A graph zone.

    Attributes:
        name: Unique zone name.
        x: X coordinate from the input map.
        y: Y coordinate from the input map.
        zone_type: Movement semantics for entering the zone.
        color: Optional visualization color.
        max_drones: Maximum occupancy for regular zones.
        is_start: Whether this is the unique start zone.
        is_end: Whether this is the unique end zone.
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: Optional[str] = None  # noqa: UP045
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

    @property
    def capacity_is_unlimited(self) -> bool:
        """Return whether occupancy is unlimited for this zone."""
        return self.is_start or self.is_end


@dataclass(eq=False)
class Connection:
    """A bidirectional connection between two zones."""

    first: Zone
    second: Zone
    max_link_capacity: int = 1
    name: str = ""

    def __post_init__(self) -> None:
        """Use the declaration order as the printable connection name."""
        if not self.name:
            self.name = f"{self.first.name}-{self.second.name}"

    def other(self, zone: Zone) -> Zone:
        """Return the opposite endpoint.

        Args:
            zone: One endpoint of this connection.

        Returns:
            The other endpoint.

        Raises:
            ValueError: If *zone* is not attached to this connection.
        """
        if zone is self.first:
            return self.second
        if zone is self.second:
            return self.first
        raise ValueError(f"zone {zone.name!r} is not on {self.name!r}")

    def key(self) -> frozenset[str]:
        """Return an undirected key used for duplicate detection."""
        return frozenset((self.first.name, self.second.name))


@dataclass(frozen=True)
class PlannedMove:
    """A single scheduled movement for one drone."""

    connection: Connection
    origin: Zone
    destination: Zone
    depart_turn: int
    arrival_turn: int

    @property
    def duration(self) -> int:
        """Return the movement duration in turns."""
        return self.arrival_turn - self.depart_turn


@dataclass
class DronePlan:
    """The complete movement plan assigned to a single drone."""

    drone_id: int
    moves: list[PlannedMove] = field(default_factory=list)

    @property
    def delivered_turn(self) -> int:
        """Return the turn in which the drone reaches the end zone."""
        if not self.moves:
            return 0
        return self.moves[-1].arrival_turn


@dataclass
class SimulationResult:
    """Validated simulation output and metadata."""

    plans: list[DronePlan]
    turns: list[list[str]]
    total_turns: int

    def plain_lines(self) -> list[str]:
        """Return subject-compliant output lines."""
        return [" ".join(moves) for moves in self.turns]
