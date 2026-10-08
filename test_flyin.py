from __future__ import annotations

from pathlib import Path

import pytest

from errors import NoRouteError, ParseError
from parser import MapParser, ParsedMap
from simulator import Simulator

ROOT = Path(__file__).resolve().parent


def parse_text(text: str) -> ParsedMap:
    """Parse a test map from a multiline string."""
    return MapParser().parse_lines(text.strip().splitlines())


def test_linear_two_drones_optimum_four() -> None:
    """A three-edge capacity-1 pipeline finishes two drones in four turns."""
    parsed = parse_text(
        """
nb_drones: 2
start_hub: s 0 0
hub: a 1 0
hub: b 2 0
end_hub: e 3 0
connection: s-a
connection: a-b
connection: b-e
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 4
    assert result.turns[-1] == ["D2-e"]


def test_restricted_pipeline_and_connection_output() -> None:
    """Restricted entry takes two turns and the link can pipeline one per turn."""
    parsed = parse_text(
        """
nb_drones: 2
start_hub: s 0 0
hub: r 1 0 [zone=restricted]
end_hub: e 2 0
connection: s-r [max_link_capacity=1]
connection: r-e
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 4
    flat = result.plain_lines()
    assert "D1-s-r" in flat[0]
    assert "D1-r" in flat[1]
    assert "D2-s-r" in flat[1]


def test_blocked_path_is_unsolvable() -> None:
    """A path through a blocked zone is not a route."""
    parsed = parse_text(
        """
nb_drones: 1
start_hub: s 0 0
hub: x 1 0 [zone=blocked]
end_hub: e 2 0
connection: s-x
connection: x-e
"""
    )
    with pytest.raises(NoRouteError):
        Simulator(parsed.graph, parsed.drone_count).run()


def test_duplicate_connection_is_rejected() -> None:
    """a-b and b-a are the same bidirectional connection."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: a 0 0
end_hub: b 1 0
connection: a-b
connection: b-a
"""
        )


def test_connection_requires_previous_zone_definition() -> None:
    """Connections cannot forward-reference zones."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
connection: s-e
end_hub: e 1 0
"""
        )


def test_start_end_max_drones_is_ignored() -> None:
    """max_drones on start/end never limits their occupancy."""
    parsed = parse_text(
        """
nb_drones: 4
start_hub: s 0 0 [max_drones=1]
end_hub: e 1 0 [max_drones=1]
connection: s-e [max_link_capacity=4]
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 1
    assert len(result.turns[0]) == 4


def test_priority_is_preferred_on_equal_routes() -> None:
    """Min-cost tie-breaking selects a priority zone over a normal one."""
    parsed = parse_text(
        """
nb_drones: 1
start_hub: s 0 0
hub: p 1 1 [zone=priority]
hub: n 1 -1 [zone=normal]
end_hub: e 2 0
connection: s-p
connection: p-e
connection: s-n
connection: n-e
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 2
    assert result.turns[0] == ["D1-p"]


def test_zone_capacity_two_allows_parallel_arrivals() -> None:
    """max_drones=2 permits two simultaneous occupants."""
    parsed = parse_text(
        """
nb_drones: 2
start_hub: s 0 0
hub: a 1 0 [max_drones=2]
end_hub: e 2 0
connection: s-a [max_link_capacity=2]
connection: a-e [max_link_capacity=2]
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 2
    assert len(result.turns[0]) == 2
    assert len(result.turns[1]) == 2


def test_invalid_drone_count_is_rejected() -> None:
    """The mandatory drone count is a strictly positive integer."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 0
start_hub: s 0 0
end_hub: e 1 0
connection: s-e
"""
        )


def test_invalid_zone_type_is_rejected() -> None:
    """Only the four subject-defined zone types are accepted."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
hub: x 1 0 [zone=danger]
end_hub: e 2 0
connection: s-x
connection: x-e
"""
        )


def test_nonpositive_regular_zone_capacity_is_rejected() -> None:
    """Regular-zone max_drones values must be positive integers."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
hub: x 1 0 [max_drones=0]
end_hub: e 2 0
connection: s-x
connection: x-e
"""
        )


def test_nonpositive_link_capacity_is_rejected() -> None:
    """Connection max_link_capacity must be a positive integer."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
end_hub: e 1 0
connection: s-e [max_link_capacity=-1]
"""
        )


def test_malformed_metadata_is_rejected() -> None:
    """Metadata tokens must use key=value syntax inside one bracket block."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
hub: x 1 0 [zone=normal color]
end_hub: e 2 0
connection: s-x
connection: x-e
"""
        )


def test_duplicate_start_is_rejected() -> None:
    """Exactly one start_hub is allowed."""
    with pytest.raises(ParseError):
        parse_text(
            """
nb_drones: 1
start_hub: s 0 0
start_hub: other 1 0
end_hub: e 2 0
connection: s-e
"""
        )


def test_direct_high_capacity_connection_finishes_in_one_turn() -> None:
    """Link capacity can allow the whole fleet to move simultaneously."""
    parsed = parse_text(
        """
nb_drones: 100
start_hub: s 0 0
end_hub: e 1 0
connection: s-e [max_link_capacity=100]
"""
    )
    result = Simulator(parsed.graph, parsed.drone_count).run()
    assert result.total_turns == 1
    assert len(result.turns[0]) == 100


def test_every_drone_is_printed_at_end_exactly_once() -> None:
    """Delivered drones never move or print another end event later."""
    parsed_25 = MapParser().parse_lines(
        ["nb_drones: 25\n"]
        + (ROOT / "example.map").read_text().splitlines(keepends=True)[1:]
    )

    end = parsed_25.graph.end
    assert end is not None

    result = Simulator(
        parsed_25.graph,
        parsed_25.drone_count,
    ).run()

    counts = {drone_id: 0 for drone_id in range(1, 26)}

    for line in result.plain_lines():
        for token in line.split():
            if token.endswith(f"-{end.name}"):
                drone_id = int(
                    token.split("-", 1)[0][1:]
                )
                counts[drone_id] += 1

    assert all(count == 1 for count in counts.values())
