# Architecture decisions

One file per decision, named by a four-digit number in order and a short title
(`0001-record-architecture-decisions.md`). Why this folder exists:
[0001](0001-record-architecture-decisions.md). Each record has front matter with `status` and
`date`, then these sections:

- Context and Problem Statement;
- Considered Options, only when there were real options;
- Decision Outcome;
- Consequences, good and bad.

A record that a later one replaces keeps its file; its status becomes `superseded by` and the
number of the new record.

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Architecture decision records | accepted | 2026-11-16 |
| [0002](0002-provider-agnostic-ports-and-adapters.md) | Provider-agnostic ports and adapters | accepted | 2026-11-13 |
| [0003](0003-versioned-json-contracts.md) | Versioned JSON contracts between ports | accepted | 2026-11-15 |
| [0004](0004-model-invocable-skills-behind-the-box.md) | Model-invocable skills behind the approval box | accepted | 2026-11-16 |
| [0005](0005-mcp-fallback-for-reads-only.md) | MCP fallback for reads only | accepted | 2026-11-16 |
| [0006](0006-script-first.md) | Script first | accepted | 2026-10-27 |
| [0007](0007-gate-threat-model.md) | Approval gate threat model | accepted | 2026-11-15 |
| [0008](0008-gate-denies-endless-waits.md) | Denied endless waits in the approval gate | accepted | 2026-11-16 |
| [0009](0009-tracker-writes-only-the-users-cards.md) | Tracker writes limited to the user's cards | accepted | 2026-10-27 |
| [0010](0010-epic-initiative-link-without-premium.md) | Epic-to-initiative link without the premium plan | accepted | 2026-11-16 |
| [0011](0011-epics-and-initiatives-outside-sprints.md) | Epics and initiatives outside sprints, with due dates | accepted | 2026-11-16 |
| [0012](0012-card-filling-rules-in-layers.md) | Card filling rules in layers | accepted | 2026-11-24 |

## Older rulings

Decisions taken while building each feature, before these records, stay in `docs/plans/` as
history, each with what it costs if wrong:

- [ws release](../plans/2026-11-13-release-rulings.md)
- [ws review pack](../plans/2026-11-15-card-review-rulings.md)
- [ws card start](../plans/2026-11-15-card-start-rulings.md)
- [ws observe](../plans/2026-11-15-observe-rulings.md)
- [tracker write port](../plans/2026-11-15-tracker-write-port-rulings.md)
