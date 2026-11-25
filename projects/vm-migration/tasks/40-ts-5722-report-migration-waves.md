+++
card = "TS-5722"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5724"]
blocked_by = ["TS-5707"]
docs = ["12-report-migration-waves.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-24
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 40 — Cadastrar URLs, tokens e credenciais dos envios no Parameter Store

## Contexto

URL e token do platform-cessao e do data-lake-api em homologação e produção e reinício da API e do worker do shared-service.

Também as credenciais dos envios que usam fontes de fora:

- GalaPay da Padtek (ID e hash);
- chave do SFTP do Mercato Pago (File 4);
- SFTP da empresa para os ganhos semanais da VLTS I, com usuário de serviço no lugar do usuário pessoal usado hoje;
- local no S3 do modelo de relatório do aviso mensal do Jurídico.

## Pronto quando

- Teste de conexão passa em homologação e produção para todas as conexões.
