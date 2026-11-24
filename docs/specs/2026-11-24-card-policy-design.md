# Card policy: filling rules in layers

Status: approved by the user on 2026-11-24 (three layers; the company profile only in the local
config; a project layer; `ws` writes labels, the original estimate and the "caused by" link; an
audit command that drafts what is missing).

## Problem

How a card is filled is a team rule: the title format, which labels a card carries, whether an
estimate is required, which sections the description has, what is filled when the card is done.
`ws card check` holds one set of these rules today, the user's own style, partly hard-coded in the
tracker adapter (`src/ws/tracker/jira/rules.py`: `_prefix_problem`, `_section_problems`) and in
`src/ws/tracker/vocab.py` (`_SECTIONS`). A company may set its own rules, and another company or
context others. The user keeps a default and switches by config.

## Layers

The merged policy is built from up to three files; each declares only what it changes, and the
more specific one wins.

1. **Default:** `src/ws/data/card-policy/default.toml`, in the repo. It states today's behaviour, so
   a user without the other layers sees no change.
2. **Company:** `~/.config/workspace/card-policies/<name>.toml`, chosen by `config.toml`:
   `[card] policy = "<name>"`. Never in the repo: a company name is a masked word there. A name
   that has no file is a config error (exit 2).
3. **Project:** `projects/<slug>/card-policy.toml`, optional. The project of a draft is the
   project of its `item` key; otherwise the project whose `project.toml` lists the card's epic;
   otherwise none.

Merge: tables merge key by key and the later layer wins; a list or a scalar is replaced whole.
`ws card policy [--project SLUG]` prints the merged policy as JSON (contract `card-policy` v1)
with `sources`: for each top-level key, the layer that set it.

## Contract `card-policy` v1

Files are TOML and map 1:1 to the JSON the command prints. Unknown keys are an error.

```toml
version = 1

[title]
# "epic_prefix": "[PREFIX] text", PREFIX = the epic's prefix (today's rule).
# "subgroup": "[group] - text"; the group is free text, 1 to 60 characters, no brackets.
format = "epic_prefix"

[sections.task]          # one table per type: task, bug, hotfix, improvement, feature, epic, initiative
required = ["Contexto", "Pronto quando"]
optional = ["Desenho combinado", "A fazer antes de implementar"]   # advisory, listed by `policy`

[create]
require = ["epic"]       # any of: epic, due, estimate, assignee, reporter, categories
due_with_sprint = true   # today's rule: a due date is required when the card goes into a sprint

[estimate]
padding_percent = 0      # > 0: the preview adds one advisory line, never a refusal

[categories.label]       # a group of labels; a card carries at most one value of each group
values = ["a", "b"]
required = true          # with create.require "categories": exactly one value on a new card
skip_when = []           # values of other groups that exempt the card from this group

[categories.tag]
values = ["X", "Y", "Z"]
required = true
skip_when = ["a"]
derive = { from = "estimate", threshold_hours = 6, above = "X", at_most = "Y", keep = ["Z"] }
# derive: the audit proposes the value from the estimate; a value in `keep` is never replaced;
# the check refuses a derived value that contradicts the estimate (e.g. "Y" with 10h).

[epic]
skip_when = []           # cards carrying one of these labels have no epic

[finish]
require = []             # any of: start, time_spent. Checked on a move to done and by the audit

[links.bug]
caused_by = "off"        # "off" | "suggest": the audit lists a bug without a caused_by link
```

## Where the policy applies

- `ws card check` and `preview`: the merged policy of the draft's project.
  - create: title format, sections of the type, `create.require`, categories, `epic.skip_when`;
  - edit: title format when the title changes, categories when labels change, the derived value
    when labels or the estimate change;
  - move to done: `finish.require` (the start date already set or set by the same batch; time
    spent above zero or a worklog in the same batch).
- `ws card audit`: reads cards (`--sprint active|next|<name>`, `--who me|dev-…`, repeatable,
  `--keys`) and reports, per card, the gaps against the create rules, and against the finish rules
  for done cards. Output JSON: `{cards: [{ref, title, gaps: [{rule, field, detail, fix}]}]}`;
  `fix` is `{"value": …}` when computed (a derived category) or `{"needs": "input"}`.
  `--drafts DIR` writes one `edit` draft per card with every computed value and lists in
  `need_input` what only a person or the model can give (estimate, subgroup title, label,
  sections, time spent). It never writes to the tracker.
- The writability rule does not change: only cards where the user is the assignee or the reporter
  (ADR 0009).

## Tracker side

- Draft keys: `labels` (create, a list); `add_labels`, `remove_labels` (edit, lists; never a
  replace of the whole list); `estimate` (create and edit, `10h`, `2h 30m`, same parser as the
  worklog `time`).
- Link kind `caused_by` (the draft's card is caused by the listed cards), with the opposite
  `causes`; `[tracker.<kind>.links] causes = "<link type name>"` maps it. Same direction handling
  as `blocks` and `blocked_by`.
- When the tracker cannot set the estimate on create (field not on the create screen), the writer
  sends it as a second request right after the create, under the same approval, as a move sends
  the start date.
- Reads: a card also carries its labels, original estimate, time spent and creation date; a card
  query can select by sprint and by assignee.
- Preview lines in PT-BR: `Categorias: + a, - b`, `Estimativa original: 10h`.

## Out of scope

Story points, the resolution date (the tracker sets it), discovering category values from the
tracker.
