# Task items, card rules and a neutral tracker: design

Date: 2026-11-13. Status: written, builder-checked, waiting for the user's review.

## Goal

Every task in the workspace says, in fields a script can read, which card it is, its nature (card
type), its epic, who develops it (assignee) and who writes and follows it (reporter), and which
cards it depends on. `ws` writes those fields to the tracker the user configured, through the
`/card` preview and approval, and tells when the workspace and the tracker disagree. While the user
iterates on a task, Claude helps decide the task's nature, size and place by fixed rules, and
turns findings into cards for the next sprint instead of growing the current one. Skills and the
core speak a neutral vocabulary; Jira is one adapter.

## Why now (checked on 2026-11-13)

- Management asked for sprints with closed scope (2026-11-13). The first planning is on Monday,
  2026-11-16. Before it, the board must be organized: cards and epics created, assigned and filled.
  Choosing the sprint is out of this work.
- The epic TS-5278 (Artemis V2) holds cards that exist only because a VM of automations is being
  switched off (its owner left the company). The scope of each epic is blurred.
- The workspace repo is shared with another developer: nothing in the repo or in the rules may
  depend on who runs `ws`.
- The user now writes and follows another developer's cards (reporter = the user, assignee = the
  other developer). `ws card` only writes cards assigned to the user, always creates the type
  Tarefa, always assigns the user and always needs a sprint. It cannot create links or epics.
- Nothing compares the workspace with the tracker. Task tables carry card keys by hand; the 31
  cards of the VM screens work have no card; several statuses are behind the real state.
