"""Exact V4 artillery probability transitions for Infantry Units.

The domain models each Team under the template, carries Unit morale and pinning
state through a bounded sequence of bombardments, and applies verified
between-turn Rally, Last Stand, and Formation Last Stand probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from itertools import product
from typing import Protocol


class ShootingNation(str, Enum):
    """Nations with explicit artillery policies in the current rules registry."""

    UNITED_STATES = "United States"
    UNITED_KINGDOM = "United Kingdom"
    JAPAN = "Japan"


class RangeIn(str, Enum):
    """How the first bombardment in a scenario was ranged in."""

    FIRST = "First attempt"
    SECOND = "Second attempt"
    THIRD = "Third attempt"
    REPEAT = "Repeat Bombardment"


class ArtilleryRule(str, Enum):
    """Explicit Unit rules supported by artillery policies."""

    TIME_ON_TARGET = "time_on_target"
    FIRE_BURSTS = "fire_bursts"
    BANNERS = "banners"


@dataclass(frozen=True)
class ArtilleryRuleOption:
    """One selectable special rule that the Unit's card confirms it has."""

    identifier: ArtilleryRule
    label: str


@dataclass(frozen=True)
class ArtilleryCommand:
    """Resolved artillery facts and target Unit roster for an exact scenario."""

    shooting_nation: ShootingNation
    infantry_teams_under_template: int
    in_command_teams_under_template: int
    infantry_teams_outside_template: int
    in_command_infantry_outside_template: int
    gun_teams_in_unit: int
    in_command_gun_teams: int
    unit_initial_infantry_and_gun_teams: int
    guns_firing: int
    artillery_to_hit: int
    firepower: int
    horizon: int
    dug_in: bool
    range_in: RangeIn
    repeat_spotter_can_see_aiming_point: bool = True
    infantry_save: int = 3
    unit_has_prior_casualty_or_bailed_team: bool = False
    unit_leader_present: bool = True
    unit_leader_under_template: bool = False
    unit_leader_in_command: bool = True
    last_stand_rating: int = 4
    rally_rating: int = 4
    command_leadership_applies: bool = False
    part_of_formation: bool = False
    other_extant_formation_units: int = 0
    assume_battery_remains_eligible: bool = True
    selected_rules: frozenset[ArtilleryRule] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.shooting_nation, ShootingNation):
            raise TypeError("shooting_nation must be a supported ShootingNation")
        if not isinstance(self.range_in, RangeIn):
            raise TypeError("range_in must be a RangeIn")
        if self.range_in is RangeIn.REPEAT:
            raise ValueError("A scenario starts with an initial Range In attempt; only Shooting #2+ are Repeat Bombardments")
        nonnegative = (
            "in_command_teams_under_template",
            "infantry_teams_outside_template",
            "in_command_infantry_outside_template",
            "gun_teams_in_unit",
            "in_command_gun_teams",
            "other_extant_formation_units",
        )
        positive = (
            "infantry_teams_under_template",
            "unit_initial_infantry_and_gun_teams",
            "guns_firing",
            "horizon",
        )
        for name in nonnegative + positive:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < (1 if name in positive else 0):
                raise ValueError(f"{name} must be an integer >= {1 if name in positive else 0}")
        for name in (
            "dug_in",
            "repeat_spotter_can_see_aiming_point",
            "unit_has_prior_casualty_or_bailed_team",
            "unit_leader_present",
            "unit_leader_under_template",
            "unit_leader_in_command",
            "command_leadership_applies",
            "part_of_formation",
            "assume_battery_remains_eligible",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.in_command_teams_under_template > self.infantry_teams_under_template:
            raise ValueError("in-command covered Infantry Teams cannot exceed covered Teams")
        if self.in_command_infantry_outside_template > self.infantry_teams_outside_template:
            raise ValueError("in-command uncovered Infantry Teams cannot exceed uncovered Teams")
        if self.in_command_gun_teams > self.gun_teams_in_unit:
            raise ValueError("in-command Gun Teams cannot exceed Gun Teams")
        current_count = (
            self.infantry_teams_under_template
            + self.infantry_teams_outside_template
            + self.gun_teams_in_unit
        )
        if self.unit_initial_infantry_and_gun_teams < current_count:
            raise ValueError("initial Unit Infantry/Gun Team count cannot be below the current roster")
        if (
            self.unit_initial_infantry_and_gun_teams > current_count
            and not self.unit_has_prior_casualty_or_bailed_team
            and self.unit_leader_present
        ):
            raise ValueError("a smaller current roster than the initial roster requires prior loss/bailed state")
        if self.artillery_to_hit not in range(2, 7):
            raise ValueError("Artillery To Hit base must be from 2+ through 6+")
        if self.firepower not in range(1, 7):
            raise ValueError("Firepower must be from 1+ through 6+")
        if self.infantry_save != 3:
            raise ValueError("V4 Infantry Other Save is 3+; other save values are unsupported for Infantry")
        for name in ("last_stand_rating", "rally_rating"):
            rating = getattr(self, name)
            if isinstance(rating, bool) or not isinstance(rating, int) or rating not in range(2, 7):
                raise ValueError(f"{name} must be from 2+ through 6+")
        if self.unit_leader_under_template and not self.unit_leader_present:
            raise ValueError("an absent Unit Leader cannot be under the template")
        if self.unit_leader_under_template and self.unit_leader_in_command and self.in_command_teams_under_template < 1:
            raise ValueError("an in-command covered Unit Leader must be included in that count")
        if self.unit_leader_under_template and not self.unit_leader_in_command and self.in_command_teams_under_template == self.infantry_teams_under_template:
            raise ValueError("an out-of-command covered Unit Leader requires an out-of-command covered Team")
        if self.unit_leader_present and not self.unit_leader_under_template:
            if self.unit_leader_in_command and self.in_command_infantry_outside_template < 1:
                raise ValueError("an in-command uncovered Unit Leader must be included in that count")
            if not self.unit_leader_in_command and self.in_command_infantry_outside_template == self.infantry_teams_outside_template:
                raise ValueError("an out-of-command uncovered Unit Leader requires an out-of-command Team")
        if not self.part_of_formation and self.other_extant_formation_units:
            raise ValueError("other Formation Unit count only applies when target belongs to a Formation")
        if self.part_of_formation and self.other_extant_formation_units < 1:
            raise ValueError("the initial target Formation must have at least one other eligible extant Unit")
        if self.command_leadership_applies and not self.part_of_formation:
            raise ValueError("Command Leadership requires target Formation membership")
        if not isinstance(self.selected_rules, frozenset) or not all(
            isinstance(rule, ArtilleryRule) for rule in self.selected_rules
        ):
            raise TypeError("selected_rules must be a frozenset of ArtilleryRule identifiers")
        if self.horizon > 1 and not self.assume_battery_remains_eligible:
            raise ValueError("multi-turn scenarios require the user to confirm the battery remains eligible")
        if self.horizon > 1 and ArtilleryRule.TIME_ON_TARGET in self.selected_rules:
            raise ValueError("Time on Target with Repeat Bombardment is unresolved and is not supported")
        if self.range_in is RangeIn.REPEAT and ArtilleryRule.TIME_ON_TARGET in self.selected_rules:
            raise ValueError("Time on Target and Repeat Bombardment interaction is unresolved")


class NationArtilleryRules(Protocol):
    """Policy surface for verified nation/unit artillery special rules."""

    def available_unit_rules(self, range_in: RangeIn) -> tuple[ArtilleryRuleOption, ...]: ...
    def successful_hit_reroll(self, command: ArtilleryCommand, shooting_number: int) -> bool: ...
    def failed_hit_reroll(self, command: ArtilleryCommand) -> bool: ...
    def reroll_successful_saves(self, command: ArtilleryCommand, shooting_number: int) -> bool: ...
    def hits_required_to_pin(self, command: ArtilleryCommand) -> int: ...


@dataclass(frozen=True)
class _CoreNationRules:
    nation: ShootingNation

    def available_unit_rules(self, range_in: RangeIn) -> tuple[ArtilleryRuleOption, ...]:
        if self.nation is ShootingNation.UNITED_STATES and range_in is RangeIn.FIRST:
            return (ArtilleryRuleOption(ArtilleryRule.TIME_ON_TARGET, "This Unit has Time on Target"),)
        if self.nation is ShootingNation.JAPAN:
            return (
                ArtilleryRuleOption(ArtilleryRule.FIRE_BURSTS, "This Unit has Fire Bursts"),
                ArtilleryRuleOption(ArtilleryRule.BANNERS, "This Unit has Banners"),
            )
        return ()

    def successful_hit_reroll(self, command: ArtilleryCommand, shooting_number: int) -> bool:
        if command.guns_firing not in (1, 2):
            return False
        if (
            self.nation is ShootingNation.JAPAN
            and command.guns_firing == 2
            and ArtilleryRule.FIRE_BURSTS in command.selected_rules
        ):
            return False
        return True

    def failed_hit_reroll(self, command: ArtilleryCommand) -> bool:
        return command.guns_firing >= 5

    def reroll_successful_saves(self, command: ArtilleryCommand, shooting_number: int) -> bool:
        if shooting_number > 1:
            return True  # Repeat Bombardment.
        return (
            self.nation is ShootingNation.UNITED_STATES
            and ArtilleryRule.TIME_ON_TARGET in command.selected_rules
            and command.range_in is RangeIn.FIRST
        )

    def hits_required_to_pin(self, command: ArtilleryCommand) -> int:
        return 2 if self.nation is ShootingNation.JAPAN and ArtilleryRule.BANNERS in command.selected_rules else 1


class ArtilleryRulesRegistry:
    """Registry limited to nations with explicit V1 policy implementations."""

    def __init__(self) -> None:
        self._rules: dict[ShootingNation, NationArtilleryRules] = {
            nation: _CoreNationRules(nation) for nation in ShootingNation
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
class _State:
    covered_in_command: int
    covered_out_of_command: int
    leader_alive: bool
    pinned: bool
    has_prior_losses: bool
    unit_destroyed: bool = False
    formation_destroyed: bool = False


@dataclass(frozen=True)
class ShootingResult:
    """Exact probability summary after one bombardment in the horizon."""

    shooting_number: int
    expected_teams_remaining: float
    bad_spirit_probability: float
    destroyed_probability: float
    formation_destroyed_probability: float | None
    pinned_probability: float
    team_count_distribution: tuple[tuple[int, float], ...]
    resolved_to_hit: int


@dataclass(frozen=True)
class ArtilleryResult:
    """The exact state-distribution summaries for each bombardment."""

    shooting_nation: ShootingNation
    firepower_profile: int
    adjusted_firepower: int
    shootings: tuple[ShootingResult, ...]
    used_rule_branches: tuple[str, ...]
    incomplete_items: tuple[str, ...]


def _adjust_firepower(profile: int) -> int:
    return {1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 6: 4}[profile]


def _resolved_to_hit(command: ArtilleryCommand, shooting_number: int) -> int:
    attempt_modifier = {
        RangeIn.FIRST: 0,
        RangeIn.SECOND: 1,
        RangeIn.THIRD: 2,
        RangeIn.REPEAT: 0 if command.repeat_spotter_can_see_aiming_point else 1,
    }[command.range_in]
    if shooting_number > 1:
        attempt_modifier = 0 if command.repeat_spotter_can_see_aiming_point else 1
    target = command.artillery_to_hit + attempt_modifier
    if target > 8:
        raise ValueError("Resolved Artillery To Hit above 8+ is unresolved and unsupported")
    return target


def _success_probability(target: int) -> float:
    if target <= 6:
        return (7 - target) / 6
    if target == 7:
        return 1 / 18
    if target == 8:
        return 1 / 36
    raise ValueError("Only To Hit thresholds through 8+ are supported")


def _hit_probability(command: ArtilleryCommand, rules: NationArtilleryRules, shooting_number: int) -> float:
    p = _success_probability(_resolved_to_hit(command, shooting_number))
    if rules.successful_hit_reroll(command, shooting_number):
        return p * p
    if rules.failed_hit_reroll(command):
        return 1 - (1 - p) ** 2
    return p


def _team_survival_probability(
    command: ArtilleryCommand, rules: NationArtilleryRules, shooting_number: int
) -> float:
    save_success = 4 / 6  # Verified Infantry Other Save 3+.
    # A successful save is re-rolled after a Repeat or eligible Time on Target.
    # The unresolved overlap is rejected in ArtilleryCommand validation.
    if rules.reroll_successful_saves(command, shooting_number):
        save_success *= 4 / 6
    save_failure = 1 - save_success
    if not command.dug_in:
        return save_success
    fp_success = (7 - _adjust_firepower(command.firepower)) / 6
    return save_success + save_failure * (1 - fp_success)


@lru_cache(maxsize=None)
def _group_transition(
    count: int, *, p_hit: float, p_survive_if_hit: float, hit_cap: int
) -> tuple[tuple[tuple[int, int], float], ...]:
    """Return probabilities for (survivors, hits capped at pin threshold)."""
    states: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for _ in range(count):
        next_states: dict[tuple[int, int], float] = {}
        outcomes = (
            (1, 0, 1 - p_hit),
            (1, 1, p_hit * p_survive_if_hit),
            (0, 1, p_hit * (1 - p_survive_if_hit)),
        )
        for (survivors, hits), state_p in states.items():
            for survival_delta, hit_delta, outcome_p in outcomes:
                key = (survivors + survival_delta, min(hit_cap, hits + hit_delta))
                next_states[key] = next_states.get(key, 0.0) + state_p * outcome_p
        states = next_states
    return tuple(states.items())


def _team_count(command: ArtilleryCommand, state: _State) -> int:
    return (
        state.covered_in_command
        + state.covered_out_of_command
        + command.infantry_teams_outside_template
        + command.gun_teams_in_unit
    )


def _in_command_infantry(command: ArtilleryCommand, state: _State) -> int:
    return state.covered_in_command + command.in_command_infantry_outside_template


def _in_command_guns(command: ArtilleryCommand) -> int:
    return command.in_command_gun_teams


def _unit_in_good_spirits(command: ArtilleryCommand, state: _State) -> bool:
    if state.unit_destroyed or _team_count(command, state) == 0:
        return False
    if not state.has_prior_losses:
        return True
    if not state.leader_alive:
        return False
    infantry_required = 5 if command.unit_initial_infantry_and_gun_teams >= 16 else 3
    return _in_command_infantry(command, state) >= infantry_required or _in_command_guns(command) >= 2


def _merge_add(mapping: dict[_State, float], state: _State, probability: float) -> None:
    if probability:
        mapping[state] = mapping.get(state, 0.0) + probability


def _resolve_bombardment(
    distribution: dict[_State, float],
    command: ArtilleryCommand,
    rules: NationArtilleryRules,
    shooting_number: int,
) -> dict[_State, float]:
    hit_cap = rules.hits_required_to_pin(command)
    p_hit = _hit_probability(command, rules, shooting_number)
    p_survive = _team_survival_probability(command, rules, shooting_number)
    transitioned: dict[_State, float] = {}
    for state, state_probability in distribution.items():
        if state.unit_destroyed or state.formation_destroyed:
            _merge_add(transitioned, state, state_probability)
            continue

        groups: list[tuple[str, tuple[tuple[tuple[int, int], float], ...]]] = []
        covered_ic = state.covered_in_command
        covered_ooc = state.covered_out_of_command
        leader_is_covered = command.unit_leader_under_template and state.leader_alive
        if leader_is_covered:
            if command.unit_leader_in_command:
                covered_ic -= 1
            else:
                covered_ooc -= 1
        groups.append(("ic", _group_transition(covered_ic, p_hit=p_hit, p_survive_if_hit=p_survive, hit_cap=hit_cap)))
        groups.append(("ooc", _group_transition(covered_ooc, p_hit=p_hit, p_survive_if_hit=p_survive, hit_cap=hit_cap)))
        if leader_is_covered:
            groups.append(("leader", _group_transition(1, p_hit=p_hit, p_survive_if_hit=p_survive, hit_cap=hit_cap)))
        for combinations in product(*(group for _, group in groups)):
            probability = state_probability
            survivors_ic = 0
            survivors_ooc = 0
            leader_alive = state.leader_alive
            hit_count = 0
            for (group_name, _), ((survivors, hits), group_p) in zip(groups, combinations):
                probability *= group_p
                hit_count = min(hit_cap, hit_count + hits)
                if group_name == "ic":
                    survivors_ic = survivors
                elif group_name == "ooc":
                    survivors_ooc = survivors
                else:
                    leader_alive = bool(survivors)
            if leader_is_covered:
                if command.unit_leader_in_command:
                    survivors_ic += int(leader_alive)
                else:
                    survivors_ooc += int(leader_alive)
            remaining = survivors_ic + survivors_ooc + command.infantry_teams_outside_template + command.gun_teams_in_unit
            killed = survivors_ic < state.covered_in_command or survivors_ooc < state.covered_out_of_command
            zero_teams = remaining == 0
            pinned = state.pinned or hit_count >= hit_cap
            next_state = _State(
                covered_in_command=survivors_ic,
                covered_out_of_command=survivors_ooc,
                leader_alive=leader_alive,
                pinned=pinned,
                has_prior_losses=state.has_prior_losses or killed,
                unit_destroyed=state.unit_destroyed or zero_teams,
                formation_destroyed=state.formation_destroyed,
            )
            _merge_add(transitioned, next_state, probability)
    return transitioned


def _rally_probability(command: ArtilleryCommand, state: _State) -> float:
    if not state.pinned or state.unit_destroyed:
        return 1.0
    p = (7 - command.rally_rating) / 6
    if command.command_leadership_applies and state.leader_alive:
        p = 1 - (1 - p) ** 2
    return p


def _resolve_starting_step(distribution: dict[_State, float], command: ArtilleryCommand) -> dict[_State, float]:
    after_step: dict[_State, float] = {}
    for state, probability in distribution.items():
        if state.formation_destroyed:
            _merge_add(after_step, state, probability)
            continue
        if state.unit_destroyed:
            formation_destroyed = command.part_of_formation and command.other_extant_formation_units < 2
            _merge_add(
                after_step,
                _State(
                    state.covered_in_command,
                    state.covered_out_of_command,
                    state.leader_alive,
                    state.pinned,
                    state.has_prior_losses,
                    True,
                    formation_destroyed,
                ),
                probability,
            )
            continue
        p_rally = _rally_probability(command, state)
        rally_states = ((False, 1 - p_rally), (True, p_rally)) if state.pinned else ((False, 1.0),)
        for rallied, rally_p in rally_states:
            rallied_state = _State(
                state.covered_in_command,
                state.covered_out_of_command,
                state.leader_alive,
                False if rallied else state.pinned,
                state.has_prior_losses,
                state.unit_destroyed,
                state.formation_destroyed,
            )
            if _team_count(command, rallied_state) == 0:
                formation_destroyed = command.part_of_formation and command.other_extant_formation_units < 2
                _merge_add(
                    after_step,
                    _State(
                        rallied_state.covered_in_command,
                        rallied_state.covered_out_of_command,
                        rallied_state.leader_alive,
                        rallied_state.pinned,
                        rallied_state.has_prior_losses,
                        True,
                        formation_destroyed,
                    ),
                    probability * rally_p,
                )
                continue
            if _unit_in_good_spirits(command, rallied_state):
                morale_outcomes = ((True, 1.0),)
            else:
                p_last_stand = (7 - command.last_stand_rating) / 6
                if command.command_leadership_applies and rallied_state.leader_alive:
                    p_last_stand = 1 - (1 - p_last_stand) ** 2
                morale_outcomes = ((True, p_last_stand), (False, 1 - p_last_stand))
            for survived_last_stand, morale_p in morale_outcomes:
                destroyed = not survived_last_stand
                formation_destroyed = False
                if command.part_of_formation:
                    extant_after_target = command.other_extant_formation_units + int(not destroyed)
                    if extant_after_target < 2:
                        formation_destroyed = True
                        destroyed = True
                final_state = _State(
                    rallied_state.covered_in_command,
                    rallied_state.covered_out_of_command,
                    rallied_state.leader_alive,
                    rallied_state.pinned,
                    rallied_state.has_prior_losses,
                    rallied_state.unit_destroyed or destroyed,
                    rallied_state.formation_destroyed or formation_destroyed,
                )
                _merge_add(after_step, final_state, probability * rally_p * morale_p)
    return after_step


def _summarize(
    distribution: dict[_State, float], command: ArtilleryCommand, shooting_number: int, resolved_to_hit: int
) -> ShootingResult:
    count_distribution: dict[int, float] = {}
    expected = bad_spirit = destroyed = formation = pinned = 0.0
    for state, probability in distribution.items():
        remaining = 0 if state.unit_destroyed or state.formation_destroyed else _team_count(command, state)
        count_distribution[remaining] = count_distribution.get(remaining, 0.0) + probability
        expected += remaining * probability
        destroyed += probability * state.unit_destroyed
        formation += probability * state.formation_destroyed
        pinned += probability * state.pinned * (not state.unit_destroyed)
        if not state.unit_destroyed and not state.formation_destroyed and not _unit_in_good_spirits(command, state):
            bad_spirit += probability
    return ShootingResult(
        shooting_number=shooting_number,
        expected_teams_remaining=expected,
        bad_spirit_probability=bad_spirit,
        destroyed_probability=destroyed,
        formation_destroyed_probability=formation if command.part_of_formation else None,
        pinned_probability=pinned,
        team_count_distribution=tuple(sorted(count_distribution.items())),
        resolved_to_hit=resolved_to_hit,
    )


def calculate_artillery(
    command: ArtilleryCommand,
    *,
    rules_registry: ArtilleryRulesRegistry,
) -> ArtilleryResult:
    """Calculate exact distributions across the initial volley and repeats."""
    rules = rules_registry.for_nation(command.shooting_nation)
    allowed = {option.identifier for option in rules.available_unit_rules(command.range_in)}
    if not command.selected_rules.issubset(allowed):
        raise ValueError("A selected Unit rule is not available for this nation and initial Range In")
    if command.unit_leader_under_template and command.infantry_teams_under_template < 1:
        raise ValueError("Unit Leader under-template input requires a covered Infantry Team")

    leader_covered_ic = int(command.unit_leader_present and command.unit_leader_under_template and command.unit_leader_in_command)
    leader_covered_ooc = int(command.unit_leader_present and command.unit_leader_under_template and not command.unit_leader_in_command)
    state = _State(
        covered_in_command=command.in_command_teams_under_template,
        covered_out_of_command=command.infantry_teams_under_template - command.in_command_teams_under_template,
        leader_alive=command.unit_leader_present,
        pinned=False,
        has_prior_losses=(
            command.unit_has_prior_casualty_or_bailed_team or not command.unit_leader_present
        ),
    )
    # Current covered totals already include a present leader; the transition
    # splits the leader from regular Teams while preserving the total counts.
    if leader_covered_ic and state.covered_in_command < 1:
        raise ValueError("Covered in-command Unit Leader is not included in the covered count")
    if leader_covered_ooc and state.covered_out_of_command < 1:
        raise ValueError("Covered out-of-command Unit Leader is not included in the covered count")
    distribution: dict[_State, float] = {state: 1.0}
    rows: list[ShootingResult] = []
    for shooting_number in range(1, command.horizon + 1):
        distribution = _resolve_bombardment(distribution, command, rules, shooting_number)
        rows.append(_summarize(distribution, command, shooting_number, _resolved_to_hit(command, shooting_number)))
        if shooting_number < command.horizon:
            distribution = _resolve_starting_step(distribution, command)

    branches = [
        "Exact per-Team artillery To Hit and casualty transitions",
        "Verified Infantry Other Save 3+",
        "Unit pinning and Rally are carried through Starting Steps",
        "Unit Last Stand and applicable Command Leadership rerolls",
    ]
    if command.dug_in:
        branches.append("Dug In means user-confirmed Foxholes/Bulletproof Cover; adjusted Firepower after failed save")
    if ArtilleryRule.TIME_ON_TARGET in command.selected_rules:
        branches.append("Declared US Unit has Time on Target on the initial first-attempt Range In")
    if ArtilleryRule.FIRE_BURSTS in command.selected_rules:
        branches.append("Declared Japanese Unit has Fire Bursts")
    if ArtilleryRule.BANNERS in command.selected_rules:
        branches.append("Declared Japanese Unit has Banners; two bombardment hits pin")
    if command.part_of_formation:
        branches.append("Formation Last Stand uses user-entered other extant Unit count")
    return ArtilleryResult(
        shooting_nation=command.shooting_nation,
        firepower_profile=command.firepower,
        adjusted_firepower=_adjust_firepower(command.firepower),
        shootings=tuple(rows),
        used_rule_branches=tuple(branches),
        incomplete_items=(
            "Other nation-specific rules and weapon exceptions are outside the supported V1 policy inventory.",
            "The firing battery is assumed eligible for every selected repeat once confirmed by the user.",
            "The target roster and In Command flags are held fixed except for artillery casualties; update them for movement between turns.",
        ),
    )
