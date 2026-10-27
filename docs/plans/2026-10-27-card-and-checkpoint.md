# Card write and checkpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** The `card` skill with `ws card` (spec `docs/specs/2026-10-27-card-write-design.md`) and
the `checkpoint` skill with `ws checkpoint` (spec `docs/specs/2026-10-27-checkpoint-design.md`).
The specs are the requirements; this plan splits the work and fixes the interfaces between tasks.

**Global Constraints:** standard library only, `uv` only, English names, PT-BR text for people,
every path from `ws.config`, no real names, company domains, site URL, account ids or field ids of
the real site in the repo (tests use `https://example.atlassian.net`, keys like `TS-101`, fake
account ids such as `acc-me`), commits PT-BR with a prefix and at most 72 characters, no trailers,
`uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` clean before each commit. No
test or command touches the real Jira, GitHub or the user's real config.

## Execution

| Task | Model | Effort | Depends on |
|---|---|---|---|
| A1 `ws.adf` converter | sonnet | medium | — |
| A2 `JiraClient` writes, config keys, `ws setup` ask rules | sonnet | medium | — |
| A3 `ws card` (draft, rules, check, epics, apply) | sonnet | high | A1, A2 merged |
| A4 the `card` skill, README, the daily's note | sonnet | low | — (writes against the spec) |
| C1 `ws checkpoint` | sonnet | medium | — |
| C2 the `checkpoint` skill, README | sonnet | low | — |
| Reviews | sonnet | medium (A3: high) | |
| Final review of the card part | opus | high | it writes outside (Jira) |
| Final review of the checkpoint part | sonnet | high | contained |

A1, A2, A4, C1 and C2 run in parallel (separate worktrees); A3 starts when A1 and A2 are on `main`.

## Interfaces fixed between tasks

- **A1** `src/ws/adf.py`: `to_adf(markdown: str) -> dict` (an ADF `doc`); `class AdfError(ValueError)`
  with `.line` (1-based) and a message naming the construct; `foreign_nodes(doc: dict) -> set[str]`,
  the node and mark types in a Jira document that `to_adf` cannot produce (for the `edit` rule).
- **A2** `src/ws/jira.py`: `JiraClient._request(method, path, body=None, query=None) -> dict | list | None`
  (JSON content type; 204 or empty body → `None`; Jira's `errorMessages`/`errors` in the message);
  `JiraError` gains `.status` (int, or `None` for a network error or timeout) and `.uncertain`
  (True for timeouts, connection errors and 5xx on a write); public helpers `get(path, query=None)`,
  `post(path, body)`, `put(path, body)`; `issue(key, fields: list[str]) -> dict`;
  `transitions(key) -> list[dict]` (with `expand=transitions.fields`);
  `active_sprints(board_id: int) -> list[dict]` (`GET /rest/agile/1.0/board/{id}/sprint?state=active`);
  `create_meta(project: str, issue_type: str) -> dict` (`GET /rest/api/3/issue/createmeta/{project}/issuetypes`,
  then the type by name, `.../issuetypes/{id}`: fields with `allowedValues`).
  `src/ws/userconfig.py`: `JiraConfig` gains `project: str | None`, `board_id: int | None`,
  `issue_type: str | None`, `start_date_field: str | None`, `sprint_field: str | None` (None when
  absent; wrong types → `ConfigInvalid`).
  `src/ws/bootstrap.py`: `ws setup` checks `~/.claude/settings.json` `permissions.ask` for
  `Bash(ws card apply:*)` and every entry of `ATLASSIAN_WRITE_TOOLS` (a constant listing, for the
  server prefixes `mcp__claude_ai_Atlassian_MCP__` and `mcp__plugin_productivity_atlassian__`, the
  tools `createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`, `addCommentToJiraIssue`,
  `addOrEditJiraIssueComment`, `addWorklogToJiraIssue`, `executeWrite`, `executeDestructive`);
  missing ones → one "needs you" line with the JSON to add (never edits the file).
- **A3** `src/ws/card.py` + `ws card check|epics|apply` in `cli.py`, exactly as the spec's
  "The commands", "The rules" and "The requests"; drafts under `data_dir()/cards/drafts`,
  pending under `data_dir()/cards/pending`, done under `data_dir()/cards/done`.
- **A4** `skills/card/SKILL.md` (`disable-model-invocation: true`) per the spec's "The skill
  `card`"; README: the `ws card` rows and the new `[jira]` keys in "Local config" (placeholders),
  a line that the API key must be an unscoped token, the `ask` rules `ws setup` asks for; the
  daily's "Para você:" note (`skills/daily/SKILL.md` and `references/detailed.md`) says
  "para aplicar: /card mover <KEY> para <status>; ...".
- **C1** `src/ws/checkpoint.py` + `ws checkpoint check|diff|commit` in `cli.py`, exactly as the
  spec; reuse `standup._section`; tests with throwaway repos and a bare remote.
- **C2** `skills/checkpoint/SKILL.md` per the spec's "The skill `checkpoint`" (model-invoked, the
  triggers listed there); README rows for `ws checkpoint`.

## Commits

A1 `feat: conversor de markdown para o documento do Jira`; A2 `feat: cliente do Jira escreve e
ws setup pede confirmação para escritas`; A3 `feat: ws card cria e atualiza cards com prévia e
aprovação`; A4 `feat: skill card e nota do daily para aplicar`; C1 `feat: ws checkpoint valida e
publica a pasta do projeto`; C2 `feat: skill checkpoint`.
