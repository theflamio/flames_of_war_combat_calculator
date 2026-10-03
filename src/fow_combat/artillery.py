"""V4 single-bombardment resolution against Infantry Teams."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .domain.dice import DieRoller


class ShootingNation(str, Enum):
    UNITED_STATES = "United States"
    UNITED_KINGDOM = "United Kingdom"
    JAPAN = "Japan"
    OTHER = "Other / unsupported nation rules"


class RangeIn(str, Enum):
    FIRST = "First attempt"
    SECOND = "Second attempt"
    THIRD = "Third attempt"
    REPEAT = "Repeat Bombardment"


class ArtilleryRule(str, Enum):
    TIME_ON_TARGET = "time_on_target"
    FIRE_BURSTS = "fire_bursts"
    BANNERS = "banners"


@dataclass(frozen=True)
class ArtilleryRuleOption:
    identifier: ArtilleryRule
    label: str


@dataclass(frozen=True)
class ArtilleryCommand:
    shooting_nation: ShootingNation
    infantry_teams_under_template: int
    guns_firing: int
    artillery_to_hit: int
    firepower: int
    range_in: RangeIn
    teams_under_template_same_unit: bool = False
    repeat_spotter_can_see_aiming_point: bool = True
    selected_rules: frozenset[ArtilleryRule] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.shooting_nation, ShootingNation):
            raise TypeError("shooting_nation must be a ShootingNation")
        if not isinstance(self.range_in, RangeIn):
            raise TypeError("range_in must be a RangeIn")
        for name in ("infantry_teams_under_template", "guns_firing"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if isinstance(self.artillery_to_hit, bool) or self.artillery_to_hit not in range(2, 7):
            raise ValueError("Artillery To Hit must be from 2+ through 6+")
        if isinstance(self.firepower, bool) or self.firepower not in range(1, 7):
            raise ValueError("Firepower must be from 1+ through 6+")
        for name in ("teams_under_template_same_unit", "repeat_spotter_can_see_aiming_point"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if not isinstance(self.selected_rules, frozenset) or not all(
            isinstance(rule, ArtilleryRule) for rule in self.selected_rules
        ):
            raise TypeError("selected_rules must be a frozenset of ArtilleryRule identifiers")
        if self.range_in is not RangeIn.REPEAT and not self.repeat_spotter_can_see_aiming_point:
            raise ValueError("spotter visibility is only applicable to a Repeat Bombardment")


class NationArtilleryRules(Protocol):
    def available_unit_rules(self, range_in: RangeIn) -> tuple[ArtilleryRuleOption, ...]: ...
    def reroll_successful_to_hit(self, command: ArtilleryCommand) -> bool: ...
    def reroll_failed_to_hit(self, command: ArtilleryCommand) -> bool: ...
    def reroll_successful_saves(self, command: ArtilleryCommand) -> bool: ...
    def first_hit_does_not_count_for_pinning(self, command: ArtilleryCommand) -> bool: ...


@dataclass(frozen=True)
class _CoreNationRules:
    nation: ShootingNation

    def available_unit_rules(self, range_in: RangeIn) -> tuple[ArtilleryRuleOption, ...]:
        if self.nation is ShootingNation.UNITED_STATES:
            if range_in is RangeIn.FIRST:
                return (ArtilleryRuleOption(ArtilleryRule.TIME_ON_TARGET, "This Unit has Time on Target"),)
            return ()
        if self.nation is ShootingNation.JAPAN:
            return (
                ArtilleryRuleOption(ArtilleryRule.FIRE_BURSTS, "This Unit has Fire Bursts"),
                ArtilleryRuleOption(ArtilleryRule.BANNERS, "This Unit has Banners"),
            )
        return ()

    def reroll_successful_to_hit(self, command: ArtilleryCommand) -> bool:
        return not (
            self.nation is ShootingNation.JAPAN
            and ArtilleryRule.FIRE_BURSTS in command.selected_rules
            and command.guns_firing == 2
        ) and command.guns_firing <= 2

    def reroll_failed_to_hit(self, command: ArtilleryCommand) -> bool:
        return command.guns_firing >= 5

    def reroll_successful_saves(self, command: ArtilleryCommand) -> bool:
        return command.range_in is RangeIn.REPEAT or (
            self.nation is ShootingNation.UNITED_STATES
            and ArtilleryRule.TIME_ON_TARGET in command.selected_rules
            and command.range_in is RangeIn.FIRST
        )

    def first_hit_does_not_count_for_pinning(self, command: ArtilleryCommand) -> bool:
        return self.nation is ShootingNation.JAPAN and ArtilleryRule.BANNERS in command.selected_rules


class ArtilleryRulesRegistry:
    """Small explicit nation policy registry for supported V1 nations."""

    def __init__(self) -> None:
        self._rules: dict[ShootingNation, NationArtilleryRules] = {
            nation: _CoreNationRules(nation)
            for nation in (ShootingNation.UNITED_STATES, ShootingNation.UNITED_KINGDOM, ShootingNation.JAPAN)
        }

    def for_nation(self, nation: ShootingNation) -> NationArtilleryRules:
        try:
            return self._rules[nation]
        except KeyError as exc:
            raise ValueError(f"No artillery rules policy for {nation}") from exc

    def available_unit_rules(
        self, nation: ShootingNation, range_in: RangeIn
    ) -> tuple[ArtilleryRuleOption, ...]:
        return self.for_nation(nation).available_unit_rules(range_in)


@dataclass(frozen=True)
class ArtilleryResult:
    shooting_nation: ShootingNation
    resolved_to_hit: int
    hits_per_trial: tuple[int, ...]
    casualties_per_trial: tuple[int, ...]
    trials: int
    firepower_profile: int
    adjusted_firepower: int
    pin_probability: float | None
    pinning_hit_threshold: int | None
    used_rule_branches: tuple[str, ...]
    incomplete_items: tuple[str, ...]


def _adjust_firepower(profile: int) -> int:
    return {1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 6: 4}[profile]


def _to_hit_target(command: ArtilleryCommand) -> int:
    extra = {
        RangeIn.FIRST: 0,
        RangeIn.SECOND: 1,
        RangeIn.THIRD: 2,
        RangeIn.REPEAT: 0 if command.repeat_spotter_can_see_aiming_point else 1,
    }[command.range_in]
    return command.artillery_to_hit + extra


def calculate_artillery(
    command: ArtilleryCommand,
    *,
    rules_registry: ArtilleryRulesRegistry,
    die_roller: DieRoller,
    trials: int = 10_000,
) -> ArtilleryResult:
    """Sample independent Team hit/save outcomes using the injected D6 port."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer")
    rules = rules_registry.for_nation(command.shooting_nation)
    available_rule_ids = {
        option.identifier
        for option in rules.available_unit_rules(command.range_in)
    }
    if not command.selected_rules.issubset(available_rule_ids):
        raise ValueError("A selected Unit rule is not available for this Shooting Nation and Range In scenario")
    target = _to_hit_target(command)
    if target > 6:
        raise ValueError("This Artillery To Hit threshold is unresolved: V1 does not implement artillery 7+ To Hit dice mechanics.")
    repeat_hit, repeat_miss = rules.reroll_successful_to_hit(command), rules.reroll_failed_to_hit(command)
    reroll_successful_saves = rules.reroll_successful_saves(command)
    pinning_threshold = 2 if rules.first_hit_does_not_count_for_pinning(command) else 1

    def d6() -> int:
        roll = die_roller.roll_d6()
        if isinstance(roll, bool) or not isinstance(roll, int) or roll not in range(1, 7):
            raise ValueError("DieRoller must return an integer from 1 through 6")
        return roll

    def roll_hit() -> bool:
        result = d6() >= target
        if (result and repeat_hit) or (not result and repeat_miss):
            result = d6() >= target
        return result

    def infantry_save_succeeds() -> bool:
        result = d6() >= 3  # Ordinary exposed Infantry Other Save is 3+.
        if result and reroll_successful_saves:
            result = d6() >= 3
        return result

    hits_out: list[int] = []
    casualties_out: list[int] = []
    for _ in range(trials):
        hit_count = sum(roll_hit() for _ in range(command.infantry_teams_under_template))
        casualty_count = sum(not infantry_save_succeeds() for _ in range(hit_count))
        hits_out.append(hit_count)
        casualties_out.append(casualty_count)

    branches = ["V4 artillery To Hit", "number-of-weapons To Hit re-roll", "Infantry Other Save 3+"]
    if command.range_in is RangeIn.REPEAT:
        branches.append("Repeat Bombardment: successful saves re-rolled")
    if ArtilleryRule.TIME_ON_TARGET in command.selected_rules:
        branches.append("Declared US Unit has Time on Target: successful saves re-rolled")
    if ArtilleryRule.FIRE_BURSTS in command.selected_rules:
        branches.append("Declared Japanese Unit has Fire Bursts")
    if ArtilleryRule.BANNERS in command.selected_rules:
        branches.append("Declared Japanese Unit has Banners; first hit does not count toward pinning")
    return ArtilleryResult(
        shooting_nation=command.shooting_nation,
        resolved_to_hit=target,
        hits_per_trial=tuple(hits_out),
        casualties_per_trial=tuple(casualties_out),
        trials=trials,
        firepower_profile=command.firepower,
        adjusted_firepower=_adjust_firepower(command.firepower),
        pin_probability=(
            sum(hit_count >= pinning_threshold for hit_count in hits_out) / trials
            if command.teams_under_template_same_unit
            else None
        ),
        pinning_hit_threshold=pinning_threshold if command.teams_under_template_same_unit else None,
        used_rule_branches=tuple(branches),
        incomplete_items=(
            "Firepower is recorded with its adjusted profile but is not rolled against ordinary exposed Infantry.",
            *(
                ("Pinning probability is unavailable unless the user confirms all Teams under the template belong to one Unit.",)
                if not command.teams_under_template_same_unit
                else ()
            ),
            "Unit/Formation Last Stand and destruction are unavailable without additional Unit and Formation facts.",
            "This result covers ordinary exposed Infantry and does not resolve defensive exceptions such as Bulletproof Cover or weapon rules such as Brutal.",
            "Nation-specific support is not exhaustive. US Time on Target and Japanese Fire Bursts/Banners are explicit Unit-rule choices; UK Mike Target coordination is outside this single-bombardment calculation.",
        ),
    )
