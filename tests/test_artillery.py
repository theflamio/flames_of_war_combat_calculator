"""Exact contract tests for V4 infantry artillery probabilities and state changes.

Expected probabilities are derived from the accepted V4 rules specification:
single-D6 thresholds have (7-T)/6 success faces, hit re-rolls are conditional
re-rolls rather than extra shots, and the exact state transitions multiply
independent per-Team outcomes. Tests deliberately use small rosters so the
resulting distributions can be checked by hand.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from src.fow_combat.artillery import (
    ArtilleryCommand,
    ArtilleryRule,
    ArtilleryRulesRegistry,
    RangeIn,
    ShootingNation,
    calculate_artillery,
)


def command(**overrides) -> ArtilleryCommand:
    """Make a minimal valid unit with six Infantry, one covered, five uncovered."""
    values = dict(
        shooting_nation=ShootingNation.UNITED_KINGDOM,
        infantry_teams_under_template=1,
        in_command_teams_under_template=1,
        infantry_teams_outside_template=5,
        in_command_infantry_outside_template=5,
        gun_teams_in_unit=0,
        in_command_gun_teams=0,
        unit_initial_infantry_and_gun_teams=6,
        guns_firing=3,
        artillery_to_hit=4,
        firepower=5,
        horizon=1,
        dug_in=False,
        range_in=RangeIn.FIRST,
        unit_leader_present=True,
        unit_leader_under_template=False,
        unit_leader_in_command=True,
        last_stand_rating=4,
        rally_rating=4,
    )
    values.update(overrides)
    return ArtilleryCommand(**values)


def calculate(**overrides):
    return calculate_artillery(command(**overrides), rules_registry=ArtilleryRulesRegistry())


def distribution(row) -> dict[int, float]:
    return dict(row.team_count_distribution)


def test_infantry_save_only_accepts_verified_three_plus():
    for unsupported in (4, 5):
        with pytest.raises(ValueError, match=r"Infantry Other Save is 3\+"):
            command(infantry_save=unsupported)


@pytest.mark.parametrize(
    ("profile", "adjusted"),
    [(1, 1), (2, 2), (3, 3), (4, 3), (5, 4), (6, 4)],
)
def test_artillery_firepower_adjustment_table(profile, adjusted):
    result = calculate(firepower=profile)
    assert result.firepower_profile == profile
    assert result.adjusted_firepower == adjusted


def test_not_dug_in_failed_save_kills_without_firepower_gate():
    # 4+ To Hit with 3 guns: 1/2 hit. Ordinary Infantry fails its 3+ save
    # on 1 or 2, so conditional casualty chance is 1/3 and total is 1/6.
    result = calculate()
    row = result.shootings[0]
    assert distribution(row) == pytest.approx({5: 1 / 6, 6: 5 / 6})
    assert row.expected_teams_remaining == pytest.approx(6 - 1 / 6)


def test_dug_in_failed_save_requires_and_uses_adjusted_firepower():
    # Printed FP 5+ adjusts to 4+, so a failed 3+ save (1/3) is fatal only
    # when FP succeeds (1/2): fatal chance conditional on a hit is 1/6.
    # Including the 1/2 hit chance gives one-team casualty probability 1/12.
    result = calculate(dug_in=True)
    assert result.adjusted_firepower == 4
    assert distribution(result.shootings[0]) == pytest.approx({5: 1 / 12, 6: 11 / 12})


@pytest.mark.parametrize(
    ("guns", "expected_hit_probability"),
    [(1, Fraction(1, 4)), (2, Fraction(1, 4)), (3, Fraction(1, 2)), (4, Fraction(1, 2)),
     (5, Fraction(3, 4)), (6, Fraction(3, 4))],
)
def test_weapon_count_hit_rerolls_are_exactly_one_conditional_reroll(guns, expected_hit_probability):
    # At 4+ base To Hit, p=3/6=1/2. One/two guns reroll successes => p²=1/4;
    # five or more reroll failures => 1-(1-p)²=3/4; three/four do not reroll.
    result = calculate(guns_firing=guns)
    casualty_probability = float(expected_hit_probability) / 3
    assert distribution(result.shootings[0]) == pytest.approx(
        {5: casualty_probability, 6: 1 - casualty_probability}
    )


@pytest.mark.parametrize(
    ("range_in", "visibility", "expected_target"),
    [
        (RangeIn.FIRST, True, 4),
        (RangeIn.SECOND, True, 5),
        (RangeIn.THIRD, True, 6),
    ],
)
def test_initial_range_in_modifiers(range_in, visibility, expected_target):
    result = calculate(
        range_in=range_in,
        repeat_spotter_can_see_aiming_point=visibility,
    )
    assert result.shootings[0].resolved_to_hit == expected_target


def test_exact_three_shooting_distribution_carries_the_survivor_state_forward():
    # Shot 1: hit chance 1/2, exposed Infantry save fails 1/3; kill chance 1/6.
    # Each repeat has the same hit chance, but successful 3+ saves are rerolled:
    # final save succeeds (2/3)^2=4/9, so kill chance conditional on hit is 5/9;
    # repeat kill chance is 5/18. The one covered Team survives N shots with
    # (5/6)*(13/18)^(N-1), with five uncovered Teams never affected.
    result = calculate(horizon=3)
    assert [r.shooting_number for r in result.shootings] == [1, 2, 3]
    assert [r.resolved_to_hit for r in result.shootings] == [4, 4, 4]
    survival = [Fraction(5, 6), Fraction(65, 108), Fraction(845, 1944)]
    for row, p_survive in zip(result.shootings, survival):
        assert distribution(row) == pytest.approx({5: 1 - float(p_survive), 6: float(p_survive)})
        assert row.expected_teams_remaining == pytest.approx(5 + float(p_survive))


def test_repeat_unseen_to_hit_modifier_repeats_each_later_shooting():
    result = calculate(
        horizon=3,
        range_in=RangeIn.FIRST,
        repeat_spotter_can_see_aiming_point=False,
        artillery_to_hit=4,
    )
    assert [row.resolved_to_hit for row in result.shootings] == [4, 5, 5]
    # 4+ initial target with 3-4 guns hits on 3/6, so first kill = 1/6;
    # repeat kill = (1/3)*(5/9)=5/27 and multiplies survival onward.
    survivors = [Fraction(5, 6), Fraction(110, 162), Fraction(2420, 4374)]
    for row, p_survive in zip(result.shootings, survivors):
        assert distribution(row) == pytest.approx({5: 1 - float(p_survive), 6: float(p_survive)})


def test_pinning_carries_until_starting_step_rally_and_can_recur():
    # A 4+ Rally succeeds 1/2. A bombardment hits the one covered Team with
    # probability 1/2. After each Starting Step, pin persists only if it was
    # already pinned, Rally failed, and the new volley misses. Repeat save
    # rerolls also raise the covered Team's casualty chance to 5/18 per repeat,
    # reducing future opportunities to hit that same Team. Exact enumeration
    # of (covered survives, pinned) gives 1/2, 7/12, then 227/432.
    result = calculate(horizon=3)
    assert [row.pinned_probability for row in result.shootings] == pytest.approx(
        [Fraction(1, 2), Fraction(7, 12), Fraction(227, 432)]
    )


def test_command_leadership_rerolls_a_failed_rally_test():
    # A 4+ Rally test succeeds on 3/6; Command Leadership rerolls one failure,
    # so success is 1-(3/6)^2=3/4. Propagating the independent hit/save and
    # Rally branches gives P(pinned after shot 2)=1/2 for this one-Team case.
    result = calculate(
        horizon=2,
        part_of_formation=True,
        other_extant_formation_units=1,
        command_leadership_applies=True,
    )
    assert result.shootings[1].pinned_probability == pytest.approx(Fraction(1, 2))


def test_dug_in_repeat_repeats_successful_saves_before_firepower():
    # On a repeat, Infantry save success is (2/3)^2=4/9; failure is 5/9.
    # Foxhole Bulletproof Cover then requires adjusted FP 4+ (1/2) to destroy,
    # so conditional casualty given hit is (5/9)*(1/2)=5/18. With 4+ To Hit,
    # the second-shooting casualty probability is 5/36.
    result = calculate(horizon=2, dug_in=True)
    assert distribution(result.shootings[1]) == pytest.approx(
        {5: 1 - 341 / 432, 6: 341 / 432}
    )


def test_japanese_banners_requires_two_hits_to_pin():
    # With two covered Teams and no hit reroll (Fire Bursts), each Team hits
    # at 1/2. Banners removes the first hit from pinning, so pinning requires
    # both hits: (1/2)^2=1/4.
    result = calculate(
        shooting_nation=ShootingNation.JAPAN,
        infantry_teams_under_template=2,
        in_command_teams_under_template=2,
        infantry_teams_outside_template=5,
        in_command_infantry_outside_template=5,
        unit_initial_infantry_and_gun_teams=7,
        guns_firing=2,
        selected_rules=frozenset({ArtilleryRule.FIRE_BURSTS, ArtilleryRule.BANNERS}),
    )
    assert result.shootings[0].pinned_probability == pytest.approx(1 / 4)


def test_us_time_on_target_rerolls_successful_saves_only_when_selected_and_first_range_in():
    result = calculate(
        shooting_nation=ShootingNation.UNITED_STATES,
        selected_rules=frozenset({ArtilleryRule.TIME_ON_TARGET}),
    )
    # Rerolled successful saves mean survival 4/9 and failure 5/9; hit is 1/2.
    assert distribution(result.shootings[0]) == pytest.approx({5: 5 / 18, 6: 13 / 18})


def test_last_stand_four_plus_success_probability_and_command_reroll():
    # The starting roster is already not In Good Spirits. Its one uncovered
    # Team is never hit, so Last Stand is tested between volleys. A 4+ test
    # succeeds on 3/6; eligible Command Leadership rerolls one failed result,
    # giving 1-(3/6)^2=3/4 success. Using one uncovered Team avoids a zero-Team
    # destruction branch, and Formation membership with one other Unit avoids
    # unrelated Formation destruction.
    base = dict(
        infantry_teams_under_template=1,
        in_command_teams_under_template=1,
        infantry_teams_outside_template=1,
        in_command_infantry_outside_template=1,
        unit_initial_infantry_and_gun_teams=2,
        unit_has_prior_casualty_or_bailed_team=True,
        part_of_formation=True,
        other_extant_formation_units=1,
        horizon=2,
        artillery_to_hit=6,
    )
    no_reroll = calculate(**base)
    with_reroll = calculate(**base, command_leadership_applies=True)
    # 6+ to hit is 1/6 and standard save fails 1/3, so first volley casualty
    # probability is 1/18. Last Stand applies in every surviving branch;
    # any initial casualty still leaves the target unit present.
    assert no_reroll.shootings[0].bad_spirit_probability == pytest.approx(1.0)
    assert no_reroll.shootings[1].destroyed_probability == pytest.approx(1 / 2)
    assert with_reroll.shootings[1].destroyed_probability == pytest.approx(1 / 4)


def test_zero_remaining_teams_destroy_unit_without_last_stand():
    # One covered Team, 4+ To Hit, 3+ save: immediate zero-Team destruction
    # occurs with (1/2)*(1/3)=1/6. No Unit Last Stand is rolled in this branch.
    result = calculate(
        infantry_teams_under_template=1,
        in_command_teams_under_template=1,
        infantry_teams_outside_template=0,
        in_command_infantry_outside_template=0,
        unit_initial_infantry_and_gun_teams=1,
        unit_leader_under_template=True,
    )
    assert result.shootings[0].destroyed_probability == pytest.approx(1 / 6)
    assert distribution(result.shootings[0]) == pytest.approx({0: 1 / 6, 1: 5 / 6})


def test_formation_is_destroyed_only_after_fewer_than_two_units_remain():
    # If the target's only Team is killed, it is immediately gone. With one
    # other extant Formation Unit, the Formation then has only one Unit and is
    # destroyed at the next Starting Step. The target itself may survive its
    # volley, in which case two Units remain and the Formation survives.
    result = calculate(
        infantry_teams_under_template=1,
        in_command_teams_under_template=1,
        infantry_teams_outside_template=0,
        in_command_infantry_outside_template=0,
        unit_initial_infantry_and_gun_teams=1,
        unit_leader_under_template=True,
        part_of_formation=True,
        other_extant_formation_units=1,
        horizon=2,
    )
    assert result.shootings[0].formation_destroyed_probability == pytest.approx(0)
    assert result.shootings[1].formation_destroyed_probability == pytest.approx(1 / 6)
    # The Unit can also be destroyed immediately by a repeat casualty before
    # its next Last Stand check: 1/6 + (5/6)*(1/2)*(5/9) = 43/108.
    assert result.shootings[1].destroyed_probability == pytest.approx(43 / 108)


def test_bad_spirit_probability_uses_survivors_in_command_after_casualties():
    # Three Infantry are In Command before the shot. One covered Team can die
    # with probability 1/6; that leaves two and makes the Unit not In Good
    # Spirits. The two uncovered survivors are unaffected by the template.
    result = calculate(
        infantry_teams_under_template=1,
        in_command_teams_under_template=1,
        infantry_teams_outside_template=2,
        in_command_infantry_outside_template=2,
        unit_initial_infantry_and_gun_teams=3,
    )
    assert result.shootings[0].bad_spirit_probability == pytest.approx(1 / 6)


def test_nation_specific_hit_and_banner_branches_are_explicit_unit_rules():
    # Japanese two-gun Fire Bursts changes the ordinary successful-hit reroll
    # case (p=.25) back to p=.5. It is only active when selected on the Unit.
    base = dict(
        shooting_nation=ShootingNation.JAPAN,
        guns_firing=2,
        infantry_teams_outside_template=5,
        in_command_infantry_outside_template=5,
        unit_initial_infantry_and_gun_teams=6,
    )
    without_rule = calculate(**base)
    with_rule = calculate(**base, selected_rules=frozenset({ArtilleryRule.FIRE_BURSTS}))
    # Kill is hit * failed-save = hit/3.
    assert distribution(without_rule.shootings[0]) == pytest.approx({5: 1 / 12, 6: 11 / 12})
    assert distribution(with_rule.shootings[0]) == pytest.approx({5: 1 / 6, 6: 5 / 6})


def test_repeat_bombardment_cannot_assume_unresolved_time_on_target_overlap():
    with pytest.raises(ValueError, match="Time on Target with Repeat Bombardment is unresolved"):
        command(
            shooting_nation=ShootingNation.UNITED_STATES,
            selected_rules=frozenset({ArtilleryRule.TIME_ON_TARGET}),
            horizon=2,
        )


def test_bad_spirit_never_exceeds_probability_mass_and_results_are_exact_shape():
    result = calculate(horizon=4)
    assert len(result.shootings) == 4
    for row in result.shootings:
        assert sum(probability for _, probability in row.team_count_distribution) == pytest.approx(1)
        assert 0 <= row.bad_spirit_probability <= 1
        assert 0 <= row.destroyed_probability <= 1
        assert 0 <= row.pinned_probability <= 1
