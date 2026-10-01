"""Application use cases, independent of Streamlit."""

from .model import CombatInput, CombatResult, TRIALS, RandomSource, simulate


def calculate(combat_input: CombatInput, rng: RandomSource | None = None) -> CombatResult:
    """Calculate one result using the app's established trial count."""
    return simulate(combat_input, trials=TRIALS, rng=rng)
