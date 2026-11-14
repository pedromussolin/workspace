# Fallback: the classic Datadog tools

Use it only when `execute_code` is unavailable or its run failed (`invalid_request`, a timeout, a
whole run with `sem_dados` because every query failed). Tell the user the program needs a fix.

## Get the calls

```
ws deploy-check queries <key> --env <env> [--at ISO]
```

The output is a JSON list. Each item is `{"check", "window", "tool", "arguments"}`:

- `window` is `before`, `after` or `baseline`; the `from` and `to` of the arguments already hold it;
- `tool` is `aggregate_spans`, `aggregate_rum_events` or `analyze_datadog_logs` of the Datadog MCP;
- `arguments` go to that tool verbatim, `telemetry` included.

`analyze_datadog_logs` needs the `datadog/ddsql` skill loaded first (the tool says so): load it once,
before the first logs call. The other two tools need no skill.

## Run and judge

Run the items one tool call each (independent ones in the same message), keep only the numbers, and
judge them with the same rules as the program:

| Check | Compare | Rule |
|---|---|---|
| traffic | requests per minute, before and after | informational; `sem_dados` under `min_requests` in either window |
| errors, http_5xx | error (or 5xx) count over request count (the traffic counts) | rate up more than 50% is `piorou` when the after count exceeds the before rate applied to the after traffic by at least `min_extra_errors` (default 10), otherwise `atencao`; from zero, 10 or more is `piorou`, fewer is `atencao` |
| p95 | `p95_duration_ns` of the two windows, in ms | `piorou` when up more than 30% and more than 50 ms |
| error_logs | count per minute | up more than 50% is `piorou` with at least `min_extra_errors` more than the before rate gives for the after window, otherwise `atencao` |
| new_errors | signatures of the after window absent from the baseline | any is `atencao`; one with 10 or more occurrences is `piorou` |
| version | share of the after window's traffic on the expected `DD_VERSION` | `sem_dados` under `min_requests` in the window or when a bucket lacks the version facet; at least 95% is `ok`, below is `atencao` |

When the after window is not complete (`complete: false` in the plan), compare rates over the
elapsed part and say so. The verdict of a service is its worst check; `sem_dados` never counts as
bad. Write the same PT-BR report as the program path: a table, new errors with counts and a one-line
description, the version share, and the order advice.
