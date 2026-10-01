# Repository agent workflow

This repository uses Codex project-scoped custom agents declared in `.codex/agents/`.
The primary agent acts as the Lead Agent and coordinates specialist work through
Codex's native subagent mechanism. Do not make parallel assignments that write to
the same owned files.

## Shared constraints

- Treat the user's current request as the authority for whether work is read-only,
  documentation-only, or implementation work. Do not infer permission to change
  application behavior from an analysis or setup request.
- No agent may change game-rule interpretation based on guesswork. Rule changes
  require an explicit written specification from the Flames of War Rules Expert
  and acceptance by the Lead Agent. Uncertain rules must be marked unresolved.
- The Python Developer implements the accepted specification; the Developer does
  not decide or reinterpret game rules.
- The Test & Math Verification Agent derives expected results independently from
  the accepted rules specification and mathematical reasoning. It must not use
  the Developer's claims or implementation as the source of expected values.
- Respect the file ownership map below. Ask the Lead Agent to route a change to
  its owner rather than editing another role's files. Ownership is a workflow
  boundary; Codex permissions do not enforce per-agent path restrictions.
- Do not commit changes unless the user explicitly asks.

## File ownership

| Role | May modify | Must not modify |
| --- | --- | --- |
| Lead Agent | `AGENTS.md`, `.codex/config.toml`, `.codex/agents/lead.toml` | Application source, rule/architecture specifications, and tests |
| Software Architect | `doc/architecture.md` | Application source, `doc/rules-spec.md`, tests, and agent configuration |
| Flames of War Rules Expert | `doc/rules-spec.md` | Application source, architecture specification, tests, and agent configuration |
| Python Developer | `app.py`, `src/fow_combat/**` | Rule/architecture specifications, tests, and agent configuration |
| Test & Math Verification Agent | `tests/**` | Application source, rule/architecture specifications, and agent configuration |

The `src/fow_combat/**`, `doc/architecture.md`, `doc/rules-spec.md`, and
`tests/**` paths are reserved ownership boundaries for future work; they do not
currently exist. The Lead Agent coordinates their creation when a user requests
work that requires them. For files outside these boundaries, the Lead Agent
assigns one owner before any edit. The Lead Agent does not edit application or
specialist-owned files to integrate work; it delegates those edits to the owner.

## Delegation workflow

1. The Lead Agent defines the requested outcome, scope, and whether edits or tests
   are authorized.
2. For rule-dependent work, ask the Rules Expert to write or update
   `doc/rules-spec.md`. The specification must distinguish verified rules,
   assumptions, and unresolved questions.
3. Ask the Architect to document boundaries in `doc/architecture.md` when a
   structural design decision is needed.
4. Give the Developer only accepted requirements and the relevant rule
   specification. The Developer may implement only behavior explicitly covered
   by that specification.
5. When the user requests tests or verification, ask the Test & Math Verification
   Agent to independently derive expected outcomes and own `tests/**`. It reports
   discrepancies to the Lead Agent and Developer; it does not patch production
   code.
6. The Lead Agent reviews the specialist reports, checks that their scopes did
   not overlap, resolves disagreements, and reports remaining uncertainty.

