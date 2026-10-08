from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from errors import ParseError
from graph import DroneGraph
from models import Connection, Zone, ZoneType


@dataclass(frozen=True)
class ParsedMap:
    """Result produced by :class:`MapParser`."""

    graph: DroneGraph
    drone_count: int


class MapParser:
    """Parse and validate one Fly-in input file."""

    _zone_re = re.compile(
        r"^(start_hub|end_hub|hub):\s+([^\s\-\[\]]+)\s+"
        r"([+-]?\d+)\s+([+-]?\d+)(?:\s+(\[.*\]))?$"
    )
    _connection_re = re.compile(
        r"^connection:\s+([^\s\-\[\]]+)-([^\s\-\[\]]+)"
        r"(?:\s+(\[.*\]))?$"
    )
    _drones_re = re.compile(r"^nb_drones:\s*([+-]?\d+)\s*$")
    _metadata_re = re.compile(r"^\[([^\[\]]*)\]$")
    _metadata_item_re = re.compile(r"^([^=\s]+)=([^=\s]+)$")

    def parse(self, path: str | Path) -> ParsedMap:
        """Parse a map file.

        Args:
            path: Input file path.

        Returns:
            Parsed graph and number of drones.

        Raises:
            ParseError: If the input violates the subject syntax.
            OSError: If the file cannot be opened.
        """
        source = Path(path)
        with source.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        return self.parse_lines(lines)

    def parse_lines(self, lines: list[str]) -> ParsedMap:
        """Parse map content supplied as individual lines."""
        graph = DroneGraph()
        drone_count: Optional[int] = None  # noqa: UP045
        first_record_seen = False
        start_count = 0
        end_count = 0
        connections_seen: set[frozenset[str]] = set()

        for number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if not first_record_seen:
                first_record_seen = True
                drone_count = self._parse_drone_count(line, number)
                continue
            if line.startswith("nb_drones:"):
                raise ParseError(number, "nb_drones may only appear first")
            zone_match = self._zone_re.fullmatch(line)
            if zone_match is not None:
                prefix = zone_match.group(1)
                name = zone_match.group(2)
                x = int(zone_match.group(3))
                y = int(zone_match.group(4))
                metadata_text = zone_match.group(5)
                if name in graph.zones:
                    raise ParseError(number, f"duplicate zone name {name!r}")
                is_start = prefix == "start_hub"
                is_end = prefix == "end_hub"
                if is_start:
                    start_count += 1
                    if start_count > 1:
                        raise ParseError(number, "more than one start_hub")
                if is_end:
                    end_count += 1
                    if end_count > 1:
                        raise ParseError(number, "more than one end_hub")
                metadata = self._parse_metadata(metadata_text, number)
                zone = self._make_zone(
                    name,
                    x,
                    y,
                    metadata,
                    is_start,
                    is_end,
                    number,
                )
                graph.add_zone(zone)
                continue
            connection_match = self._connection_re.fullmatch(line)
            if connection_match is not None:
                first_name = connection_match.group(1)
                second_name = connection_match.group(2)
                metadata_text = connection_match.group(3)
                if first_name not in graph.zones or second_name not in graph.zones:
                    raise ParseError(
                        number,
                        "connections may only use previously defined zones",
                    )
                key = frozenset((first_name, second_name))
                if len(key) != 2:
                    raise ParseError(number, "self-connections are not allowed")
                if key in connections_seen:
                    raise ParseError(number, "duplicate connection")
                metadata = self._parse_metadata(metadata_text, number)
                unknown = set(metadata) - {"max_link_capacity"}
                if unknown:
                    key_name = sorted(unknown)[0]  # noqa: FURB192
                    raise ParseError(
                        number,
                        f"unknown connection metadata {key_name!r}",
                    )
                capacity = self._positive_int(
                    metadata.get("max_link_capacity", "1"),
                    number,
                    "max_link_capacity",
                )
                connection = Connection(
                    graph.get_zone(first_name),
                    graph.get_zone(second_name),
                    capacity,
                    f"{first_name}-{second_name}",
                )
                graph.add_connection(connection)
                connections_seen.add(key)
                continue
            raise ParseError(number, "unrecognized or malformed input")

        if not first_record_seen or drone_count is None:
            raise ParseError(1, "missing nb_drones declaration")
        final_line = max(len(lines), 1)
        if start_count != 1:
            raise ParseError(final_line, "exactly one start_hub is required")
        if end_count != 1:
            raise ParseError(final_line, "exactly one end_hub is required")
        return ParsedMap(graph=graph, drone_count=drone_count)

    def _parse_drone_count(self, line: str, number: int) -> int:
        """Parse the mandatory first record."""
        match = self._drones_re.fullmatch(line)
        if match is None:
            raise ParseError(number, "first record must be nb_drones")
        count = int(match.group(1))
        if count <= 0:
            raise ParseError(number, "nb_drones must be a positive integer")
        return count

    def _parse_metadata(
        self,
        text: Optional[str],  # noqa: UP045
        number: int,
    ) -> dict[str, str]:
        """Parse a bracketed metadata block."""
        if text is None:
            return {}
        match = self._metadata_re.fullmatch(text)
        if match is None:
            raise ParseError(number, "malformed metadata block")
        body = match.group(1).strip()
        if not body:
            return {}
        result: dict[str, str] = {}
        for token in body.split():
            item = self._metadata_item_re.fullmatch(token)
            if item is None:
                raise ParseError(number, f"malformed metadata item {token!r}")
            key, value = item.groups()
            if key in result:
                raise ParseError(number, f"duplicate metadata key {key!r}")
            result[key] = value
        return result

    def _make_zone(
        self,
        name: str,
        x: int,
        y: int,
        metadata: dict[str, str],
        is_start: bool,
        is_end: bool,
        number: int,
    ) -> Zone:
        """Validate metadata and construct one zone."""
        unknown = set(metadata) - {"zone", "color", "max_drones"}
        if unknown:
            key_name = sorted(unknown)[0]  # noqa: FURB192
            raise ParseError(number, f"unknown zone metadata {key_name!r}")
        zone_value = metadata.get("zone", ZoneType.NORMAL.value)
        try:
            zone_type = ZoneType(zone_value)
        except ValueError as exc:
            raise ParseError(
                number,
                f"invalid zone type {zone_value!r}",
            ) from exc
        color = metadata.get("color")
        if color is not None and any(char.isspace() for char in color):
            raise ParseError(number, "color must be a single-word string")
        max_drones = 1
        if not (is_start or is_end):
            max_drones = self._positive_int(
                metadata.get("max_drones", "1"),
                number,
                "max_drones",
            )
        return Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )

    @staticmethod
    def _positive_int(value: str, number: int, field: str) -> int:
        """Parse a strictly positive decimal integer."""
        if re.fullmatch(r"\d+", value) is None:
            raise ParseError(number, f"{field} must be a positive integer")
        parsed = int(value)
        if parsed <= 0:
            raise ParseError(number, f"{field} must be a positive integer")
        return parsed
