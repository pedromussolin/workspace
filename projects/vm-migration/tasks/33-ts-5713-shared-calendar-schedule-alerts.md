+++
card = "TS-5713"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5721", "TS-5724"]
blocked_by = ["TS-5709", "TS-5711"]
docs = ["09-shared-calendar-schedule-alerts.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-25
+++
# 33 — Shared: agenda por dia útil e aviso de falha de execução

## Contexto

Agenda além do cron (só em dia útil, N-ésimo e último dia útil do mês) e aviso quando uma execução falha, por monitor no Datadog ou e-mail.

Cobre todas as recorrências dos scripts de envio: dia útil, segunda-feira, dia fixo do mês (1, 25 e 27), primeiro dia útil do mês e várias vezes no mesmo dia (resultado do processamento do Mercato Pago, das 9h às 11h).

## Pronto quando

- Agendamento por dia útil funcionando e falha de execução gera aviso.
- Cada recorrência dos scripts de envio tem um agendamento equivalente.
