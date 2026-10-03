# Proposed architecture: Flames of War V4 shooting resolution

## Purpose and boundaries

This document describes both the current implementation and a design proposal for evolving the calculator from its present abstract binomial chain into a user-input-driven V4 shooting-resolution calculator. Users already know the tabletop situation and enter its relevant facts; the app does not identify weapons or units from a database or catalog. The architecture does not implement rules or decide any item marked `UNRESOLVED` in `doc/rules-spec.md`. Future rule behavior must be specified there, with verified facts, assumptions, and unresolved questions distinguished, and accepted by the Lead Agent before implementation. `IMPLEMENTATION_CONFLICT` entries describe behavior in the existing app that the architecture expects later approved rule implementation to replace; they are not themselves a complete replacement specification.

This proposal separates domain calculation from Streamlit and allows calculation to be run deterministically without UI or global random state. It recommends introducing richer domain types and modules incrementally, retaining the current MVC boundary as the application shell.

## Evidence and classification key

- **[VERIFIED_V4]** is a rule or procedure explicitly supported by the verified material recorded in `doc/rules-spec.md` (the V4 Quick Reference Sheet and its cited V4 FAQ clarification). The listed rulebook page references and qualifications remain those in that document.
- **[PROJECT CONCEPT]** names an existing calculator concept or a domain entity needed to express the audited procedure. It is not by itself a game-rule claim.
- **[ARCHITECTURE]** is a software design recommendation, not a rule interpretation.
- **[UNRESOLVED V4]** marks dependencies the available rules audit does not settle. No default or behavior is proposed for them.

## Proposed package structure (PLANNED)

```text
app.py                              # Streamlit composition root
src/fow_combat/
    __init__.py
    application/
        commands.py                 # Input command / use-case request types
        shooting_service.py         # Orchestrates one requested resolution
        ports.py                    # RNG protocols
    domain/
        inputs.py                   # Direct shot count and user-provided situation facts
        shooting.py                 # Current shooting situation and specified hit resolution
        resolution.py               # Aggregate resolution result and probability distributions
    adapters/
        streamlit_view.py            # Widgets and result display
        numpy_rng.py                 # Production random-source adapter
    reporting/
        summaries.py                 # Histograms and presentation-independent summaries
 tests/
    ...                              # Owned and derived by verification role when requested
```

**[ARCHITECTURE]** The initial implementation need not create every file at once. Keep dependencies pointing inward: Streamlit and NumPy adapters depend on application/domain contracts; domain modules depend on other domain contracts only. The application service coordinates domain operations, while the domain has no Streamlit imports, display formatting, or direct calls to a global random generator. Avoid a single `model.py` becoming a second monolith; split modules when an accepted behavior has a clear owner.

## Current implementation snapshot (IMPLEMENTED)

The application currently has two separate paths. Normal Shooting uses `app.py -> view.py -> controller.calculate -> model.simulate`; that legacy model owns the abstract hit/save/Firepower binomial chain and imports NumPy. The Streamlit view owns its widgets and presentation summaries and imports NumPy for histograms. The separate Artillery Shooting page uses `app.py -> artillery_view.render_page -> artillery_controller.calculate_artillery_use_case -> artillery.calculate_artillery`; the artillery resolver uses the `domain.dice.DieRoller` port and a nation-specific rules registry. The `domain` package also contains the existing direct-shooting data-only inputs and typed To Hit and Firepower thresholds. The direct-shooting domain values do not drive either current UI path. No general direct-fire V4 resolver or hit-allocation module is implemented; artillery V1 implements only its explicitly supported Infantry bombardment calculation and exposes incomplete outputs as described below.

The actual domain input objects do not require weapon or Unit identity. `shots` is entered directly; `ShootingConditions` preserves battlefield flags separately; `TargetSituation.team_count` can represent the 12+ Teams criterion and other relevant target facts; `SaveSituation` can represent explicit but possibly incomplete save facts. These structures carry facts only and do not implement their rule effects. The existing Streamlit UI still uses the legacy `CombatInput` (`shots`, string To Hit, save, Firepower) and does not expose the new domain situation.

