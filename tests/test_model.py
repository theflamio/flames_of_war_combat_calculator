"""Independent contract checks for the abstract simulation model.

The oracle follows the written audit: ordinary target ``h+`` succeeds on
``7-h`` faces of a six-sided die; 7+ and 8+ require 6 then 5+/6+; save
failure and Firepower success are subsequent conditional binomial stages.
These tests verify the implementation's abstract chain, not full V4 resolution.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.fow_combat.model import CombatInput, CombatResult, simulate, to_prob


class FakeRng:
    """Return queued outcomes and record each call's parameters and order."""

    def __init__(self, binomial_results=(), dice_results=()):
        self.binomial_results = list(binomial_results)
        self.dice_results = list(dice_results)
        self.binomial_calls = []
        self.dice_calls = []
        self.events = []

    def binomial(self, n, p, size=None):
        self.events.append("binomial")
        self.binomial_calls.append((np.asarray(n).copy(), p, size))
        result = np.asarray(self.binomial_results.pop(0), dtype=int)
        return result

    def randint(self, low, high, size):
        self.events.append("randint")
        self.dice_calls.append((low, high, size))
        result = np.asarray(self.dice_results.pop(0), dtype=int)
        assert result.shape == size
        return result


@pytest.mark.parametrize(
    ("label", "expected"),
    [("1+", 1), ("2+", 5 / 6), ("3+", 4 / 6), ("4+", 3 / 6),
     ("5+", 2 / 6), ("6+", 1 / 6), ("7+", 0), ("8+", 0)],
)
def test_to_prob_is_six_sided_target_probability(label, expected):
    # Count successful faces among six: 1+..6+ map to 6..1 faces; 7+/8+
    # have no single-die success because they need the separate reroll path.
    assert to_prob(label) == expected


def test_to_prob_rejects_unknown_target_labels():
    with pytest.raises(KeyError):
        to_prob("9+")


@pytest.mark.parametrize(
    ("target", "success_faces", "expected_probability"),
    [("2+", 5, 5 / 6), ("4+", 3, 3 / 6), ("6+", 1, 1 / 6)],
)
def test_normal_hit_stage_uses_target_probability(target, success_faces, expected_probability):
    # Independent die counting gives (7-h)/6 successful faces for a normal h+.
    rng = FakeRng(binomial_results=[[2, 1], [1, 0], [1, 0]])
    result = simulate(CombatInput(3, target, "5+", "4+"), trials=2, rng=rng)

    assert rng.binomial_calls[0][0].item() == 3
    assert rng.binomial_calls[0][1] == expected_probability
    assert expected_probability == success_faces / 6
    assert rng.binomial_calls[0][2] == 2
    assert result.hits.tolist() == [2, 1]


@pytest.mark.parametrize(
    ("target", "second_die_minimum", "expected_hits", "probability"),
    [("7+", 5, [1, 0], 1 / 18), ("8+", 6, [1, 0], 1 / 36)],
)
def test_special_hit_is_six_then_required_second_die(
    target, second_die_minimum, expected_hits, probability
):
    # Two shots/trial: only first-die sixes qualify; the second roll must reach
    # the respective threshold. Enumeration yields 1/6*2/6 or 1/6*1/6.
    rng = FakeRng(
        binomial_results=[[1, 0], [1, 0]],
        dice_results=[[[6, 5], [1, 1]], [[second_die_minimum, 1], [6, 6]]],
    )
    result = simulate(CombatInput(2, target, "7+", "6+"), trials=2, rng=rng)

    assert result.hits.tolist() == expected_hits
    assert [call[:2] for call in rng.dice_calls] == [(1, 7), (1, 7)]
    assert all(call[2] == (2, 2) for call in rng.dice_calls)
    assert rng.binomial_calls[0][1] == 1  # every roll fails the abstract 7+ save
    assert probability == (1 / 6) * ((6 - second_die_minimum + 1) / 6)
    assert rng.events == ["randint", "randint", "binomial", "binomial"]


def test_save_failure_then_firepower_success_receive_prior_stage_counts():
    # The rules-spec abstract model defines a conditional chain: the save draw
    # has n=hits, and Firepower has n=failed saves. This checks both ordering
    # and propagation without using sampled implementation output as the oracle.
    rng = FakeRng(binomial_results=[[4, 2], [3, 1], [2, 0]])
    result = simulate(CombatInput(5, "3+", "4+", "5+"), trials=2, rng=rng)

    assert rng.events == ["binomial", "binomial", "binomial"]
    # NumPy's first binomial draw receives the scalar shot count; later draws
    # receive per-trial arrays produced by the previous stages.
    assert rng.binomial_calls[0][0].item() == 5
    assert [call[0].tolist() for call in rng.binomial_calls[1:]] == [[4, 2], [3, 1]]
    assert [call[1] for call in rng.binomial_calls] == [4 / 6, 1 - 3 / 6, 2 / 6]
    assert [call[2] for call in rng.binomial_calls] == [2, None, None]
    assert result.hits.tolist() == [4, 2]
    assert result.kills.tolist() == [2, 0]


def test_result_preserves_arrays_and_requested_trial_count():
    rng = FakeRng(binomial_results=[[0, 1, 2], [0, 1, 1], [0, 1, 0]])
    result = simulate(CombatInput(2, "4+", "4+", "4+"), trials=3, rng=rng)

    assert isinstance(result, CombatResult)
    assert isinstance(result.hits, np.ndarray)
    assert isinstance(result.kills, np.ndarray)
    assert result.hits.tolist() == [0, 1, 2]
    assert result.kills.tolist() == [0, 1, 0]
    assert result.trials == 3


def test_threshold_count_uses_all_shots_as_opportunity_count():
    # Eight shots with the required sequence 6 then 6 produce exactly eight
    # hits. This supplies the count boundary used for the app's >=8 threshold.
    rng = FakeRng(
        binomial_results=[[8], [8], [8]],
        dice_results=[[[6] * 8], [[6] * 8]],
    )
    result = simulate(CombatInput(8, "8+", "7+", "1+"), trials=1, rng=rng)

    assert result.hits.tolist() == [8]
    assert result.kills.tolist() == [8]
