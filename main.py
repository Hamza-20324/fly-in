from __future__ import annotations

import argparse
import sys
from pathlib import Path

from errors import FlyInError
from parser import MapParser
from simulator import Simulator
from visualizer import TerminalVisualizer


class FlyInApplication:
    """Coordinate parsing, optimization, simulation, and display."""

    def run(self, argv: list[str] | None = None) -> int:
        """Run the CLI and return a process status code."""
        arguments = self._arguments(argv)
        try:
            parsed = MapParser().parse(arguments.map_file)
            result = Simulator(parsed.graph, parsed.drone_count).run(
                max_turns=arguments.max_turns
            )
        except (FlyInError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if arguments.visual:
            print(TerminalVisualizer(parsed.graph).render(result))
        else:
            for line in result.plain_lines():
                print(line)
        if arguments.stats:
            print(
                f"turns={result.total_turns} drones={parsed.drone_count}",
                file=sys.stderr,
            )
        return 0

    @staticmethod
    def _arguments(argv: list[str] | None) -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Route drones through a capacitated zone network."
        )
        parser.add_argument("map_file", type=Path, help="Fly-in map file")
        parser.add_argument(
            "--visual",
            action="store_true",
            help="show colored turn-by-turn zone state",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="print total turn count to stderr",
        )
        parser.add_argument(
            "--max-turns",
            type=int,
            default=None,
            help="optional upper bound for schedule search",
        )
        return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(FlyInApplication().run())
