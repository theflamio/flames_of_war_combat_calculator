"""Streamlit entry point and composition root for the calculator."""

import streamlit as st

from src.fow_combat.controller import calculate
from src.fow_combat.view import render_inputs, render_results


st.title("Flames of war Combat Calculator (Binomial Chain)")
combat_input = render_inputs()
result = calculate(combat_input)
render_results(result, combat_input.shots)
