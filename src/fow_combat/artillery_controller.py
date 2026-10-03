"""Application service for exact multi-turn artillery probability results."""

from .artillery import ArtilleryCommand, ArtilleryResult, ArtilleryRulesRegistry, calculate_artillery


def calculate_artillery_use_case(
    command: ArtilleryCommand,
    *,
    rules_registry: ArtilleryRulesRegistry,
) -> ArtilleryResult:
    """Resolve a bounded artillery scenario through the domain policy registry."""
    return calculate_artillery(command, rules_registry=rules_registry)
