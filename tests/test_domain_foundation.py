"""Tests for direct shooting inputs and the injected D6 port."""

from __future__ import annotations

import pytest

from src.fow_combat.domain import (
    DieRoller,
    FirepowerTarget,
    OtherSaveTarget,
    SaveProcedure,
    SaveSituation,
    ShootingConditions,
    ShootingSituation,
    TargetSituation,
    ToHitTarget,
)


class QueuedDieRoller:
    """Test-only deterministic DieRoller backed by an explicit queue."""

    def __init__(self, rolls: list[int]):
        self._rolls = list(rolls)

    def roll_d6(self) -> int:
        if not self._rolls:
            raise AssertionError("no queued D6 result remains")
        roll = self._rolls.pop(0)
        if not 1 <= roll <= 6:
            raise AssertionError(f"queued result is not a D6 value: {roll}")
        return roll


@pytest.mark.parametrize("target", list(ToHitTarget))
def test_to_hit_target_is_typed_and_has_label(target):
    assert target.label == f"{int(target)}+"


def test_unresolved_one_plus_is_not_a_domain_target():
    with pytest.raises(ValueError):
        ToHitTarget(1)


@pytest.mark.parametrize("target", list(FirepowerTarget))
def test_firepower_target_represents_d6_threshold(target):
    assert target.label == f"{int(target)}+"


def test_direct_situation_inputs_need_no_weapon_or_unit_identity():
    situation = ShootingSituation(
        shots=18,
        firepower=FirepowerTarget.SIX_PLUS,
        to_hit=ToHitTarget.FOUR_PLUS,
    )

    assert situation.shots == 18
    assert situation.firepower is FirepowerTarget.SIX_PLUS
    assert not hasattr(situation, "weapon")
    assert not hasattr(situation, "unit")


def test_situation_carries_conditions_target_size_and_explicit_save_facts():
    conditions = ShootingConditions(
        long_range=True,
        concealed=True,
        dug_in=True,
        gone_to_ground=True,
        shooter_out_of_command=True,
        shooting_through_smoke=True,
        at_night=True,
    )
    target = TargetSituation(team_count=12, bulletproof_cover=True)
    save = SaveSituation(
        procedure=SaveProcedure.OTHER,
        other_save_target=OtherSaveTarget.INFANTRY,
    )
    situation = ShootingSituation(
        18,
        FirepowerTarget.SIX_PLUS,
        ToHitTarget.FOUR_PLUS,
        conditions,
        target,
        save,
    )

    assert situation.conditions is conditions
    assert situation.target.team_count == 12
    assert situation.target.bulletproof_cover
    assert situation.save.procedure is SaveProcedure.OTHER
    assert situation.save.other_save_target is OtherSaveTarget.INFANTRY


def test_armour_save_facts_can_be_entered_explicitly():
    save = SaveSituation(procedure=SaveProcedure.ARMOUR, armour_rating=3, anti_tank=6)

    assert save.procedure is SaveProcedure.ARMOUR
    assert save.armour_rating == 3
    assert save.anti_tank == 6


def test_dug_in_and_concealed_are_retained_as_separate_facts():
    situation = ShootingSituation(
        1,
        FirepowerTarget.ONE_PLUS,
        ToHitTarget.SIX_PLUS,
        ShootingConditions(dug_in=True, concealed=False),
    )

    assert situation.conditions.dug_in
    assert not situation.conditions.concealed


def test_queued_die_roller_conforms_to_injected_port_and_is_deterministic():
    roller: DieRoller = QueuedDieRoller([6, 1, 4])

    assert [roller.roll_d6() for _ in range(3)] == [6, 1, 4]
    with pytest.raises(AssertionError, match="no queued"):
        roller.roll_d6()


@pytest.mark.parametrize("invalid", [0, 7])
def test_queued_die_roller_rejects_non_d6_values(invalid):
    roller = QueuedDieRoller([invalid])

    with pytest.raises(AssertionError, match="not a D6"):
        roller.roll_d6()


@pytest.mark.parametrize("shots", [-1, -18])
def test_situation_rejects_negative_direct_shot_count(shots):
    with pytest.raises(ValueError, match="shots must be non-negative"):
        ShootingSituation(shots, FirepowerTarget.SIX_PLUS, ToHitTarget.FOUR_PLUS)


def test_target_situation_rejects_nonpositive_known_team_count():
    with pytest.raises(ValueError, match="team_count must be positive"):
        TargetSituation(team_count=0)


@pytest.mark.parametrize("shots", [1.5, True, "2"])
def test_situation_requires_an_integer_shot_count(shots):
    with pytest.raises(TypeError, match="shots must be an integer"):
        ShootingSituation(shots, FirepowerTarget.SIX_PLUS, ToHitTarget.FOUR_PLUS)


@pytest.mark.parametrize("team_count", [1.5, True, "12"])
def test_target_team_count_requires_an_integer(team_count):
    with pytest.raises(TypeError, match="team_count must be an integer"):
        TargetSituation(team_count=team_count)


def test_target_situation_can_represent_pinning_ineligibility_facts():
    target = TargetSituation(team_count=12, armoured_tank_team=True)

    assert target.team_count >= 12
    assert target.armoured_tank_team


def test_input_requires_typed_firepower_and_to_hit_facts():
    with pytest.raises(TypeError, match="firepower must be a FirepowerTarget"):
        ShootingSituation(1, "5+", ToHitTarget.FOUR_PLUS)
    with pytest.raises(TypeError, match="to_hit must be a ToHitTarget"):
        ShootingSituation(1, FirepowerTarget.FIVE_PLUS, "4+")
