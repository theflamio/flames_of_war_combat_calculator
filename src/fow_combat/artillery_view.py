"""Streamlit presentation for the separate Artillery Shooting use case."""

from __future__ import annotations

import secrets

import numpy as np
import streamlit as st

from .artillery import ArtilleryCommand, ArtilleryResult, ArtilleryRulesRegistry, RangeIn, ShootingNation
from .artillery_controller import calculate_artillery_use_case


class _SecureDieRoller:
    def roll_d6(self) -> int:
        return secrets.randbelow(6) + 1


def collect_command() -> ArtilleryCommand:
    nation = ShootingNation(st.selectbox("Shooting Nation", list(ShootingNation), format_func=lambda n: n.value))
    teams = st.number_input("Infantry Teams under template", min_value=1, max_value=100, value=4, step=1)
    guns = st.number_input("Number of guns firing", min_value=1, max_value=20, value=4, step=1)
    same_unit = st.checkbox("All Infantry Teams under the template belong to the same Unit")
    to_hit_label = st.selectbox("Artillery To Hit (target Team Is Hit On)", ["2+", "3+", "4+", "5+", "6+"], index=2)
    firepower_label = st.selectbox("Firepower", ["1+", "2+", "3+", "4+", "5+", "6+"], index=2)
    st.caption("Firepower is recorded and adjusted by the V4 artillery table. It is not an extra roll against ordinary exposed Infantry.")
    range_label = st.selectbox("Range In", [r.value for r in RangeIn])
    range_in = RangeIn(range_label)
    spotter_sees = True
    if range_in is RangeIn.REPEAT:
        spotter_sees = st.checkbox("Spotting Team can see the Aiming Point", value=True)

    registry = ArtilleryRulesRegistry()
    available_rules = registry.available_unit_rules(nation, range_in)
    selected_rules = frozenset(
        option.identifier
        for option in available_rules
        if st.checkbox(option.label, key=f"artillery_rule_{option.identifier.value}")
    )

    return ArtilleryCommand(
        shooting_nation=nation,
        infantry_teams_under_template=int(teams),
        guns_firing=int(guns),
        artillery_to_hit=int(to_hit_label[0]),
        firepower=int(firepower_label[0]),
        range_in=range_in,
        teams_under_template_same_unit=same_unit,
        repeat_spotter_can_see_aiming_point=spotter_sees,
        selected_rules=selected_rules,
    )


def render(result: ArtilleryResult, teams: int) -> None:
    st.subheader("Artillery bombardment results")
    st.write(f"Shooting Nation: **{result.shooting_nation.value}**")
    st.write(f"Resolved Artillery To Hit: **{result.resolved_to_hit}+**")
    left, right = st.columns(2)
    with left:
        st.metric("Average Teams hit", round(float(np.mean(result.hits_per_trial)), 2))
        st.subheader("Teams hit distribution")
        st.bar_chart(np.bincount(result.hits_per_trial, minlength=teams + 1) / result.trials)
    with right:
        st.metric("Average Infantry casualties", round(float(np.mean(result.casualties_per_trial)), 2))
        st.subheader("Infantry casualties distribution")
        st.bar_chart(np.bincount(result.casualties_per_trial, minlength=teams + 1) / result.trials)

    st.write(f"Firepower profile: {result.firepower_profile}+; adjusted artillery Firepower: {result.adjusted_firepower}+")
    st.caption("The adjusted Firepower does not affect the ordinary exposed Infantry save/casualty calculation above.")
    st.subheader("Pinning")
    if result.pin_probability is None:
        st.info("Unavailable: confirm that all Infantry Teams under the template belong to the same Unit.")
    else:
        st.metric(
            f"Chance Unit is Pinned ({result.pinning_hit_threshold}+ bombardment hits)",
            f"{result.pin_probability * 100:.2f}%",
        )
    st.write("Rules applied: " + "; ".join(result.used_rule_branches))
    st.subheader("Incomplete or unsupported results")
    for item in result.incomplete_items:
        st.write(f"- {item}")


def render_page() -> None:
    st.header("Artillery Shooting")
    try:
        command = collect_command()
        result = calculate_artillery_use_case(
            command,
            rules_registry=ArtilleryRulesRegistry(),
            die_roller=_SecureDieRoller(),
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    render(result, command.infantry_teams_under_template)
