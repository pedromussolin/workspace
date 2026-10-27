# Detailed standup (PT-BR)

Used when the user asks for the detailed daily. Run step 4 without `--top`.

Every line describes the task, never the person: no first person ("fiz", "fechei") and no second person. Example: "Release do portal com permissões por área: PRs prontas para o deploy".

Use exactly these three headings, in this order:

```text
**Ontem**
- <KEY> — <title>: <one short line on what was done, from subjects and prs>. <suggestion>
- <N> commits sem card em <repos>

**Hoje**
- <KEY> — <title> (<status>): <next_step>. <suggestion>
- <project>: <next step text>

**Impedimentos**
- <KEY> — <title>: sem commit há pelo menos <workdays> dias úteis; card atualizado em <updated>.
Algum desses é impedimento?
```

- **Ontem:** one line per `yesterday` entry, in order, naming its key and `title` (omit " — <title>" when `title` is null); the short line
  is built from its `subjects` and `prs` (cite `ref` for a PR), never inventing what changed. The
  "N commits sem card em <repos>" line (`keyless.commits`, `keyless.repos`) only when
  `keyless.commits` is greater than 0. No topic without a key.
- **Hoje:** one line per `today` entry with its `status`; omit ": <next_step>" when it is null.
  Then one line per `next_steps` entry as "<project>: <text>".
- **Impedimentos:** one line per `blockers` entry, then the question "Algum desses é impedimento?"
  once. With none, write "Nenhum." and no question.
- `<suggestion>`: only when the entry's `suggestion` is not null, as "Sugestão: mover de <from>
  para <to> (<evidence>)"; nothing moved. Otherwise nothing.
- Status names in PT-BR, also for a suggestion's `from` and `to`: `todo` "a fazer", `in_progress` "em andamento", `validation` "em
  validação", `done` "concluída", `cancelled` "cancelada".
- `jira` false: start the text with "Jira indisponível: sem status nem títulos dos cards"; list
  the `yesterday` topics by key, with the PR title when there is one; under **Hoje** only the
  `next_steps`; under **Impedimentos** write "indisponível".
- Dates in the text are `dd/mm` (`blockers[].updated` is ISO in the report).
- End with every `warnings` entry, as it is.