The diagrams below use **IMPLEMENTED** for code that exists, **PLANNED** for architecture proposed here, and **UNRESOLVED** for rule-dependent stages blocked by `doc/rules-spec.md`. PlantUML source is maintained only in `doc/uml/`:

- [System context](uml/system-context.puml)
- [Components and layers](uml/components.puml)
- [V1.0.0 calculation flow](uml/calculation-flow.puml)
- [Domain input model](uml/domain-model.puml)
- [Python module dependencies](uml/python-dependencies.puml)

## Domain model and responsibilities

### User-provided situation facts and firing context

- **[ARCHITECTURE]** The user directly enters the total number of shots and Firepower, along with relevant current-situation facts such as To Hit value/modifier information, long-range status, target concealed, target dug in, Gone to Ground, save/armour facts, and other inputs the product requests. These facts are entered directly; the app does not identify a weapon or unit, consult a weapon/unit database or army list, calculate shots from model count × ROF, or require the user to build a weapon profile.
- **[PROJECT CONCEPT]** `ShootingInput` (or an equivalent small request type) carries the direct shot count, Firepower, and user-provided situation facts. It does not need `Weapon`, `WeaponProfile`, `RateOfFire`, firing-mode selection, or a weapon catalog. `dug_in`, `concealed`, and `gone_to_ground` remain distinct user facts and must not be derived from one another.
- **[ARCHITECTURE]** An explicit Rules Expert-owned applicability mapping in the accepted V4 rules specification determines which supplied facts affect which resolution stages, and under what conditions. The application preserves the input facts separately from applicable modifiers and rule-derived results. It must not infer stage applicability in widgets, generic parsing, or domain defaults.
- **[UNRESOLVED V4]** Full input-to-stage applicability and interactions outside the verified cases must be specified before the corresponding V4 calculation is enabled. Direct entry of a fact does not itself mean it modifies a particular stage; the verified Dug In-to-Concealed cases are described below.

### Target facts and hit modifiers

- **[PROJECT CONCEPT]** Represent target class/state and other relevant facts as direct situation inputs when requested. No unit identification or profile retrieval is assumed. A target identity input is needed only if an accepted rule requires it.
- **[VERIFIED_V4]** The current audit records the V4 hit modifiers: +1 for range over 16in/40cm, Concealed but not Gone to Ground, shooter Out of Command, smoke, or night; +2 for Concealed and Gone to Ground. It also records sequencing inputs including range, line of sight, concealment, target declaration, and shooting eligibility.
- **[ARCHITECTURE]** The accepted V4 specification owns an explicit input-to-stage applicability mapping. Represent user-provided facts separately from rule-derived applicability decisions; preserve applicable decisions and reasons in the result. Inputs such as range, concealment, Dug In, Gone to Ground, command, smoke, and night must not automatically modify a stage merely because they were supplied. In particular, Dug In is not an independent To Hit modifier; apply the verified concealment relationship only when its stated conditions hold.
- **[UNRESOLVED V4]** The audit does not fully specify how every target-state, weapon-specific, scenario, or special-rule circumstance enters the calculation. Modifier eligibility and precedence beyond listed verified cases must remain behind policies whose behavior is enabled only by accepted specification.
- **[VERIFIED_V4]** Dug In is not itself a To Hit modifier. It can make particular Infantry or man-packed/medium Gun Teams Concealed under the applicable conditions; retain `dug_in` independently and do not infer `concealed` without the required Team/context facts (see `doc/rules-spec.md`).
- **[UNRESOLVED V4]** The existing helper's `1+` To Hit mapping is explicitly unresolved. Do not expose it as an available domain result or assign it game semantics absent a specification.

### To Hit and random die outcomes

