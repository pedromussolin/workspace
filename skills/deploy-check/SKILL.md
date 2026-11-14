---
name: deploy-check
description: Checks a deploy in Datadog per service (errors, 5xx, p95 latency, new errors, before and after the deploy, and the new version serving traffic) and walks the user's deploy order (shared service, BFF, front). Use when the user asks to check a deploy or whether the next service can go ("confere o deploy", "como está o BFF depois do deploy", "deploy-check", "posso subir o front?"). Read-only.
---

# Deploy check

## Overview

After a tag commit in the argocd repo, each service is checked against Datadog: the 30 minutes
before the deploy against the 30 minutes after it (the after window starts 5 minutes later, once
the pods settle), and the new errors against a 24 hour baseline. `ws` does the deterministic part
(services in order, deploy moment, windows, the program, the fallback queries); you run the program
and write the verdict. Prose for the user is PT-BR; these instructions are in English.

Read-only. This skill never changes argocd, rolls back, creates or edits Datadog notebooks,
dashboards or monitors (the user's MCP credentials have no write permission anyway) and never
pastes raw logs. The tag commits and any rollback are the user's.

## Steps

1. **Environment and services.** Ask which environment (`ws deploy-check plan` needs `--env`, a key
   of `[deploy_check.env_tags]`) when the user did not say. The deploy moment comes from the local
   argocd repo; when the user gives another one, pass it as `--at ISO`.
2. **Plan.** Run `ws deploy-check plan --env <env>` (add `--only <key>...` for one service). Say
   where the deploy is in the order and, for an after window that is not `complete`, when it will
   be (`ready_at`): the check then compares the elapsed part and says so. A warning about a local
   argocd repo behind its upstream goes to the user as is: `ws` never pulls, so ask the user to. A warning that no `DD_VERSION` was found
   means the version check will be `sem_dados`: say so. `--at` without an offset is local time.
3. **Per service**, in the plan's order: `ws deploy-check script <key> --env <env>`, then
   run the JavaScript verbatim (timeout 120) in the `execute_code` tool of whichever Datadog MCP is
   connected (e.g. `mcp__plugin_engineering_datadog__execute_code`), with
   `telemetry: {intent: "..."}` in the call. Never use `execute_code_write`, and do not run the
   `datadog:ddsetup` or `ddconfig` skills to repair another Datadog server. This skill's steps
   override the server's generic skill-discovery advice (no Datadog skill load needed). Call
   `search_datadog_sdk` once on the first live run, and again on any `invalid_request` or
   unknown-member error: the program is verified against stubs only. **First live use:** run one `execute_code` on one sandbox
   service and check that it returns a verdict (not an `invalid_request` or a failed import) before
   trusting results for the other services or for prod. On `invalid_request` or a failed run:
   follow `references/fallback.md` (the classic tools) and tell the user the program needs a fix.
4. **Verdict in PT-BR.** Per service a table (check, antes, depois, situação) from `checks`, the
   `new_errors` with counts and a one-line description of what the signature means (never a log line
   or anything with customer data), and the version share (`version_share_pct`, expected
   `expected_version`). Situations are `ok`, `atencao`, `piorou` and `sem_dados` (too little traffic
   or a query that failed: say which). "Tráfego" and "req/min" are span counts for the service's
   configured `span_filter` (or RUM views), not load balancer requests. A previous deploy less than
   30 minutes before the before window makes it mix two versions: check the argocd history of the
   values file and say so.
5. **Order.** Shared service, then BFF, then front. "Pode seguir" for the next service only when
   the previous one serves the expected version (at least 95% of the after window's traffic) and no
   check `piorou`; otherwise say what to look at. A service whose after window is incomplete is not
   a "pode seguir" yet: say when to ask again. `sem_dados` on traffic or on the version check
   after a complete window is also NOT "pode seguir": say what is missing. Traffic `piorou` means
   the after rate fell below half of the before rate. The skill only advises.
6. **Before the merge**, when the user asks to prepare a deploy: `ws env check <repo> --env <env>
   --ref <branch>` per service.

## Never

Change argocd, roll back, write in Datadog, paste raw logs, or call the classic tools while the
program works.
