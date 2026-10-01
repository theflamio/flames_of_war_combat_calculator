"""User-entered Firepower threshold, without resolving a Firepower test."""

from enum import IntEnum


class FirepowerTarget(IntEnum):
    """A D6 threshold from 1+ through 6+ supplied for the situation."""

    ONE_PLUS = 1
    TWO_PLUS = 2
    THREE_PLUS = 3
    FOUR_PLUS = 4
    FIVE_PLUS = 5
    SIX_PLUS = 6

    @property
    def label(self) -> str:
        return f"{self.value}+"