- **[VERIFIED_V4]** An ordinary target from 2+ through 6+ corresponds to its unmodified single-D6 success probability. For 7+ the V4 procedure is 6 followed by 5+; for 8+ it is 6 followed by 6.
- **[ARCHITECTURE]** `ToHitTarget` should be a typed user-entered value, not a UI string. A pure `ToHitCalculator` receives that fact and the accepted policy's applicable inputs; a `HitResolver` consumes a `DieRoller` port and emits one `ShotOutcome` per shot. For 7+/8+, model the gated second roll as part of that shot's recorded roll sequence, rather than replacing it with an approximate probability. A sequence of shot outcomes supports audit, allocation, and deterministic replay.
- **[PROJECT CONCEPT]** Preserve probability reporting as a derived summary where useful, but do not make a probability-only binomial draw the domain event if the application needs per-shot allocation and traces.

### Saves and outcome types

- **[VERIFIED_V4]** V4 has distinct Armour Save and Other Save procedures. Armour resolution uses armour rating, Anti-tank, and the recorded range condition; its outcomes include bail out or destruction depending on comparisons. Other Saves depend on target class and can directly destroy on a failed save in some cases.
- **[ARCHITECTURE]** Represent save facts and outcomes only to the extent required by the accepted specification. Select a save procedure from supplied situation facts only where accepted rules specify the branch. Do not model every save as one generic threshold or collapse distinct outcomes into “kill.”
- **[UNRESOLVED V4]** The intended target class and outcome represented by the current generic save selector are unresolved. Branch selection, all save modifiers, and details not established by the audit remain blocked on a rules specification. Keep those as explicit missing/unknown input rather than a default save type.

### Firepower

- **[VERIFIED_V4]** Firepower is invoked only in specified resolution branches, including recorded armour and Other Save cases. It is not an unconditional check after every failed save. When called, its threshold test is a D6 test.
- **[ARCHITECTURE]** `FirepowerResolver` accepts a typed `Firepower` value and an explicit eligible resolution context; it returns a typed success/failure result and die trace. The caller/branch policy decides whether Firepower applies, and must be derived from accepted rules. Keep its interface unable to silently run for every failure.
- **[UNRESOLVED V4]** The audit leaves unspecified the intended circumstance for the current generic Firepower test. Do not bind that selector to a save category or resolution branch until specified.

### Pinning

- **[VERIFIED_V4]** A Unit reaches the Pinned Down threshold at 5 total hits, or 8 total hits if it has at least 12 Teams. Armoured Tank Teams and Aircraft cannot be Pinned Down. “Big platoon” is not the rule criterion; use the target Unit Team count where this context is represented.
- **[ARCHITECTURE]** The target facts can be supplied directly, without a Unit identity or profile lookup. Any pinning distribution interface should keep its target context and cumulative hit basis explicit; the thresholds and ineligibility facts are already specified in `doc/rules-spec.md`.
- **[UNRESOLVED V4]** The hit allocation and target/volley grouping needed to derive a pinning probability, the mapping from shot outcomes to Unit-allocated hits, and the treatment of prior/cumulative hits remain unspecified. Do not report the legacy whole-volley hit tails as V4 pinning probabilities.

### Additional V4 inputs

- **[ARCHITECTURE]** Keep the MVP domain model small. Add only the situation inputs and stage calculations required by the accepted rules specification and requested outputs; do not introduce a general special-rule framework, weapon catalog, or abstractions for unsupported cases.
- **[UNRESOLVED V4]** Other special rules and their interactions are not established by the audit. Add them only when specified and needed by the product.

## Application and Streamlit interface

**[ARCHITECTURE]** Keep `app.py` as the composition root. `streamlit_view.py` gathers the user's current-situation facts into an application command and renders a completed result. It must not calculate probabilities, decide rule applicability, choose game-rule branches, or call the RNG. The application service validates the command, passes the entered facts through rules-owned applicability policies, invokes only specified resolution stages, and returns an immutable `ShootingResolution` suitable for rendering. Each input is applied at a stage only when the accepted V4 specification says it applies under the supplied conditions. Input-to-rule mapping belongs behind that policy/specification boundary, not in widgets, generic input parsing, or an implicit catalog.

