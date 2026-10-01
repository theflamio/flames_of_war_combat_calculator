"""Pure combat simulation model, independent of the Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

TRIALS = 50_000


class RandomSource(Protocol):
    """The NumPy random operations used by the simulation."""

    def binomial(self, n: int | NDArray[np.integer], p: float, size: int) -> NDArray[np.integer]: ...


@dataclass(frozen=True)
class CombatInput:
    shots: int
    to_hit: str
    to_save: str
    to_fire_power: str


@dataclass(frozen=True)
class CombatResult:
    hits: NDArray[np.integer]
    kills: NDArray[np.integer]
    trials: int


def to_prob(label: str) -> float:
    """Return the existing single-die target probability mapping."""
    return {
        "1+": 1.0,
        "2+": 5 / 6,
        "3+": 4 / 6,
        "4+": 3 / 6,
        "5+": 2 / 6,
        "6+": 1 / 6,
        "7+": 0.0,
        "8+": 0.0,
    }[label]


def simulate(
    combat_input: CombatInput,
    trials: int = TRIALS,
    rng: RandomSource | None = None,
) -> CombatResult:
    """Simulate the existing hit, failed-save, and Firepower binomial chain.

    ``rng`` may be ``numpy.random``, a NumPy Generator, or a compatible source. Omitting it
    uses NumPy's unseeded global random source, matching the original app.
    """
    random = np.random if rng is None else rng
    p_hit = to_prob(combat_input.to_hit)
    p_fire_power = to_prob(combat_input.to_fire_power)
    p_fail_save = 1 - to_prob(combat_input.to_save)

    if combat_input.to_hit in ["7+", "8+"]:
        reroll_target = 5 if combat_input.to_hit == "7+" else 6

        draw_integers = getattr(random, "randint", None) or random.integers
        first_rolls = draw_integers(1, 7, (trials, combat_input.shots))
        valid = first_rolls == 6
        second_rolls = draw_integers(1, 7, (trials, combat_input.shots))
        hits = np.sum(valid & (second_rolls >= reroll_target), axis=1)
    else:
        hits = random.binomial(combat_input.shots, p_hit, trials)

    failed_saves = random.binomial(hits, p_fail_save)
    kills = random.binomial(failed_saves, p_fire_power)
    return CombatResult(hits=hits, kills=kills, trials=trials)
