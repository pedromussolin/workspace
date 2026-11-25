+++
card = "TS-5715"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5716"]
blocked_by = ["TS-5714"]
docs = ["08-shared-email-destination.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-19
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 35 — Shared: resolução de destinatários e envio pelo Graph com anexos

## Contexto

Resolver contatos, pessoas e grupos do diretório e enviar mensagem única com to, cc, cco e anexos, com sessão de upload para anexos grandes.

Também grava uma cópia do arquivo numa pasta do SharePoint pelo Graph, para os boletos pagos da Padtek, que hoje vão para a pasta da Conciliação.

## A fazer antes de implementar

- Confirmar com a Conciliação se a pasta do SharePoint dos boletos pagos ainda é usada.

## Pronto quando

- Envio com anexo grande validado em homologação.
- Cópia no SharePoint validada em homologação, se a pasta ainda for usada.