A proposed flow is:

```text
app.py
  -> StreamlitView.collect_command() -> ShootingCommand
  -> ShootingService.resolve(command, dependencies) -> ShootingResolution
       -> rules-owned applicability/context preparation
       -> direct shot count -> specified To Hit resolution
       -> specified save and Firepower resolution
       -> hit, pinning, and kill distributions where defined
  -> StreamlitView.render(resolution)
```

The stages shown define architectural seams, not a claim that every branch or ordering detail is completely specified. User-entered facts do not imply applicability: for example, entering long range, concealed, Dug In, armour/save details, or Firepower does not itself determine which calculations they affect. `dug_in` remains distinct from `concealed` and `gone_to_ground`; the rules spec describes when Dug In can make particular Teams Concealed, but applicability depends on the actual Team type and situation or on entering the resolved Concealed fact. The application must not run a downstream stage when its required game-rule condition is unresolved. The UI requests the current-situation facts needed by accepted rules and outputs, and must not present an underspecified result as complete V4 output. Probability distributions for hits/pinning and kills are desired outputs. The 5/8 pinning thresholds and pinning ineligibility facts are specified; deriving V4 pinning probabilities still depends on unresolved allocation and hit-pool semantics. Presentation summaries derive from the same resolution outcomes.

The current widgets and calculations are the V1.0.0 baseline. Migration may temporarily retain that explicitly named legacy/abstract behavior, but it must not be presented as V4 shooting until applicable V4 behavior is specified and implemented. The product's direct shot-count and Firepower inputs remain the input model.

## Randomness and deterministic testing

- **[ARCHITECTURE]** Inject a `RandomSource`/`DieRoller` interface at the application boundary. A minimal domain-facing contract supplies a D6 result; production uses an adapter backed by NumPy or another selected source. No domain function reads global random state.
- Each resolution command may receive a seed or a supplied random-source instance. Seed handling belongs to the adapter/application layer; results can include a replayable seed or roll trace according to product needs. Avoid passing a NumPy-specific API into domain modules.
- Pure calculations (modifier aggregation, target selection, branch selection, summaries) need no randomness and should be tested as ordinary deterministic functions.
- Deterministic resolver tests inject queued die results and verify the sequence, branch gates, and emitted events. Mathematical verification derives expected results independently from the accepted rules specification. Statistical tests, if later required, should be separate, seeded, and tolerance-based; do not use simulation estimates as the expected-value oracle.
- **[UNRESOLVED V4]** Randomness does not resolve any game-rule ambiguity. A seeded simulation of an unspecified volley, save type, Firepower branch, or pinning pool remains semantically unspecified.

## Migration from current implementation

1. Preserve `src/fow_combat/model.py`, `controller.py`, `view.py`, and `app.py` as the V1.0.0 abstract-chain baseline while establishing the small situation-input and resolution contracts. The present implementation samples hits, generic failed saves, and generic Firepower kills; current tests verify that abstraction, not full V4 procedure.
2. Extract shared types and introduce injected D6 randomness without changing the existing model's behavior. Keep any compatibility API clearly named/documented as legacy abstraction; do not silently change its output labels or claim V4 conformance through refactoring.
3. Add user-input contracts for current-situation facts as product requirements and accepted rules require. Do not add a weapon/unit catalog dependency. Keep user facts distinct from rule-derived applicability; keep missing data explicit and reject or mark incomplete commands instead of inventing defaults.
4. Implement one fully specified resolution stage at a time, with separate owner-assigned rules specification, domain implementation, and independently derived verification. Route each stage through the service while retaining the old path until a replacement is accepted and reviewed.
5. Replace conflicting UI controls and outputs only under later explicit rules implementation work. In particular, generic save/Firepower, aggregate pinning tails, and “kills” must not be re-labeled as V4 outcomes without specified domain semantics.
6. Remove the compatibility path only after product acceptance and the test/verification role has established the replacement behavior. No migration step authorizes a rule interpretation by itself.

