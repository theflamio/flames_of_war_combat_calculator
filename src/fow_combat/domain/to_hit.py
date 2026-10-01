"""Typed To Hit targets supported by the audited target representation."""

from enum import IntEnum


class ToHitTarget(IntEnum):
    """Typed To Hit target threshold, represented without UI label strings.

    Values 2 through 8 are represented. The rules audit leaves 1+ unresolved,
    so it is intentionally absent. This type does not apply modifiers or
    implement the 7+/8+ resolution procedure.
    """

    TWO_PLUS = 2
    THREE_PLUS = 3
    FOUR_PLUS = 4
    FIVE_PLUS = 5
    SIX_PLUS = 6
    SEVEN_PLUS = 7
    EIGHT_PLUS = 8

    @property
    def label(self) -> str:
        return f"{self.value}+"
