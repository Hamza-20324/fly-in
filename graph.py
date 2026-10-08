from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from models import Connection, Zone


class DroneGraph:
    """Store zones, bidirectional connections, and start/end references."""

    def __init__(self) -> None:
        """Create an empty graph."""
        self._zones: dict[str, Zone] = {}
        self._connections: list[Connection] = []
        self._adjacency: dict[str, list[Connection]] = {}
        self.start: Optional[Zone] = None  # noqa: UP045
        self.end: Optional[Zone] = None  # noqa: UP045

    @property
    def zones(self) -> dict[str, Zone]:
        """Return the zone mapping."""
        return self._zones

    @property
    def connections(self) -> list[Connection]:
        """Return all declared connections."""
        return self._connections

    def add_zone(self, zone: Zone) -> None:
        """Add one already-validated zone."""
        self._zones[zone.name] = zone
        self._adjacency[zone.name] = []
        if zone.is_start:
            self.start = zone
        if zone.is_end:
            self.end = zone

    def add_connection(self, connection: Connection) -> None:
        """Add a bidirectional connection to adjacency lists."""
        self._connections.append(connection)
        self._adjacency[connection.first.name].append(connection)
        self._adjacency[connection.second.name].append(connection)

    def get_zone(self, name: str) -> Zone:
        """Return a zone by name."""
        return self._zones[name]

    def neighbors(self, zone: Zone) -> Iterable[tuple[Zone, Connection]]:
        """Yield adjacent zones with their connection objects."""
        for connection in self._adjacency[zone.name]:
            yield connection.other(zone), connection

    def connection_between(self, first: Zone, second: Zone) -> Connection:
        """Return the connection joining two adjacent zones."""
        for connection in self._adjacency[first.name]:
            if connection.other(first) is second:
                return connection
        raise KeyError(f"no connection between {first.name} and {second.name}")
