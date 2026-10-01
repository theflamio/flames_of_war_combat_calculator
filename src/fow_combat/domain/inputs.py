"""Direct facts describing one user-known shooting situation.

These structures only carry entered facts. They do not derive rule effects,
choose missing save procedures, allocate hits, or resolve outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .firepower import FirepowerTarget
from .to_hit import ToHitTarget


class SaveProcedure(Enum):
    """Save branch explicitly supplied by the user, if known."""

    ARMOUR = "armour"
    OTHER = "other"


class OtherSaveTarget(Enum):
    """Target categories with Other Save values in the accepted V4 audit."""

    INFANTRY = "infantry"
    HEAVY_WEAPONS = "heavy_weapons"
    CAVALRY = "cavalry"
    UNARMOURED_TANK = "unarmoured_tank"
    UNARMOURED_TANK_GUN_SHIELD = "unarmoured_tank_gun_shield"
    RECCE_UNARMOURED_TANK = "recce_unarmoured_tank"
    AIRCRAFT = "aircraft"


@dataclass(frozen=True)
class ShootingConditions:
    """Entered situation flags; no flag is translated into a modifier here.

    ``long_range`` means the verified over-16in/40cm condition. ``dug_in``
    remains independent from ``concealed`` and ``gone_to_ground``.
    """

    long_range: bool = False
    concealed: bool = False
    dug_in: bool = False
    gone_to_ground: bool = False
    shooter_out_of_command: bool = False
    shooting_through_smoke: bool = False
    at_night: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class TargetSituation:
    """Target facts needed to describe eligibility and save context.

    Team count is the user-entered count for the relevant target Unit. The
    optional/exact facts avoid requiring a Unit identity or catalog lookup.
    """

    team_count: int | None = None
    armoured_tank_team: bool = False
    aircraft: bool = False
    bulletproof_cover: bool = False

    def __post_init__(self) -> None:
        if self.team_count is not None:
            if isinstance(self.team_count, bool) or not isinstance(self.team_count, int):
                raise TypeError("team_count must be an integer when provided")
            if self.team_count < 1:
                raise ValueError("team_count must be positive when provided")
        for name in ("armoured_tank_team", "aircraft", "bulletproof_cover"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class SaveSituation:
    """Explicit save facts; absent fields remain unknown rather than inferred."""

    procedure: SaveProcedure | None = None
    other_save_target: OtherSaveTarget | None = None
    armour_rating: int | None = None
    anti_tank: int | None = None
    gun_shield: bool = False
    recce: bool = False

    def __post_init__(self) -> None:
        if self.procedure is not None and not isinstance(self.procedure, SaveProcedure):
            raise TypeError("procedure must be a SaveProcedure when provided")
        if self.other_save_target is not None and not isinstance(
            self.other_save_target, OtherSaveTarget
        ):
            raise TypeError("other_save_target must be an OtherSaveTarget when provided")
        for name in ("armour_rating", "anti_tank"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise TypeError(f"{name} must be an integer when provided")
        for name in ("gun_shield", "recce"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class ShootingSituation:
    """V1 input facts supplied directly by the user for a shooting situation.

    No weapon or Unit identity is required, and no shots are derived from
    models or ROF. The unresolved rules needed to turn these facts into V4
    probability outputs are deliberately outside this input data contract.
    """

    shots: int
    firepower: FirepowerTarget
    to_hit: ToHitTarget
    conditions: ShootingConditions = ShootingConditions()
    target: TargetSituation = TargetSituation()
    save: SaveSituation = SaveSituation()

    def __post_init__(self) -> None:
        if isinstance(self.shots, bool) or not isinstance(self.shots, int):
            raise TypeError("shots must be an integer")
        if self.shots < 0:
            raise ValueError("shots must be non-negative")
        if not isinstance(self.firepower, FirepowerTarget):
            raise TypeError("firepower must be a FirepowerTarget")
        if not isinstance(self.to_hit, ToHitTarget):
            raise TypeError("to_hit must be a ToHitTarget")
        if not isinstance(self.conditions, ShootingConditions):
            raise TypeError("conditions must be ShootingConditions")
        if not isinstance(self.target, TargetSituation):
            raise TypeError("target must be TargetSituation")
        if not isinstance(self.save, SaveSituation):
            raise TypeError("save must be SaveSituation")
