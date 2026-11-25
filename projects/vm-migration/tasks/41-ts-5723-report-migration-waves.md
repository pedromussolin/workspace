+++
card = "TS-5723"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5724"]
blocked_by = ["TS-5714"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-19
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 41 — Migrar as listas de destinatários dos envios da mv_mail_list para contatos

## Contexto

Levar para contatos e conexões de e-mail, direto no ambiente e sem arquivo versionado, as 25 listas da mv_mail_list usadas pelos scripts de envio de relatórios: 1, 2, 6, 10, 11, 12, 13, 14, 19, 20, 23, 25, 26, 27, 28, 29, 32, 33, 34, 35, 37, 38, 39, 46 e 47.

Pontos de atenção:

- o vencimento atualizado usa a lista 38 no para e a 39 em cópia, e a 39 também é de outro alerta;
- o write-off mensal filtra a lista 19 por domínio no código;
- o aviso do Jurídico usa cópia oculta.

## Pronto quando

- As 25 listas cadastradas e conferidas, com para, cópia e cópia oculta como hoje.
