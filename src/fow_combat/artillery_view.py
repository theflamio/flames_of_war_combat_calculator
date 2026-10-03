"""Streamlit input and result presentation for exact Artillery Shooting."""

from __future__ import annotations

import streamlit as st

from .artillery import (
    ArtilleryCommand,
    ArtilleryResult,
    ArtilleryRule,
    ArtilleryRulesRegistry,
    RangeIn,
    ShootingNation,
)
from .artillery_controller import calculate_artillery_use_case


def _count(label: str, *, minimum: int, maximum: int, value: int) -> int:
    return int(st.number_input(label, min_value=minimum, max_value=maximum, value=value, step=1))


def collect_command() -> ArtilleryCommand:
    """Collect user-resolved artillery, Infantry, Unit and Formation facts."""
    nation = ShootingNation(
        st.selectbox("Shooting Nation", list(ShootingNation), format_func=lambda item: item.value)
    )
    st.caption(
        "Nation choices have explicit US, UK and Japanese artillery policies. The V4 army-book and Unit-card rule inventory is not exhaustive."
    )

    left, right = st.columns(2)
    with left:
        teams_under_template = _count(
            "Infantry Teams under the artillery template", minimum=1, maximum=60, value=4
        )
        in_command_covered = _count(
            "Of those, Infantry Teams In Command", minimum=0, maximum=teams_under_template, value=teams_under_template
        )
        teams_outside = _count("Other Infantry Teams in the target Unit", minimum=0, maximum=60, value=0)
        in_command_outside = _count(
            "Of those, other Infantry Teams In Command", minimum=0, maximum=teams_outside, value=teams_outside
        )
        guns_in_unit = _count("Gun Teams in the target Unit", minimum=0, maximum=30, value=0)
        in_command_guns = _count(
            "Of those, Gun Teams In Command", minimum=0, maximum=guns_in_unit, value=guns_in_unit
        )
        initial_unit_size = _count(
            "Infantry and Gun Teams in the Unit at game start (for large-Unit Last Stand)",
            minimum=max(1, teams_under_template + teams_outside + guns_in_unit),
            maximum=max(100, teams_under_template + teams_outside + guns_in_unit),
            value=teams_under_template + teams_outside + guns_in_unit,
        )
    with right:
        guns_firing = _count("Number of guns firing", minimum=1, maximum=20, value=4)
        to_hit_label = st.selectbox("Artillery To Hit (base target Team Is Hit On)", ["2+", "3+", "4+", "5+", "6+"], index=2)
        firepower_label = st.selectbox("Bombardment Firepower", ["1+", "2+", "3+", "4+", "5+", "6+"], index=3)
        save_label = st.selectbox("Infantry Save", ["3+"], index=0)
        st.caption("V4 assigns Infantry a 3+ Other Save. 4+ and 5+ refer to other target classes and are unsupported here.")
        dug_in = st.checkbox("Target Infantry is Dug In in valid Foxholes (Bulletproof Cover)")
        st.caption("A failed 3+ save against Foxhole Bulletproof Cover is followed by the adjusted bombardment Firepower test.")
        horizon = _count("Number of bombardments in this scenario", minimum=1, maximum=10, value=3)
        initial_range_options = [RangeIn.FIRST, RangeIn.SECOND, RangeIn.THIRD]
        range_in_label = st.selectbox("Initial Range In", [r.value for r in initial_range_options])
        range_in = RangeIn(range_in_label)
        repeat_visible = True
        if horizon > 1:
            repeat_visible = st.checkbox("Spotting Team can see the Aiming Point on Repeat Bombardments", value=True)

    st.subheader("Target Unit state")
    prior_losses = st.checkbox("Unit already has a Team destroyed or still Bailed Out after remounts")
    leader_present = st.checkbox("Unit Leader is present (or has been replaced)", value=True)
    leader_under_template = False
    leader_in_command = True
    if leader_present:
        leader_under_template = st.checkbox(
            "Unit Leader Infantry Team is under the template",
            value=teams_outside == 0,
            disabled=teams_outside == 0,
        )
        leader_in_command = st.checkbox("Unit Leader is In Command", value=True)
    last_stand = st.selectbox("Unit Last Stand rating (or Motivation if no separate rating)", ["2+", "3+", "4+", "5+", "6+"], index=2)
    rally = st.selectbox("Unit Rally rating (or Motivation if no separate rating)", ["2+", "3+", "4+", "5+", "6+"], index=2)
    part_of_formation = st.checkbox("Target Unit belongs to a Formation")
    other_formation_units = 0
    command_leadership = False
    if part_of_formation:
        other_formation_units = _count(
            "Other eligible Formation Units extant after their Last Stand checks (HQ counts; Transports do not)",
            minimum=0,
            maximum=30,
            value=2,
        )
        command_leadership = st.checkbox(
            "Command Leadership reroll applies (Formation Commander within 6in and Line of Sight of Unit Leader)"
        )

    assume_eligible = True
    if horizon > 1:
        assume_eligible = st.checkbox(
            "Assume firing battery remains eligible and keeps its Ranged In marker for all repeats", value=True
        )

    registry = ArtilleryRulesRegistry()
    available = registry.available_unit_rules(nation, range_in)
    selected_rules = frozenset(
        option.identifier
        for option in available
        if st.checkbox(option.label, key=f"artillery_rule_{option.identifier.value}")
    )
    if ArtilleryRule.TIME_ON_TARGET in selected_rules and horizon > 1:
        st.error("Time on Target with a later Repeat Bombardment has an unresolved V4 interaction; reduce the horizon to 1 or clear the rule.")

    return ArtilleryCommand(
        shooting_nation=nation,
        infantry_teams_under_template=teams_under_template,
        in_command_teams_under_template=in_command_covered,
        infantry_teams_outside_template=teams_outside,
        in_command_infantry_outside_template=in_command_outside,
        gun_teams_in_unit=guns_in_unit,
        in_command_gun_teams=in_command_guns,
        unit_initial_infantry_and_gun_teams=initial_unit_size,
        guns_firing=guns_firing,
        artillery_to_hit=int(to_hit_label[0]),
        firepower=int(firepower_label[0]),
        horizon=horizon,
        dug_in=dug_in,
        range_in=range_in,
        repeat_spotter_can_see_aiming_point=repeat_visible,
        infantry_save=int(save_label[0]),
        unit_has_prior_casualty_or_bailed_team=prior_losses,
        unit_leader_present=leader_present,
        unit_leader_under_template=leader_under_template,
        unit_leader_in_command=leader_in_command,
        last_stand_rating=int(last_stand[0]),
        rally_rating=int(rally[0]),
        command_leadership_applies=command_leadership,
        part_of_formation=part_of_formation,
        other_extant_formation_units=other_formation_units,
        assume_battery_remains_eligible=assume_eligible,
        selected_rules=selected_rules,
    )


