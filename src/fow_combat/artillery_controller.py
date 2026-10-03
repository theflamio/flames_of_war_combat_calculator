"""Application entry point for Artillery Shooting."""

from .artillery import ArtilleryCommand, ArtilleryResult, ArtilleryRulesRegistry, calculate_artillery
from .domain.dice import DieRoller


def calculate_artillery_use_case(
    command: ArtilleryCommand,
    *,
    rules_registry: ArtilleryRulesRegistry,
    die_roller: DieRoller,
    trials: int = 10_000,
) -> ArtilleryResult:
    return calculate_artillery(
        command, rules_registry=rules_registry, die_roller=die_roller, trials=trials
    )