## Unresolved rule dependencies and design boundaries

| Unresolved item from `doc/rules-spec.md` | Boundary affected | Required treatment |
|---|---|---|
| Whether V4 outcomes require a defined target/volley topology or per-Unit hit pool | Save resolution and pinning distribution interpretation | Keep any dependent V4 output incomplete until specified; direct total shot count remains the user input. |
| Target class for generic save and intended outcome | Save resolver selection and result vocabulary | No generic-to-V4 mapping; retain separate save contexts and require specified target facts. |
| Circumstance for generic Firepower | Firepower branch policy | No unconditional invocation or assumed branch. |
| Hit allocation, target/volley grouping, and prior/cumulative hit pool for pinning probability | Pinning probability distribution | Apply the verified 5-hit / 8-for-at-least-12-Teams threshold and verified ineligibility facts, but keep probabilities incomplete until hit allocation and cumulative pool semantics are specified. |
| Target state, any applicable weapon-specific rules, and range/terrain circumstances | Eligibility and modifier applicability | Add only individually specified facts and policies; the product does not require a weapon profile or catalog. |
| `1+` To Hit helper | To Hit target type and UI options | Do not assign V4 semantics; exclude pending explicit resolution. |

## Existing implementation conflicts

The current code's fixed To Hit selector, generic save threshold, unconditional failed-save-to-Firepower-to-kill chain, aggregate hit pool, and “infantry platoon”/“big infantry platoon” thresholds are documented as `IMPLEMENTATION_CONFLICT` or `UNRESOLVED` in the audit. This architecture identifies the components where later implementation can replace those behaviors; it does not itself authorize or specify the replacement. Existing behavior remains historical project behavior, not an accepted V4 specification.

## Artillery Shooting V1 (IMPLEMENTED WITH EXPLICIT LIMITS)

Artillery is a separate UI and calculation path. The current `app.py` sidebar selects Normal Shooting or Artillery Shooting. The normal option continues to call `view.render_inputs`, `controller.calculate`, and `view.render_results`; the artillery option imports and calls `artillery_view.render_page`. This keeps the legacy normal calculator independent of artillery inputs and resolution.

### Implemented modules and interfaces

```text
app.py
  -> src/fow_combat/artillery_view.py::render_page
       -> collect_command() -> ArtilleryCommand
       -> artillery_controller.calculate_artillery_use_case(...)
            -> artillery.calculate_artillery(...)
                 -> ArtilleryRulesRegistry.for_nation(...)
                 -> DieRoller.roll_d6()
            -> ArtilleryResult
       -> render(result, infantry_teams_under_template)
```

`src/fow_combat/artillery.py` contains `ShootingNation`, `RangeIn`, `ArtilleryCommand`, the `NationArtilleryRules` protocol, `ArtilleryRulesRegistry`, `ArtilleryResult`, Firepower adjustment, and the Monte Carlo resolver. The controller wrapper in `artillery_controller.py` forwards the command, registry, injected `DieRoller`, and trial count. `artillery_view.py` owns Streamlit collection/rendering and supplies a `secrets`-backed D6 source; the resolver itself has no Streamlit or NumPy dependency. The result includes sampled hits and casualties, the adjusted Firepower, optional pin probability, applied rule labels, and an `incomplete_items` list.

