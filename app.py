"""
Flames of war combat calculator using a binomial chain approach.
The user can input the number of shots, the to hit threshold, the save threshold and the fire power threshold. 
The app will then simulate the combat and output the expected number of hits and kills, 
as well as the probability distribution of hits and kills. 
The app also calculates the probability of achieving
certain thresholds of hits and kills, such as the chance of getting 5+ hits or 2+ kills.
"""

import streamlit as st
import numpy as np

st.title("Flames of war Combat Calculator (Binomial Chain)")

def to_prob(label):
    return {
        "1+": 1.0,
        "2+": 5/6,
        "3+": 4/6,
        "4+": 3/6,
        "5+": 2/6,
        "6+": 1/6,
        "7+": 0.0,
        "8+": 0.0
    }[label]

# --- Inputs ---
shots = st.slider("Number of shots", 1, 50, 20)

#INFO: some special rules for to hit when 7 or 8 is needed example: 7+ it is hit on a 6 and then roll again only a 5+ will it be hit
to_hit = st.selectbox("To hit", ["2+", "3+", "4+", "5+", "6+", "7+", "8+"])
st.write("Save (inf / armor) 7+ means it cannot be saved")
to_save = st.selectbox("Save (inf / armor)", ["1+", "2+", "3+", "4+", "5+", "6+", "7+"])
to_fire_power = st.selectbox("Fire power", ["1+", "2+", "3+", "4+", "5+", "6+"])

p_hit = to_prob(to_hit)
p_fire_power = to_prob(to_fire_power)
p_fail_save = 1 - to_prob(to_save)

# --- Monte Carlo (simple + robust) ---
TRIALS = 50000

if to_hit in ["7+", "8+"]:
    reroll_target = 5 if to_hit == "7+" else 6

    first_rolls = np.random.randint(1, 7, (TRIALS, shots))

    # only successful "6s" proceed
    valid = (first_rolls == 6)

    second_rolls = np.random.randint(1, 7, (TRIALS, shots))

    hits = np.sum(valid & (second_rolls >= reroll_target), axis=1)
else:
    hits = np.random.binomial(shots, p_hit, TRIALS)

failed_saves = np.random.binomial(hits, p_fail_save)
kills = np.random.binomial(failed_saves, p_fire_power)

# -----------------
# Results
# -----------------

col_left, col_right = st.columns(2)

# --- Hits outputs ---
with col_left:
    with st.container(border=True):
        st.subheader("Results hits")

        st.metric("Expected hits", round(np.mean(hits), 2))
        st.metric("Max seen (simulation)", int(np.max(hits)))
        st.metric("Min seen (simulation)", int(np.min(hits)))

        st.subheader("Probability distribution (hits)")
        hist_hits = np.bincount(hits, minlength=shots+1) / TRIALS
        st.bar_chart(hist_hits)

        st.subheader("Key probabilities")
        st.write("Pinned threshold (infantry platoon): 5+ hits")
        st.write("Pinned threshold (big infantry platoon): 8+ hits")

        st.write("Chance of 5+ hits:", round(hist_hits[5:].sum()*100, 2), "%")
        st.write("Chance of 8+ hits:", round(hist_hits[8:].sum()*100, 2), "%")


# --- Kills outputs ---
with col_right:
    with st.container(border=True):
        st.subheader("Results kills")

        st.metric("Expected kills", round(np.mean(kills), 2))
        st.metric("Max seen (simulation)", int(np.max(kills)))
        st.metric("Min seen (simulation)", int(np.min(kills)))

        st.subheader("Probability distribution (kills)")
        hist_kills = np.bincount(kills, minlength=shots+1) / TRIALS
        st.bar_chart(hist_kills)

        st.subheader("Key probabilities")
        st.write("Chance of 2+ kills:", round(hist_kills[2:].sum()*100, 2), "%")
        st.write("Chance of 5+ kills:", round(hist_kills[5:].sum()*100, 2), "%")