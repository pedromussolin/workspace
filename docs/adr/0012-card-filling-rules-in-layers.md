---
status: accepted
date: 2026-11-24
---

# Card filling rules in layers

## Context and Problem Statement

How a card is filled is a team rule: the title format, the labels a card carries, whether an
estimate is required, which sections the description has, what is filled when the card is done.
`ws card check` held one set of these rules, the user's own style, partly written in the tracker
adapter. A company may set other rules, and another company or project others again, while the
user keeps a default and switches by config. A company name is a masked word in this repo, so a
company's rules cannot be committed here.

## Decision Outcome

The rules are data, the contract `card-policy` v1, merged from up to three TOML layers; each layer
declares only what it changes and the more specific one wins (tables merge key by key, a list or a
scalar is replaced whole):

1. the default, in the repo (`src/ws/data/card-policy/default.toml`), which states the user's own
   style, so a user with no other layer sees no change;
2. the company layer, `~/.config/workspace/card-policies/<name>.toml`, chosen by `[card] policy`
   in `config.toml`, and only in the local config: it never enters the repo. A name with no file is
   a setup error (exit 2);
3. the project layer, `projects/<slug>/card-policy.toml`, optional. The project of a draft is the
   project of its `item`, else the one whose `project.toml` lists the card's epic.

`ws card check` and `preview` apply the merged policy of the draft's project; `ws card policy`
prints it for people and for the skill, which writes drafts that follow it. The writability rule
does not change ([0009](0009-tracker-writes-only-the-users-cards.md)).

## Consequences

- Good: another company or project changes the rules by a file, not by code; the default keeps
  every message and result it had.
- Good: the company's rules stay outside the repo, with the masked names.
- Bad: three places can hold a rule, so `ws card policy` (with the layer of each key) is the way to
  see which one applies.
- Bad: a rule only a person knows (an estimate, a subgroup title) still needs asking; the policy
  refuses a draft without it, and does not invent it.