`ArtilleryCommand` carries Shooting Nation, Infantry Teams under the template, guns firing, Artillery To Hit, Firepower, Range In stage, same-Unit confirmation, Repeat Bombardment spotter visibility, and `selected_rules` as a set of `ArtilleryRule` identifiers. It intentionally has no target-nation field, vehicle target, weapon profile, or unit database identity. `ShootingNation` is the firing force. The registry currently supports United States, United Kingdom, and Japan policies. Other / unsupported nation selection is present in the UI enum but has no registry entry and returns an unsupported-policy error. `ArtilleryRulesRegistry.available_unit_rules(nation, range_in)` returns the allowed labeled choices for that scenario; the resolver validates selected identifiers against that list.

### Supported and incomplete behavior

The resolver implements the accepted `doc/rules-spec.md` artillery behavior it models: the first/second/third/Repeat To Hit adjustments; the 1–2-gun successful-hit re-roll and 5+-gun failed-hit re-roll; individual To Hit rolls per Infantry Team under the template; ordinary exposed Infantry 3+ saves; Repeat Bombardment and declared US Time on Target successful-save re-roll behavior; Japanese Fire Bursts and Banners conditions; and the V4 artillery Firepower profile adjustment table. The selected nation policy is passed into the domain resolver through `ArtilleryRulesRegistry`; nation-specific effects are not implemented in the Streamlit layer. The simulation resolves one bombardment scenario and stops after the supplied Infantry Teams receive hit/save resolution. Repeat Bombardment is selected as the scenario's Range In state, not an automatic repeat loop across turns.

Pinning is reported only when the user confirms all teams under the template belong to the same Unit. In that case the sampled hit distribution is compared against the artillery one-hit pin threshold, or the two-hit Japanese Banners threshold. Without that confirmation `pin_probability` and threshold remain `None`, and the view explains the missing same-Unit condition. This condition is necessary because pinning is a Unit state; the app does not infer grouping from template count.

Individual Infantry Team casualties are reported from failed saves against the ordinary 3+ Infantry save. Unit/Formation destruction and Last Stand remain unresolved and are not reported as V1 outputs. The implementation records the Firepower profile and adjusted value but does not roll Firepower against ordinary exposed Infantry, consistent with the audited save branch. It cannot derive Unit/Formation destruction or Last Stand from the template count alone. Other listed limitations are returned in `incomplete_items`: unsupported defensive exceptions (including unmodeled non-terrain cover interactions) and weapon rules such as Brutal; incomplete national rules (including British Mike Target coordination); and the scope is limited to ordinary exposed Infantry. The overlap of Repeat Bombardment and Time on Target remains unresolved in the rule spec and is explicitly withheld by the UI for a Repeat scenario.

The nation rules registry is a deliberately small verified-policy boundary, not a complete rules catalog. The UI asks the registry for available Unit-rule options and renders them generically; it contains no nation-specific rule conditionals. Selection remains explicit because nationality alone does not establish that a Unit has Time on Target, Fire Bursts, or Banners. UK Mike Target coordinates separate batteries and is outside this single-bombardment flow. Nations without an implemented, verified V1 policy must not inherit another policy; currently they fail explicitly.

### Remaining planned architecture and rule dependencies

This V1 is implemented in a compact module and has not been split into a general artillery target hierarchy, multiple resolver stages, or per-nation files. Keep that simple structure unless a concrete extension needs the split. The original proposed structure above for application services/adapters is a broader architecture direction, not a description of current artillery code. Vehicle targets remain out of scope; a future target abstraction may be introduced when another target category is actually implemented.

The rules spec leaves Bad Spirit / Unit Last Stand application, Formation destruction after casualties, and destruction caused by this bombardment unresolved for calculator output. It also leaves broader nation-specific rule coverage and repeat/Time on Target overlapping re-roll semantics unresolved. Do not extend resolver behavior into those cases without a rules-spec update and acceptance. The existing tests currently cover the normal legacy chain and direct-shooting domain contract; artillery-specific verification is not yet represented in `tests/`. Future tests should be independently derived from the accepted rules specification by the Test & Math Verification role. The existing UML diagrams do not yet show the implemented artillery flow and remain candidates for a separate diagram update.
