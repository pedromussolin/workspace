# Daily by period

Used when the user asks for a period instead of the single day ("daily da semana passada", "resumo
de outubro", "o que fiz de 20/10 a 31/10", "texto para o gestor", "para a 1:1"). The single-day steps
of `SKILL.md` do not run; the daily's rules hold (see the end). The text is PT-BR, these instructions
are English. Nothing is written anywhere except the working files.

Working files go in `~/.local/share/workspace/standup/`; run
`mkdir -p ~/.local/share/workspace/standup` first and always use full paths.

## Steps

1. **Period.** Run `ws standup period "<the user's words>"`. It prints `since`, `until`, `label`,
   `workdays` and `warnings`. Exit 2 lists the accepted forms: say so and ask which period. When the
   label shows a year or a clip you inferred (a month without a year, an end after today, a
   `warnings` entry), show the label to the user before going on.
2. **Activity.** Run
   `ws standup collect --since <since> --until <until> > ~/.local/share/workspace/standup/activity-period.json`.
   If it fails, say so and stop.
3. **Cards**, as in the daily: remove any old `cards.json` and `cards.json.tmp`, run
   `ws task list --since <since> > ~/.local/share/workspace/standup/cards.json.tmp`, and only on
   exit 0 `mv` it to `cards.json`. On exit 1 or 2 use the tracker MCP fallback of step 3 of
   `SKILL.md`, following `references/<kind>.md` (the cards carry `status_changed` and `resolved`
   too). With no cards, go on without `--cards`. The board, the observations and the homologation
   question belong to the single-day daily and do not run here.
4. **Summary.** Run
   `ws standup summary --activity ~/.local/share/workspace/standup/activity-period.json --cards ~/.local/share/workspace/standup/cards.json --top 3`
   (without the `--cards` part when there are no cards; without `--top 3` in the detailed text).
   If the run with `--cards` fails, run it again without `--cards`, write from that summary and add
   the first run's stderr to the final warnings line. If the run without `--cards` fails, say so
   with its stderr and stop. It prints one JSON: `window`, `tracker`, `status_as_of`, `themes` (each
   with `key`, `title`, `tasks`, `more`), `blockers`, `keyless`, `totals` and `warnings`.
5. **Write** from the summary only, in the output asked for (below).

## Outputs

The default is the per-task summary. The text for a manager or 1:1 comes when asked ("texto para o
gestor", "para a 1:1"); "os dois" writes both. Hours per card are not an output.

### Resumo por tarefa (default, about 200 words)

```text
**Resumo: <label>**

**<Theme title>**
- <Task in a few words>: <outcome in plain words> (<KEY>)
- E mais <more> tarefas.

**Sem épico**
- ...

**Impedimentos**
- <Task in a few words>: bloqueado (<KEY>)
- <Task in a few words>: sem avanço desde <dd/mm> (<KEY>)
Algum desses é impedimento?

---
Para você: status de hoje, não do fim do período; Tracker indisponível; N avisos, peça "detalhado"
```

- One block per theme, in the order of `themes`; one line per task in `tasks`. "E mais N tarefas."
  (singular "E mais 1 tarefa.") only when the theme's `more` is above 0.
- The outcome in plain words, from `outcome`: `production` "entregue em produção",
  `homologation` "em homologação", `review` "em revisão", `done_without_pr` "concluída",
  `in_progress` "em andamento"; `null` says only what moved, from `subjects`. Never state more than
  the `evidence` supports.
- A theme titled "Sem épico" goes last; with no tracker (`tracker` false) every task is there and is named
  by its key and PR wording.
- **Impedimentos:** as in the daily: `kind: "blocked"` is confirmed ("bloqueado"), `kind: "stuck"`
  reads "sem avanço desde <dd/mm>" from its `updated` and gets the question "Algum desses é
  impedimento?" once; with none, "Nenhum." and no question. At most 3 lines, then "E mais N.".
- The note after `---` says that statuses are today's (`status_as_of`), not the period's; add
  "Tracker indisponível" when `tracker` is false and "N avisos, peça \"detalhado\"" when `warnings` is not
  empty. The note is always present in a period summary because of the first item.

### Detailed (on request: "detalhado")

Run step 4 without `--top`. Every task of every theme, one line each: the key, the title, what moved
(from `subjects`, `first_day` to `last_day`, `active_days`), the PRs in words (delivered, in review,
in homologation; no number or repo), and the `evidence` of the outcome in plain words. Then the
commits without a key in one line ("N commits sem card em <repos>", from `keyless`), the blockers as
above, and the same note.

### Texto para gestor ou 1:1

Plain PT-BR prose, one paragraph per theme (the epic title in bold), no bullets:
- what was delivered (`production`, then `homologation`), with the keys in parentheses;
- what is in review or in progress, in one short sentence;
- the blockers of that theme, when any.

A `stuck` card is a question to the user ("TS-123 está sem avanço desde 28/10: é um impedimento?")
before it is called a blocker in the text; a `blocked` card is already confirmed. Close with one
sentence on the whole period (`totals`: tasks, PRs merged), only with numbers the summary has. "Sem
épico" tasks go in a final paragraph. About 150 to 250 words for 5 themes; shorter with fewer.

The text is written to be pasted as it is: nothing about the person or this conversation, no
"Para você" inside it. The note for the user (statuses are today's, warnings) goes after a `---`
line, outside the text, as in the short summary.

## Rules

- Write only from the summary. Do not guess a status, a date, an outcome or a link between a commit
  and a card.
- Describe the task, never the person: no first person ("fiz", "entreguei") and no second person.
- No sha, PR number, repo, branch or jargon in the short text and in the manager text.
- Never call a write tool of the tracker, GitHub or git. The skill only reads and writes nothing.
- The status of a card is today's. Never say a task "was in validation during the week".
