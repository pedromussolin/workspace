# Card rules

How a card is shaped: where it goes, what type it is, how big, how it links, who owns it and how
the text is written. Read by `/card` and by the `task-shaping` skill. The words are neutral
(tracker-independent); the PT-BR label is what the user sees. Rules marked **[code]** are also
refused by `ws card check`, so a draft that breaks them never reaches the approval (`ws item check`,
in the next plan, will refuse the same).

## Vocabulary

| Neutral key | PT-BR label |
|---|---|
| `task`, `bug`, `hotfix`, `improvement`, `feature` | Tarefa, Bug, HotFix, Melhoria, Nova função |
| `epic`, `initiative` (levels above a card) | Épico, Iniciativa |
| `blocks`, `blocked_by`, `relates` | bloqueia, é bloqueado por, relaciona-se com |
| `assignee`, `reporter` | responsável, relator |

## 1. Place

- An initiative is an objective that crosses systems (for example, switching a machine off). It has
  no cards of its own, only epics **[code: a card's parent is an epic]**.
- An epic is one system or one objective inside an initiative, and closes when done. Its `parent`
  is its initiative **[code: a level-2 card that is not done]**. The tracker may tie the two by a
  link instead of the parent field, as the config says: then `parent` on an epic edit adds that
  link and goes alone in its draft, and a create with `parent` is refused, so a new epic is created
  first and then edited with `parent` **[code]**. When the tie is the parent field and the
  tracker's epic screens have no `parent`, the check refuses it and the user links the epic to its
  initiative by hand.
- A card has exactly one epic **[code: `epic` is required for the five card types and refused for
  `epic` and `initiative`]**. The epic is the system the code changes. When the card exists only to
  migrate or switch something off, it goes to the initiative's epic and links to the system's cards.
- A card that serves another epic is linked to it, never duplicated.

## 2. Nature (type)

Ask in this order and stop at the first yes:

| Question | Type |
|---|---|
| Is something behaving wrong in production, with evidence? | `bug` |
| ...and the fix cannot wait for the release? | `hotfix` |
| Is it product code that changes something that exists and works (performance, log, screen)? | `improvement` |
| Is it product code for something that does not exist? | `feature` |
| Is it not product code (survey, specification, decision, switching a job off, data migration, documentation, cleanup script)? | `task` |

A new card has no other type **[code]**; `epic` and `initiative` are for the levels above. An edit
changes the type only between these five, on a card **[code]**: moving a card to or from epic or
initiative changes its level, and that is done by hand in the tracker. In an edit, `epic` is for a
card and `parent` for an epic, never both **[code]**. A time-boxed investigation is a `task` whose
"Pronto quando" is a decision or a document.

## 3. Size

A card fits one sprint: at most about five working days with AI, and one checkable "Pronto quando".
Bigger work is split by deliveries that can be validated alone, not by layer. One card may span
several repos when it is one delivery (the same task ID in each repo's branch).

## 4. Links

- `blocks`: the card cannot finish without the other one. `blocked_by` is the same fact seen from
  the other side. Pick one direction per pair.
- `relates`: only context.
- Only these three **[code]**. A card never links to itself, and the same card is never in `blocks`
  and `blocked_by` of one draft **[code]**.
- At least one of the two cards must be writable (section 6) **[code]**.
- A link already in the tracker is skipped; its opposite is refused **[code]**. In one batch, the same
  link twice (`A blocks B` and `B blocked_by A`, or `relates` both ways) or a link both ways is
  refused on the later draft **[code]**.
- A link adds, never removes. Both cards must exist, so a card created in the same batch is linked
  in a later run, once its key is known.

## 5. Findings during a task

What turns up while doing a card becomes a proposed card for the next sprint, not scope of the
current card, unless the user says to include it.

## 6. People

- `assignee` is who develops; `reporter` is who writes and follows. Both default to `me` in a draft.
- A draft may say `me` (the user who runs `ws`) or a dev id: `dev-` plus 10 hex characters, the
  start of the SHA-256 of the work e-mail, trimmed and lowercased. Items in the repo never say `me`:
  the repo is shared with another developer, so they hold dev ids only.
- `ws people me` prints the user's own dev id. `ws people add EMAIL` prints the config block to
  paste for a colleague (it needs `--account ID` when the tracker hides e-mails). A dev id missing
  from the config, or there without a tracker id, fails the check with that hint **[code]**.
- A card is writable when the user is its assignee or its reporter **[code]**; anyone else's card is
  refused for every op (a link needs one writable side), and the user does it by hand.
- A `reporter` the draft leaves out is not sent: the tracker makes the creator the reporter. What
  a create sets (title, description, priority, assignee, a written reporter, the epic, due date,
  sprint) must be on the type's create screen, and each field an edit changes on the card's edit
  screen **[code]**.

## 7. Sprint and due date

- No sprint unless the user asks: leave `sprint` out. Values: `"active"`, `"next"`, the exact name
  of an open sprint, or (edit only) `"backlog"` **[code]**.
- An epic or an initiative stays out of sprints: only its cards go into one, and it keeps its due
  date **[code]**. An edit with `"backlog"` takes it out of a sprint.
- `due` is optional without a sprint and required with one **[code]**. There is no start date at
  creation: it is set when the card moves to in progress.

## 8. Text

- Title `[PREFIX] text`, with the epic's prefix and a space, as `ws card epics` prints it
  **[code]**; an epic with no prefix takes any title. An epic's or an initiative's own title starts
  with `[PREFIX] ` (the brackets and a space), at create and at edit **[code]**. One line, up to
  255 characters **[code]**.
- The text talks only about the task: never the user, the AI, the conversation or agreements
  between them. Bad: "Validar a estrutura com <o usuário>." Good: "Validar a estrutura do
  documento." A person stays when the task depends on them.
- Plain PT-BR. Only headings, paragraphs, lists, fenced code, `**bold**`, `` `code` `` and links; no
  tables, quotes, images or HTML.
- Sections are level-2 headings written exactly like this **[code]**:

| Type | Required (not empty) |
|---|---|
| `task`, `improvement`, `feature` | `## Contexto`, `## Pronto quando` |
| `bug` | also `## Como reproduzir` and `## Evidência` (log, trace or query result, no customer data) |
| `hotfix` | the bug sections plus `## Por que não espera a release` |
| `epic`, `initiative` | `## Contexto` only |

`## Desenho combinado` and `## A fazer antes de implementar` are optional, only when there is
something to say.
