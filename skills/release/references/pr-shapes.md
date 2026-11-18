# PR drafts

One file per PR in `~/.local/share/workspace/projects/<slug>/release-YYYYMMDD/pr/`. `ws release
preview publish` checks every rule below (R6) and names the file that breaks one. Texts are PT-BR.

| File | PR |
|---|---|
| `<repo>.md` | the code PR, to `master` (production) |
| `<repo>-<env>.md` | the PR of an environment (`<repo>-sandbox.md`, `<repo>-staging.md`), only when it needs its own text |
| `<repo>-<env>-2.md`, `-3`, ... | later PRs of that environment, when the previous one is already merged and the branch grew |

## Front matter

TOML between two `+++` lines, then the body in Markdown.

```
+++
title = "release 20261120: <resumo>"
tasks = ["TS-101", "TS-102"]
labels = ["release"]
assignees = ["<github login>"]
+++
```

- `title` and `tasks` are required. `labels` and `assignees` are optional lists of strings. Any
  other key is refused.
- `tasks` must hold every task key the repo's include branches carry, and the body must link each
  one (`{tasks}` does it).

## Titles

| Shape | Title |
|---|---|
| multi-branch | `release YYYYMMDD: <resumo>`, no task key |
| single-branch | the task's normal title: `type(TS-N): <texto>` with `type` one of `feat`, `chore`, `refact`, `fix`, `test` |
| environment PR | the code PR's title with the suffix of the environment without its dash, in parentheses: ` (sdbx)`, ` (stg)`; at most 100 characters |

Without an environment file the PR of that environment takes the code PR's title and body: the
title gets the suffix, and the body gets a first paragraph saying that it takes the code to that
environment to validate before production (and what the copy adds over the code branch, when it
differs). Write `<repo>-<env>.md` only when that PR needs another text; its title must end with the
suffix of the environment.

## Placeholders

The script resolves them when it sends; a body with an unknown or unresolved one is refused.

| Placeholder | Becomes |
|---|---|
| `{pr:bff}`, `{pr:bff-sandbox}`, `{pr:bff-staging}` | `<org>/<repo>#N` of that PR, once it exists (the repo names are the keys of `repos`) |
| `{url:bff}`, `{num:bff}` | its URL; its number |
| `{tasks}` | the `tasks`, one line each: `- TS-101: <site>/browse/TS-101` |
| `{release_date}` | the release date as `DD/MM/YYYY` |

- Never write `<org>/<repo>#N` literally for a repo of the release: the number would go stale.
  Write `{pr:repo}`.
- A single-branch PR needs `{release_date}`: the script writes `Release: DD/MM/YYYY` as the first
  line of the body (the date is not in its title) and `move` changes that line.
- A reference to a PR created later (`{pr:front}` in the shared PR) is fixed in a second pass
  (`gh pr edit`) after every PR exists.

## Sections

Every `## ` heading of the repo's `.github/pull_request_template.md` must appear in the body, as a
line of its own. A repo with no template uses these four (shared and BFF PRs):

1. `## O que traz`: what changes, one item per task, from the task cards and the diff
2. `## Antes de subir`: what must exist before the deploy (Parameter Store, app roles, queues)
3. `## Ordem e efeitos`: the deploy order shared, BFF, front with `{pr:...}` links, and what each
   step does
4. `## Como validei`: the checks that were run, with their real results

The front template has seven, in this order: `## Tarefa`, `## O que muda`, `## Mudanças visíveis`
(a table of where, before, after, or "Nenhuma"), `## Dependências`, `## Como validei` (the
checklist; mark only what was run), `## O que não deu para exercitar`, `## Regra de manutenção`.
Fill every one; keep the template's own checklist lines.

Rules for the prose: short sentences; what a reader must do or check comes first; what could not be
exercised is said, never hidden; no number in "Como validei" that nobody measured.