- `ws card` is Jira-specific (the 2026-10-27 design postponed the neutral version "until a second
  platform arrives"). D15 (2026-11-07) put the core behind ports with one adapter per external
  system. The user asked, on 2026-11-13, for skills that do not depend on Jira, with the tracker
  chosen in the config.

Facts of the Jira site, read on 2026-11-13 (REST, read only):

- Issue type ids: Epic 10000, História 10001, Tarefa 10002, Subtarefa 10003, Bug 10004, Melhoria
  10010, Nova função 10011, Service Request 10101, HotFix 10128, Iniciativa 10136 (level 2). JQL
  does not resolve the name "Iniciativa"; ids are needed.
- Link types: "Blocks" (blocks / is blocked by), "Relates" (relates to).
- The user has the permissions Modify Reporter, Link Issues, Edit, Assign, Create and Move.
- Create screen of Tarefa, Nova função and HotFix: `parent`, `reporter` (required), `assignee`,
  `duedate`. Edit screen of a card: `parent`, `reporter`, `issuetype` (allowed: Bug, HotFix,
  Melhoria, Tarefa, Nova função, Epic, Iniciativa, Service Request, História).
- **The Epic has no `parent` on its create or edit screen.** An epic cannot be put under an
  Iniciativa through the API; it is done by hand in Jira (or an admin adds the field to the
  screen). TS-5645 itself was converted to Iniciativa by hand.

## Decisions (user, 2026-11-13)

1. **Hierarchy.** Initiative > epic > card. TS-5645 is now the Iniciativa "[MIGRAÇÃO VM] Migração
   VM Frankl". Under it, two new epics we create: "Telas e scripts" (the other developer
   develops, the user is the reporter) and "Fechamento dos lotes do ML fora da VM" (the user's).
   A third epic, "Entrada das liquidações do ML na cessão", belongs to a third developer, who
   creates and manages it; we create nothing there. The Artemis epic keeps the batch-closing
   work; the VM epics hold the migrate and switch-off cards, linked to the Artemis cards.
2. **Type by nature**, not always Tarefa (rules below).
3. **Assignee and reporter are separate.** The user is the reporter of the other developer's cards,
   writes them and follows them.
4. **No sprint now.** Cards are created without a sprint.
5. **Approach 1** (below): one item file per card, with fields at the top.
6. **Order:** the board map first (a draft outside the repo, done), then the format and `ws`, then
   the workspace converted by script, then the tracker, then the other developer's cards.
7. **The rules live in a skill**, so Claude applies them while the user iterates on a task, not only
   when `/card` runs.
8. **Tracker-neutral.** Skills, items and the core use neutral terms; the config says which tracker
   the user works in; each tracker is an adapter. Only the Jira adapter is built now.
9. **Scope of the reorganization.** Only cards in the current work: the old epics in the backlog
   (and their cards) stay as they are for now. The type changes only on open cards; done cards
   keep their type. Cards the other developer reported get the user as reporter, by hand in the tracker (four
   cards).

## Approaches considered

1. **Item file per card with fields at the top (chosen).** D18 (task = card) and the recommended P10
   (type, epic and status as fields) applied now, without waiting for the new base (P15). Cost:
   convert the current files by script and grow `ws`.
2. **One index per project.** Files stay as they are; an index links task, card and fields. Two
   places to keep; the index drifts.
3. **Only extend `/card`.** Fast; nothing tells when the workspace and the tracker disagree, which
   is the problem that started this.

## Neutral vocabulary

| Neutral (files, config, code) | PT-BR (skills' text to the user) | Jira adapter |
|---|---|---|
| `initiative`, `epic`, `card` (levels 2, 1, 0) | iniciativa, épico, card | hierarchy levels |
| `task`, `bug`, `hotfix`, `improvement`, `feature` | Tarefa, Bug, HotFix, Melhoria, Nova função | issue type ids from `[jira.types]` |
| `blocks`, `blocked_by`, `relates` | bloqueia, é bloqueado por, relaciona | link type names from `[jira.links]` |
| `assignee`, `reporter` | responsável, relator | accountIds from `[people."dev-…"]` |
| statuses of `ws.taskmodel.Status` | a fazer, em andamento... | `status_overrides`, as today |
| `card` (an item field) | card | the issue key |

## The rules of a card (one file, two skills)

`skills/card/references/card-rules.md`, read by the new `task-shaping` skill and by `/card`.
Neutral words only. What can be checked in code is also in `ws card check` and `ws item check`
(marked **[code]**).

1. **Place.**
   - An initiative is an objective that crosses systems (switch off the VM). It has no cards of its
     own, only epics **[code: a card's parent is an epic]**.
   - An epic is one system or one objective inside an initiative, and closes when done.
   - A card has exactly one epic. The epic is the system the code changes, unless the card exists
     only to migrate or switch something off: then it goes to the initiative's epic and links to
     the system's cards. A card that serves another epic is linked, never duplicated.
2. **Nature (type).** Ask in this order:

   | Question | Type |
   |---|---|
   | Is something behaving wrong in production, with evidence? | `bug` |
   | ...and the fix cannot wait for the release? | `hotfix` |
   | Is it product code that changes something that exists and works (performance, log, screen)? | `improvement` |
   | Is it product code for something that does not exist? | `feature` |
   | Is it not product code (survey, specification, decision, switching a job off, data migration, documentation, cleanup script)? | `task` |

   No other type for a new card **[code]**. A time-boxed investigation is a `task` whose "Pronto
   quando" is a decision or a document.
3. **Size.** A card fits one sprint: at most about five working days with AI, and one checkable
   "Pronto quando". Bigger work is split by delivery that can be validated alone, not by layer; one
   card may span cessão, BFF and front when it is one delivery (same task ID in each repo's branch).
4. **Links.** `blocks` when a card cannot finish without the other; `relates` only for context
   **[code: only these]**.
5. **Findings during a task** become a proposed card for the next sprint, not scope of the current
   card, unless the user says to include it.
6. **People.** Assignee = who develops. Reporter = who writes and follows. Because the repo is
   shared with another developer, items name people by dev id (below), never `me`; only a local
   card draft may say `me` (the user who runs `ws`) **[code]**.
7. **Text.** Title `[PREFIX] text` with the epic's prefix **[code]**. Card text talks only about the
   task, never about the user, the AI or the conversation. Sections by type **[code]**:

   | Type | Required sections |
   |---|---|
   | all | `## Contexto`, `## Pronto quando` |
   | `bug`, `hotfix` | also `## Como reproduzir` and `## Evidência` (log, trace or query result, no customer data) |
   | `hotfix` | also `## Por que não espera a release` |

   `## Desenho combinado` and `## A fazer antes de implementar` stay optional.

## The item file

A Markdown file under `projects/<slug>/tasks/` that starts with a TOML front matter between `+++`
lines. A file under `tasks/` without front matter is a document (analysis, plan, survey); an item
lists its documents.

```text
+++
card = "TS-5570"
type = "feature"
epic = "TS-5278"
assignee = "me"
reporter = "me"
blocks = ["TS-5701"]
blocked_by = ["TS-5569", "tasks/13-plan-ts-5567.md"]
relates = []
docs = ["13-plan-ts-5570.md", "13-closing-design.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-20
sprint = ""
synced = 2026-11-13
+++
# 13 — Fechamento automático por horário por produto

(free text of the workspace, as today)
```

- **Contract fields** (top level), written by people and the model, sent to the tracker by `/card`:
  `card` (absent until the card exists; written back by `ws card apply`); `type`; `epic` (one of
  the project's epics); `assignee` and `reporter` (dev ids; `me` is refused in an item, since it
  would mean whoever runs `ws`); `blocks`, `blocked_by`,
  `relates` (card refs or item paths relative to the project; a path resolves to that item's
  `card`; a link to an item with no card yet waits); `docs` (paths relative to `tasks/`, each must
  exist); `tracker = false` for a task that never has a card (personal tooling, a done task kept as
  history), which then needs a top-level `status` and has no `[tracker]` table.
- **`repos`** (optional list of repo names): where `ws card start` makes the task's branches; `[]`
  means none. See `2026-11-15-card-start-design.md`.
- **After the adoption, the item is the source of the contract fields.** When the tracker differs,
  `ws item check --tracker` shows both values; the user says which side is right; `ws item drafts`
  sends the item's value, `ws item pull` copies the tracker's value into the item.
- **The `[tracker]` table** is a cache only `ws item sync` writes (status, priority, due date,
  sprint name, day of the sync); informational, the tracker wins. People and the model never edit
  it.
- **No title field.** The item's `#` heading is its workspace name, masked like the rest of the
  repo. The card title lives in the tracker with real names, written by the model in the card draft
  (outside the repo).
- **`project.toml`** in each project folder: `epics = ["TS-5278"]` (the epics whose cards belong to
  the project), optional `initiative`, and `prefixes` (epic → title prefix) when an epic's title has
  none. A project may hold several epics (D18).

## The config (local, outside the repo)

```toml
[tracker]
kind = "jira"                 # the adapter; absent with a [jira] table = "jira"

[jira]                        # the Jira adapter's own table, as today
site = "https://<site>.atlassian.net"
email = "..."
project = "TS"
board_id = 358
start_date_field = "customfield_10015"
sprint_field = "customfield_10020"

[jira.types]                  # neutral type -> issue type id; replaces [jira] issue_type
task = "10002"
bug = "10004"
hotfix = "10128"
improvement = "10010"
feature = "10011"
epic = "10000"
initiative = "10136"

[jira.links]
blocks = "Blocks"
relates = "Relates"

[identity]
email = "..."                 # the user's work e-mail; absent = [jira] email

[people."dev-3f9a2c7b1e"]     # another developer, by dev id
jira = "712020:..."           # this person's id in each tracker
label = "ana"                 # optional, shown only in the terminal; never written to the repo
```

**Dev ids.** A person is represented in the repo by a dev id: `dev-` followed by the first 10 hex
characters of the SHA-256 of the work e-mail, trimmed and lowercased. Every developer computes the
same id for the same person with nothing to agree on; the repo holds no name, no analog and no
e-mail. `ws people me` prints the user's own id (from `[identity] email`). `ws people add EMAIL
[--account ID]` computes the id, finds the person's account in the tracker by e-mail (`--account`
when the tracker hides e-mails) and prints the `[people."dev-…"]` block to paste; the e-mail is not
stored. The user's own id needs no `[people]` entry: the tracker says who the user is. In the
terminal, `ws` shows the tracker's display name (or `label`) next to a dev id; in the repo, only
the id.

`me` is accepted in card drafts (local) and refused in items. A dev id missing from the config,
or without an id for the configured tracker, fails the check with the `ws people add` hint.
Without `[jira.types]`, `ws card` exits 2 and prints the block to paste.
`ws tracker discover` (read only) prints the types and link types of the configured project in this
format, so nothing is typed by hand.

## The tracker port

`ws.tracker` defines the port (a `Protocol`) and the neutral `Card` (ref, title, type, level, parent,
assignee, reporter, status, due, priority, sprint, links). The core (rules, items, skills' commands)
depends only on it; `ws.tracker.jira` is the adapter, built from today's `jira.py`, `card.py` and
`cardrules.py`. A fake adapter serves the tests.

The port gives: who the user is; read cards by ref and by filter (assignee, reporter, parent in);
plan an operation (create, edit, move, comment, worklog, link) into the adapter's requests and its
preview lines; send a plan; and **capabilities**: `worklog`, `sprint`, `start_date`, `initiative`,
`epic_parent` (false in this Jira, see the facts), `set_reporter`, `change_type`, `link_types`. An
operation that needs a capability the adapter lacks is refused by the check, with what to do by
hand (for the epic's parent: "ligar o épico TS-… à iniciativa TS-5645 no Jira, à mão").

Tracker-specific checks stay in the adapter (transition matching, allowed priorities, the ADF
conversion). Neutral rules stay in the core (types, sections, prefix, who can be written, due and
sprint, links).

## Whose cards `ws` writes

A card is writable when the user is its assignee or its reporter. One rule for every op; the
reporter is fetched for every op. Anyone else's card is refused, in code. The rule depends only on
the card, never on a local list of people, so it is the same for every developer sharing the repo.
Cards the other developer reported before 2026-11-13 get the user as reporter by hand, once, in
the tracker. `ws task list` keeps `mine` = assignee only (the daily does not change).

## `ws card` changes

- **`create`** gains `type` (required; the five types plus `epic` and `initiative`), `assignee` and
  `reporter` (`me` or dev ids, default `me`), `sprint` (optional: absent = none; `"active"` = the board's
  active sprint with today's checks; replaces the 2026-10-27 "every card is born with a sprint"),
  `due` optional when there is no sprint, and `item` (the item's path in the repo). An epic:
  title must start with `[PREFIX] `, only `## Contexto` required; its initiative is set by hand
  when the adapter lacks `epic_parent` (the preview says so). An initiative: no parent.
- **Write-back.** After a successful create with `item`, `apply` writes `card = "<ref>"` into the
  item's front matter (that line only, or inserted as the first key; the rest byte for byte). When
  the front matter no longer parses or already has another `card`, `apply` leaves the item alone,
  finishes the batch, exits 1, prints ref and path, and records the pair under
  `~/.local/share/workspace/cards/uncertain/`. `ws item drafts` refuses to draft a create for an
  item recorded there until `ws item set-card <item> <ref>` writes it and clears the record.
- **`edit`** gains `type`, `assignee`, `reporter` and `parent`. When the tracker refuses a type
  change, the message says to do it by hand (Jira: "Mover").
- **New op `link`**: `key` plus any of `blocks`, `blocked_by`, `relates`. Adds only missing links;
  an existing one shows as "já existe"; never removes. Both cards in the project; at least one
  writable. Links to cards created in the same batch are not resolved: they go in a later run,
  once the refs exist.
- **`ws card epics`** also lists the epics of the user's initiatives and those where the user is
  assignee or reporter.

## New `ws item` commands

All read the items of the given projects (default: every project with a `project.toml`).

- **`ws item new <project> --type T --epic K [--assignee A] [--reporter R] --heading "..."`**: writes
  `tasks/NN-<slug>.md` (next free `NN`) with the front matter and the sections of
  `templates/item/<type>.md`.
- **`ws item check [projects] [--tracker]`**: offline, the schema (unknown keys, types, dev ids,
  epic in `project.toml`, documents exist, link paths resolve, `tracker = false` has a status). With
  `--tracker`: the card exists and is in the project; type, parent, assignee and reporter match;
  every link exists; and `orphans`, the writable cards of the project's epics that no item points
  to (report only). JSON with `problems`, `drift` (both values), `pending` and `orphans`; exit 1 on
  problems.
- **`ws item drafts [projects] [--only REFS]`**: for confirmed drift, `edit` drafts; for missing
  links whose refs exist, `link` drafts; for an item with no card, a `create` draft with the fields
  filled and an empty body the model must write (`ws card check` fails until it does). Into a new
  folder of `~/.local/share/workspace/cards/drafts/`; prints `{"folder", "count", "need_text"}`.
  Then `/card` previews and applies the folder as today.
- **`ws item pull <item> --fields F,...`**: copies the tracker's values of those contract fields
  into the item.
- **`ws item sync [projects]`**: rewrites only the `[tracker]` table of each item with a card.
- **`ws item table <project>`**: rewrites the `README.md` task table between `<!-- ws:items -->` and
  `<!-- /ws:items -->`: number, heading (link), card, type, assignee dev id, cached status.

`ws task list` gains `--role mine|following|all`; `following` = cards where the user is the reporter
and someone else the assignee, each with its assignee's display name.

## Skills

Neutral words; the tracker's name comes from `ws` output, never hard-coded.

- **New `task-shaping`** (model-invoked; writes only item files, never the tracker). Description:
  helps decide a task's nature (card type), size, epic, people and links, splits work that does not
  fit a sprint, and turns findings made during a task into proposed cards for the next sprint; use
  when the user plans, scopes or iterates on a task, or a finding appears mid-task. Steps: read the
  item and `card-rules.md`; propose type, epic, size (split or not) and links, one-line reason
  each; on the user's yes, write with `ws item new` or edit the front matter; `ws item check`;
  offer `/card`. A proposed card for the next sprint is a new item, never extra scope.
- **`/card`**: the new keys and `link`; points to `card-rules.md`; a "Reorganize" flow:
  `ws item check --tracker`, show the drift and ask which side is right per field, `ws item pull`
  or `ws item drafts`, write the bodies in `need_text`, one preview, one approval; after the apply,
  `ws item sync` and `ws item table`.
- **`checkpoint`**: `ws item check` (offline) before committing.
- **`daily`**: unchanged.

## Converting the workspace

Input: the board map, `~/.local/share/workspace/projects/workspace/board-map/*.tsv` (outside the
repo, real names), after the user's review. Columns, tab-separated, header first:
`project file card action type epic title assignee reporter links status scope done_when notes`
(the VM screens file adds `estimate_ai_days` before `notes`).
- `card`: a ref, `novo-<id>` (a card to create; links may point to these ids) or `-`;
- `action`: `manter`, `mover-epico`, `retipar`, `editar`, `criar`, `vincular`, `fechar`, `sem-card`,
  `perguntar` (must be resolved before the script runs);
- `type`: the tracker's type name (mapped to the neutral type by `[jira.types]`);
- `links`: `blocks:X;blocked_by:Y;relates:Z`.

`scripts/adopt-items.py`, one-off:
- for each row with a file: inserts the front matter, never touching the body;
- for each row of a card with no file: creates the item (`ws item new`), heading masked by
  `ws mask`;
- writes `project.toml` for each project;
- moves files between projects with `git mv` when the map says so and rewrites the relative links
  in the moved files and in the files pointing to them;
- renames `projects/operations-screens-migration/` to `projects/vm-migration/` (one project for the
  initiative and its epics, D18). The folders outside the repo with the same slug
  (`~/.config/workspace/private/<slug>.md`, `~/.local/share/workspace/projects/<slug>/`) are only
  printed as commands, run with `--outside`;
- then `ws item check` (offline) must pass; the user reviews the diff before the commit.

## Applying to the tracker

Through `/card` only, each step one preview and one approval: create the two epics (and link
each to TS-5645 by hand); move and edit the existing cards; create the new cards (the user's
first, then the other developer's); a second `ws item drafts` run for the links. Then `ws item
sync`, `ws item table`, and `ws item check --tracker` must report no problems.

## Tests (pytest, fake tracker and fake Jira server, no real Jira)

- Items: the fields, unknown keys, dev ids, link paths, `tracker = false`, a broken `[tracker]`
  table; `sync`, `pull` and the write-back keep every other byte.
- Port: the core runs against the fake adapter; refusals for missing capabilities.
- Jira adapter: types by id; sprint absent and `"active"`; due optional only without sprint; epic
  and initiative creation, with the epic parent refused by capability; the writable rule (assignee,
  reporter, anyone else refused); `link` adds only missing links; a refused type change
  gives the "Mover" message; the write-back failure path and `set-card`.
- `ws item check --tracker`: each drift kind, orphans, pending links. `ws item table`: text outside
  the markers unchanged. `adopt-items.py`: a small fake project, a move with link rewrites.

## Out of scope

- Adapters other than Jira (GitHub Issues, Monday): only the port is shaped for them.
- One tracker per project or per space (P15): one tracker per config for now.
- Choosing sprints; any sprint write beyond `sprint = "active"`.
- A "following" section in the daily.
- Removing links, deleting cards, moving cards across tracker projects.
- The new base of P14 and P15: when it comes, items move by script; these fields are its first
  version.
- A reverse mask to send the item's text as the card's text.

## Left to the builder

Module names inside `ws.tracker`, JSON shapes, exact flags, the PT-BR messages, the
`templates/item/` wording, and how today's `card.py` and `cardrules.py` split between core and
adapter, following the rules above.
