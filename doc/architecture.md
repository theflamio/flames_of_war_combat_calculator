# Proposed MVC architecture

## Purpose and scope

This is a structural proposal for separating the existing Streamlit calculator into Model, View, and Controller responsibilities. It does not approve, revise, or extend the game's rules. The calculation behavior described in `app.py` and audited in `doc/rules-spec.md` is the compatibility baseline. Any future change to rule interpretation still requires an explicit, accepted rules specification.

The Model should be callable without Streamlit so that `pytest` can exercise it directly. Keep the first separation modest: one model module, one controller module, one Streamlit view module, and the existing `app.py` as the composition/entry point.

## Proposed structure

```text
app.py                         # Streamlit entry point / composition root
src/fow_combat/
    __init__.py
    model.py                   # Input/result data types and combat simulation
    controller.py              # Application use case: call model for current input
    view.py                    # Streamlit widgets and result rendering
tests/
    test_model.py              # Model behavior, owned by Test & Math Verification
```

These are proposed paths; the `src/fow_combat/` and `tests/` directories do not currently exist.

## Responsibilities

### Model — `src/fow_combat/model.py`

- Define the calculator's input data contract, for example a frozen `CombatInput` containing shots, To Hit label, save label, and Firepower label.
- Define a result contract, for example `CombatResult` containing per-trial hit and kill counts and the trial count. Keep arrays available for the current observed min/max and histogram presentation; derived summary values may be exposed as model properties or a separate immutable summary type.
- Own `to_prob` and the existing Monte Carlo calculation, including current 7+/8+ hit handling, generic failed-save calculation, Firepower calculation, and 50,000-trial default.
- Have no Streamlit imports, UI side effects, or reads from widget state. Put random-number access behind an injectable RNG/source parameter so model tests can make runs repeatable. The production default must retain unseeded behavior and the same outcome distributions.
- Do not reinterpret rules or silently normalize inputs. The supported inputs and semantics remain those in the existing app and the accepted rules specification.

The model is isolated from application I/O for practical pytest testing. With an injected deterministic random source it is repeatable; without injection it retains the current stochastic behavior. This makes the computation independently testable without turning it into a different game model.

### Controller — `src/fow_combat/controller.py`

- Provide a small use-case function such as `calculate(input: CombatInput) -> CombatResult`.
- Apply application defaults such as the current trial count and call the Model.
- Remain independent of Streamlit so orchestration can be tested with ordinary Python tests if useful.
- Avoid duplicating probability or game-rule logic already owned by the Model.

### View — `src/fow_combat/view.py`

- Own Streamlit widgets, labels, layout, and presentation of results.
- Collect the same shot, To Hit, save, and Firepower values with the current options, bounds, and defaults.
- Render the same metrics, histograms, pinned-hit labels, and kill threshold summaries from a `CombatResult`.
- Avoid implementing probabilities or sampling in the UI.

### Entry point — `app.py`

- Keep `app.py` as the Streamlit launch target and composition root.
- Set the page title, ask the View for the current input, pass it to the Controller, and ask the View to display the returned result.
- Contain no combat mathematics. It can remain short and make the app's data flow explicit.

## Data flow and dependencies

```text
app.py
  ├── View: render inputs → CombatInput
  ├── Controller: calculate(CombatInput) → CombatResult
  │     └── Model: simulate(CombatInput, trials, rng) → CombatResult
  └── View: render results(CombatResult)
```

The dependency direction is one-way: `app.py` composes View and Controller; Controller depends on Model; View depends on the Model's input/result data contracts for annotations and rendering. The Model depends on NumPy and standard Python only. Neither Model nor Controller imports Streamlit. Do not make the Model call the View or Controller.

The View should return a `CombatInput` value rather than pass Streamlit widget state deeper into the application. The Controller should return the Model's result without changing its statistical meaning. Keep UI formatting, such as rounding displayed means and percentages, in the View unless a pure summary type is useful to make those presentation values straightforward to test.

## Compatibility requirements

The initial extraction should preserve the existing user-visible and mathematical behavior:

- Shot slider range 1–50 and default 20; To Hit, save, and Firepower choices and defaults remain as currently declared.
- Keep 50,000 unseeded simulation trials by default.
- Keep the current basic target conversion and 7+/8+ two-roll hit procedure.
- Keep the current generic failed-save and Firepower stages, independent binomial sampling, and their existing ordering.
- Keep hit/kill means, observed sample min/max, distributions, and the 5+, 8+, 2+, and 5+ threshold displays with current labels and rounding.
- Preserve the helper's 1+ conversion even though it is not exposed in the current UI, unless a separate approved change says otherwise.

This is compatibility with the current project implementation, not a claim that every calculation step is a complete Flames of War V4 procedure. In particular, the existing generic save/Firepower chain and threshold labels retain their audited project assumptions and conflicts. Structural extraction must not use the opportunity to resolve them implicitly.

## pytest fit and test boundaries

`tests/test_model.py` should test the Model through its public input/result contract and an injected deterministic random source. Test the current target-to-probability mapping, 7+/8+ hit behavior, the failed-save and Firepower stages, output lengths, histogram counts summing to the trial count, and threshold-tail calculations where those are exposed as pure model summaries. Keep UI rendering outside these tests. If the model uses RNG operations that are difficult to control with a seeded generator, define a small random-source interface or inject a compatible NumPy RNG; do not add Streamlit as a test dependency for model tests.

The Test & Math Verification Agent owns `tests/**` and must derive expected values independently from the accepted rules specification and mathematical reasoning. The Developer may expose the model contract and implement it but must not define its own tests' expected values. Exact probability identities and deterministic draws can verify the chain without relying on noisy Monte Carlo means. Tests of Monte Carlo estimates should use justified tolerances and avoid flaky assertions.

## File ownership

| Files | Owner | Boundary |
|---|---|---|
| `doc/architecture.md` | Software Architect | Module boundaries and interface proposal only. |
| `doc/rules-spec.md` | Flames of War Rules Expert | Rule evidence, classifications, and unresolved rule questions. |
| `app.py`, `src/fow_combat/**` | Python Developer | Entry point, Model, Controller, View, and integration, constrained by the accepted rule specification. |
| `tests/**` | Test & Math Verification Agent | Independent model tests and math verification; no production-code edits. |
| `AGENTS.md`, `.codex/config.toml`, `.codex/agents/lead.toml` | Lead Agent | Workflow configuration and coordination. |

The Lead assigns any integration edit to the Developer and should ask the Architect to update this document when the accepted structure or contracts change. Ownership is a collaboration rule; it is not a filesystem access control.

## Decisions to confirm during implementation

- Choose the concrete names and fields for `CombatInput` and `CombatResult` while keeping the contract small and typed.
- Select a NumPy RNG injection shape that supports deterministic model tests and preserves unseeded production use.
- Decide whether histograms and threshold tails are pure Model outputs or are derived in the View. Keep them deterministic and based on the same sampled counts either way; do not resample to render separate statistics.
- Decide the import/install arrangement for the proposed `src` layout so both `streamlit run app.py` and `pytest` resolve `fow_combat` consistently. This is packaging plumbing, not a reason to alter combat behavior.
