class FlyInError(Exception):
    """Base exception for expected Fly-in errors."""


class ParseError(FlyInError):
    """Raised when an input map does not respect the required syntax."""

    def __init__(self, line: int, message: str) -> None:
        """Build a parsing error with its source line.

        Args:
            line: One-based line number in the input file.
            message: Human-readable explanation of the failure.
        """
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


class NoRouteError(FlyInError):
    """Raised when a valid map has no route from start to end."""


class SimulationError(FlyInError):
    """Raised when no valid schedule can be produced or validated."""