def render(result: ArtilleryResult) -> None:
    """Display exact per-shooting probability results."""
    st.subheader("Artillery bombardment results")
    st.write(f"Shooting Nation: **{result.shooting_nation.value}**")
    st.write(
        f"Printed Firepower: **{result.firepower_profile}+**; adjusted bombardment Firepower: **{result.adjusted_firepower}+**"
    )
    rows = [
        {
            "Shooting": f"#{row.shooting_number}",
            "Expected Teams Remaining": round(row.expected_teams_remaining, 4),
            "Bad Spirit / Not In Good Spirits": f"{row.bad_spirit_probability * 100:.2f}%",
            "Destroyed": f"{row.destroyed_probability * 100:.2f}%",
            "Formation Destroyed": (
                f"{row.formation_destroyed_probability * 100:.2f}%"
                if row.formation_destroyed_probability is not None
                else "N/A (not in a Formation)"
            ),
            "Pinned Down": f"{row.pinned_probability * 100:.2f}%",
            "Artillery To Hit": f"{row.resolved_to_hit}+",
        }
        for row in result.shootings
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.subheader("Teams remaining distributions")
    for row in result.shootings:
        st.write(f"Shooting #{row.shooting_number}")
        st.dataframe(
            [
                {"Teams Remaining": count, "Probability": f"{probability * 100:.4f}%"}
                for count, probability in row.team_count_distribution
            ],
            hide_index=True,
            use_container_width=True,
        )
    st.write("Rules applied: " + "; ".join(result.used_rule_branches))
    st.subheader("Scope limitations")
    for item in result.incomplete_items:
        st.write(f"- {item}")


def render_page() -> None:
    """Render the dedicated Artillery Shooting calculator page."""
    st.header("Artillery Shooting")
    try:
        command = collect_command()
        result = calculate_artillery_use_case(command, rules_registry=ArtilleryRulesRegistry())
    except (TypeError, ValueError) as exc:
        st.error(str(exc))
        return
    render(result)
