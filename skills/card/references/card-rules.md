# Card rules

How a card is shaped: where it goes, what type it is, how big, how it links, who owns it and how
the text is written. Read by `/card` and by the `task-shaping` skill. The words are neutral
(tracker-independent); the PT-BR label is what the user sees. Rules marked **[code]** are also
refused by `ws card check` and `ws item check`, so a draft that breaks them never reaches the
approval.

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
  is its initiative.
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

A new card has no other type **[code]**; `epic` and `initiative` are for the levels above. A
time-boxed investigation is a `task` whose "Pronto quando" is a decision or a document.

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
- A link adds, never removes. Both cards must exist, so a card created in the same batch is linked
  in a later run, once its key is known.

## 5. Findings during a task

What turns up while doing a card becomes a proposed card for the next sprint, not scope of the
current card, unless the user says to include it.

## 6. People

- `assignee` is who develops; `reporter` is who writes and follows. Both default to `me` in a draft.
- A draft may say `me` (the user who runs `ws`) or a dev id: `dev-` plus 10 hex characters, the
  start of the SHA-256 of the work e-mail, lowercased. Items in the repo never say `me`: the repo is
  shared with another developer, so they hold dev ids only **[code]**.
- `ws people me` prints the user's own dev id. `ws people add EMAIL` prints the config block to
  paste for a colleague (it needs `--account ID` when the tracker hides e-mails). A dev id missing
  from the config fails the check with that hint.
- A card is writable when the user is its assignee or its reporter **[code]**; anyone else's card is
  refused for every op, and the user does it by hand.

## 7. Sprint and due date

- No sprint unless the user asks: leave `sprint` out. The only value is `"active"` (the board's
  active sprint) **[code]**.
- `due` is optional without a sprint and required with one **[code]**. There is no start date at
  creation: it is set when the card moves to in progress.

## 8. Text

- Title `[PREFIX] text`, with the epic's prefix as `ws card epics` prints it. An epic's own title
  starts with its prefix **[code]**. One line, up to 255 characters.
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
