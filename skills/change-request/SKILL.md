---
name: change-request
description: Writes, fills in and reviews a GMUD (registro de mudança, change request) for a production deploy of the company repos (platform-cessao, apl-credit-whitelabel, apl-credit-whitelabel-api, argocd, data-lake-api, apl-shared-service), including retroactive ones for changes already in production. Use when the user asks to create, write, fill in or review a GMUD or change request.
---

# Change request (GMUD)

## Overview

A GMUD (Portuguese acronym for a change request) is the text the user pastes,
field by field, into the company's change tool. Every claim needs verifiable
evidence (commit, test, log, trace) and every field is short: the reader is
the person who approves the change, not the person who wrote it.

The GMUD text is written in PT-BR, because the form is. Field names and
fixed values below are quoted as they appear in the form; keep them in PT-BR.
Everything else in this skill is instructions for you, in English.

## Survey (before writing)

1. **Scope per repository:** `git log --all --grep TS-<id>` and the merge
   commits (a branch that is already merged leaves `origin/master..<branch>`
   empty); `git diff --stat` of each one. Look in every repo, argocd
   included. Also say what does **not** change.
2. **Where the change already is:** versions in Datadog show up as
   `sand-<sha>` / `prod-<sha>` (group by `@version`). Confirm with
   `git merge-base --is-ancestor <commit> <sha>`. Already in production means
   retroactive.
3. **Tests, run now** (commit + count). For platform-cessao use the Docker
   recipe in [references/tests.md](references/tests.md): worktree of the
   branch, in the background. If the tests cannot be run, report the date of
   the last run and do not present it as current.
4. **Execution evidence:**
   - Sandbox: the flow's event logs (`env:sandbox "<fixed message>"`) and
     route spans (`service`, `resource_name`, `@http.status_code`). Record
     UTC time, version, trace ids, status, durations.
   - If the change depends on configuration that exists only in production,
     or reached production before the sandbox, say so and use
     `env:production`.
5. **Operations check** (applies to every change with a worker, queue,
   variable or infra):
   - Who consumes each new queue **in production** (argocd values: does
     `CELERY_WORKER_QUEUES` fix the list?). No consumer means nothing runs.
   - Safe deploy order: image before the deployment that uses it; backend
     before front; what happens in each wrong order.
   - What happens to a task in progress during the deploy (does the process
     receive the shutdown signal? `acks_late`? grace period vs `time_limit`).
   - Where the new variables live (argocd or outside it). If not found, write
     "a confirmar" (to be confirmed); the rollback without a deploy depends
     on it.
   - Rollback: reverse order and what is left behind (Redis, queue, data).
6. **Check every claim in the code** in Risco, Impacto and Rollback (HTTP
   code, behavior without Redis/queue/worker, migration). No evidence means
   "a confirmar". For a large change, use an adversarial reviewer in
   parallel.

## Fields

| Field | Content |
|---|---|
| Tipo | `Mudança programada` or `Mudança não programada` (urgent or already executed) |
| Summary | `<product or screen>: <what changes for the people who use it>`, in plain PT-BR, up to ~80 characters; see "Summary" below |
| Descrição | **Contexto** (the problem, with production number, period and source) · **O que muda** (one item per repo) · **O que não muda** |
| Prioridade | `Low`, `Medium` or `High`; propose one and confirm with the user |
| Link Tarefa | `<link do Jira da TS-<id>>`; do not invent the domain |
| Risco | Level (`Baixo`/`Médio`/`Alto`) + items "o que pode dar errado → o que acontece → o que segura" (what can go wrong → what happens → what holds it) |
| Impacto | Screen/user · database · infra (pod, queue, Redis) · deploy: downtime, migration, new variable |
| Plano de implantação | Steps in the safe order (step 5), each with the concrete check (pod, queue consumer, expected log/trace, screen) |
| Plano de Rollback | Reverse order · option without a deploy, if one exists · drain queue/tasks before removing a worker · what is left behind |
| Evidências de validação | Tests (commit, count) · sandbox or production (UTC, versions, traces, status, durations) |

## Summary

The title is what the approver and the people affected see in the list of changes, often with
nothing else. Write it for them, not for the developer:
- Start with the product or the screen as people call it ("Portal de Crédito", "Envio de
  Relatórios", "Conciliação CERC"), then the effect in their words.
- No repo or service names, `TS-…`, PR, version, branch, variable or component jargon (BFF,
  shared, worker, endpoint). Those go in Descrição.
- A release with many changes: name the one or two that people will notice most.
- Propose the title with the fields; the user approves it like the rest.

| Bad | Good |
|---|---|
| `apl-shared-service, apl-credit-whitelabel-api e apl-credit-whitelabel: permissões por área no portal de crédito, com a troca dos grupos do Azure` | `Portal de Crédito: permissões por área e novo Controle de Acesso` |
| `data-lake-api: cache por dia em /registration/pending` | `Conciliação CERC: aba Pendências abre mais rápido` |

## Form rules

- Deliver every field ready to paste; if the user named specific fields,
  show those first.
- Short fields, one item per line; explain a technical term the first time
  it appears.
- No password, token, connection string, internal host or IP: name the
  variable.
- A problem the change causes or worsens goes in Risco. A prior, unrelated
  problem stays out of the GMUD; mention it separately.

## Artemis V2 project

Also save the GMUD to `~/repos/workspace/projetos/artemis-v2/gmud-ts-<id>.md`,
following the root `CLAUDE.md` of `~/repos/workspace` (masked names,
confidentiality check, commit and push to `main`). Model:
`gmud-ts-5377.md` in that folder.

## Common mistakes

| Mistake | Fix |
|---|---|
| "I did not run the tests, dependencies are missing" | Devcontainer Docker image (step 3, [references/tests.md](references/tests.md)) |
| Jira link built by default | Placeholder |
| Tipo "Normal" | The two options in the table |
| "If the worker does not start, the others consume the queue" without looking at argocd | Step 5 |
| Merging everything in step 1 of the deploy plan | Order by dependency (step 5) |
| "No downtime" with a worker that kills tasks on deploy | Step 5; state the effect |
| Claiming error behavior without reading the code | Step 6; otherwise "a confirmar" |
| Evidence without a version | `sand-<sha>`/`prod-<sha>` + ancestry |
| Title made of repo names or jargon | Product or screen + effect for people ("Summary") |
