"""Domain-facing random die port."""

from typing import Protocol


class DieRoller(Protocol):
    """Supplies one six-sided die result per call."""

    def roll_d6(self) -> int:
        """Return an integer from 1 through 6, inclusive."""
        ...
