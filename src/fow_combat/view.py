"""Streamlit widgets and presentation for the combat calculator."""

import numpy as np
import streamlit as st

from .model import CombatInput, CombatResult


def render_inputs() -> CombatInput:
    shots = st.slider("Number of shots", 1, 50, 20)
    to_hit = st.selectbox("To hit", ["2+", "3+", "4+", "5+", "6+", "7+", "8+"])
    st.write("Save (inf / armor) 7+ means it cannot be saved")
    to_save = st.selectbox("Save (inf / armor)", ["1+", "2+", "3+", "4+", "5+", "6+", "7+"])
    to_fire_power = st.selectbox("Fire power", ["1+", "2+", "3+", "4+", "5+", "6+"])
    return CombatInput(shots, to_hit, to_save, to_fire_power)


def render_results(result: CombatResult, shots: int) -> None:
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            st.subheader("Results hits")
            st.metric("Expected hits", round(np.mean(result.hits), 2))
            st.metric("Max seen (simulation)", int(np.max(result.hits)))
            st.metric("Min seen (simulation)", int(np.min(result.hits)))

            st.subheader("Probability distribution (hits)")
            hist_hits = np.bincount(result.hits, minlength=shots + 1) / result.trials
            st.bar_chart(hist_hits)

            st.subheader("Key probabilities")
            st.write("Pinned threshold (infantry platoon): 5+ hits")
            st.write("Pinned threshold (big infantry platoon): 8+ hits")
            st.write("Chance of 5+ hits:", round(hist_hits[5:].sum() * 100, 2), "%")
            st.write("Chance of 8+ hits:", round(hist_hits[8:].sum() * 100, 2), "%")

    with col_right:
        with st.container(border=True):
            st.subheader("Results kills")
            st.metric("Expected kills", round(np.mean(result.kills), 2))
            st.metric("Max seen (simulation)", int(np.max(result.kills)))
            st.metric("Min seen (simulation)", int(np.min(result.kills)))

            st.subheader("Probability distribution (kills)")
            hist_kills = np.bincount(result.kills, minlength=shots + 1) / result.trials
            st.bar_chart(hist_kills)

            st.subheader("Key probabilities")
            st.write("Chance of 2+ kills:", round(hist_kills[2:].sum() * 100, 2), "%")
            st.write("Chance of 5+ kills:", round(hist_kills[5:].sum() * 100, 2), "%")
