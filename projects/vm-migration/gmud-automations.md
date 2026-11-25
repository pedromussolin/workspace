Status: rascunho
Data: 23/11/2026
Tags: GMUD, automações

# GMUD: tela Automações (rascunho)

Escrita antes da implementação, a pedido do Heitor, com o deploy marcado para quarta-feira,
25/11/2026, das 18:00 às 18:30. O que está no plano e ainda não foi conferido no código fica como
"a confirmar". Evidências vazias até existir implementação. Decisões de origem: T21 a T54 e D10 de [decisions.md](decisions.md). Revisada em 23/11 para a estrutura de banco das T44 a T50 e a
entrega única da T51, e em 24/11 com o que a implementação (branches locais, sem PR) definiu:
migrations, variáveis e roles.

## Tipo

Mudança programada

## Summary

Automações: nova tela para montar envios de arquivos e de e-mails com blocos

## Descrição

**Contexto**
- 25 scripts de envio de relatórios por e-mail rodam na EC2 de automações, fora dos repositórios, sem dono depois da saída do responsável (inventário TS-5706, 16/11/2026).
- A tela Envio de Relatórios só move arquivos entre SFTP, FTP, S3 e GCS: não consulta dados, não calcula, não gera planilha nem envia e-mail.

**O que muda**
- apl-shared-service:
  - motor de automações por blocos, que evolui o motor do Envio de Relatórios, com os blocos novos (Consultar API, Calcular colunas, Agrupar, Trocar rótulos, Parar se vazio, Ler planilha, Gerar planilha, Compactar, Disparar e-mail); o subfluxo pode terminar em qualquer bloco;
  - migration: schema `report_transfer` vira `automations`; tabelas novas `flow_versions` e `execution_steps`; `flows` ganha `category`; `execution_routes` vira `execution_subflows` (uma linha para todo subfluxo, com status, horários, erro, `payload` e `result` em JSONB); `execution_files` vira `file_results` (uma linha por arquivo), com as tabelas novas `file_storage_deliveries` e `file_email_deliveries`; conversão do histórico e reescrita dos JSON das definições; views de compatibilidade no schema antigo;
  - migrations `a6f39013f6f1` (automações) e `6063a637cfde` (agenda por dia útil no agendador);
  - task `automations.run_flow` na fila padrão, com `report_transfer.run_flow` como apelido; os
    agendamentos existentes continuam com o nome antigo (T54), para a tela Envio de Relatórios
    seguir listando agendamentos e execuções;
  - e-mail com uma mensagem só (Para, Cópia, Cópia oculta) e anexos lidos do S3, só de um prefixo permitido do bucket;
  - limpeza diária das execuções mais velhas que N dias, nascida desligada.
- apl-credit-whitelabel-api (BFF): rotas `/automations` e escopos de permissão novos.
- apl-credit-whitelabel (front): tela Operações › Automações.
- argocd: variáveis novas (lista no passo 1 do plano) e, durante o deploy, worker e agendador parados.

**O que não muda**
- A tela Envio de Relatórios, as rotas `/report-transfer`, os fluxos e os agendamentos existentes.
- Os scripts da EC2, que continuam rodando até cada onda de migração (GMUDs próprias).
- platform-cessao e data-lake-api: as rotas usadas por Consultar API entram em GMUD própria.
- As tabelas do `email_dispatch`.

## Prioridade

High

## Link Tarefa

TS-5704, link do Jira (épico "[VM TELAS] Telas e scripts da VM"; escolha do Heitor em 19/11/2026)

## Risco

Médio
- Migration falha no meio → o Job de migration falha → DDL do Postgres é transacional: tudo volta; worker e agendador continuam parados até a decisão de seguir ou voltar (a confirmar no chart se a troca dos pods espera o Job).
- Conversão do histórico demora mais que a janela → worker e agendador parados por mais tempo → medir antes o volume de `execution_routes` e `execution_files` (consulta só de leitura) e ensaiar a migration em sandbox.
- API da versão anterior durante a troca lê `report_transfer.*` → erro nas telas → views de compatibilidade no schema antigo.
- Mensagem já na fila com o nome antigo da task → falha ao religar o worker → `report_transfer.run_flow` continua registrada como apelido.
- Execução em andamento quando o worker é parado → a execução se perde (sem `acks_late`) → parar só sem execução em andamento e fora dos agendamentos; o vigia marca a interrompida em até 15 min.
- Agendamento que cairia na janela → não roda com o agendador parado → nenhum agendamento conhecido entre 18:00 e 18:30; conferir os ativos antes (a confirmar se o agendador executa os vencidos ao religar).
- Automação nova mandando e-mail a cliente antes da hora → automação nasce desativada; fora de produção, todo e-mail vai para a caixa de teste.
- Escopos sem role no Azure → ninguém vê a tela → falha fechada; roles criadas antes do front.
- Pedido de e-mail com anexo fora das automações → arquivo indevido enviado → o `email_dispatch` só aceita anexos do prefixo permitido.
- Rotas de consulta e de calendário ainda inexistentes no data-lake-api e no platform-cessao → Consultar API, `DIAS_UTEIS` e agenda por dia útil falham → nenhuma automação nova usa esses blocos até as GMUDs dessas rotas; ativar agenda por dia útil sem calendário é recusado.
- Variável do bucket de arquivos gerados ausente → os blocos que geram arquivo falham → conferir no passo 1.

## Impacto

- Tela/usuário: menu novo Operações › Automações, só para quem tiver as roles novas. Envio de Relatórios sem mudança visível.
- Banco: a migration renomeia schema e tabelas, cria quatro tabelas, acrescenta colunas e views, e reescreve dados: JSON das definições dos fluxos, contagens do histórico de subfluxos para JSON e cada linha antiga de arquivo em arquivo mais entrega.
- Infra: worker e agendador parados por alguns minutos durante a migration. Sem pod nem fila novos. Variáveis novas no argocd (a confirmar). Limpeza nova, desligada.
- Deploy: API sem indisponibilidade esperada (troca gradual dos pods). Agendamentos e execuções param enquanto o worker e o agendador estiverem desligados.

## Plano de implantação

Quarta-feira, 25/11/2026, das 18:00 às 18:30.

Antes: conferir em `scheduler.scheduled_jobs` (só leitura) que nenhum agendamento ativo cai entre 18:00 e 18:30; conferir em `scheduler.job_executions` que não há execução `RUNNING`; ter medido o volume do histórico e ensaiado a migration em sandbox.

1. argocd: variáveis novas do apl-shared-service: `CFG_AUTOMATIONS_OUTPUT_BUCKET` (obrigatória),
   `CFG_AUTOMATIONS_OUTPUT_PREFIX` (`automations`), `CFG_AUTOMATIONS_RETENTION_DAYS` (90, maior ou
   igual à retenção do disparo de e-mail), `CFG_AUTOMATIONS_DOWNLOAD_LINK_SECONDS` (300),
   `CFG_AUTOMATIONS_MAX_ROWS` (200000), `CFG_AUTOMATIONS_PURGE_BATCH_SIZE` (200),
   `CFG_API_DATA_LAKE_CALENDAR_CACHE_SECONDS` (21600), `CFG_EMAIL_DISPATCH_ATTACHMENTS_BUCKET`
   (igual ao bucket de arquivos gerados), `CFG_EMAIL_DISPATCH_ATTACHMENTS_PREFIX` (`automations/`)
   e `CFG_EMAIL_DISPATCH_MAX_ATTACHMENTS_BYTES` (35 MB); `CFG_API_DATA_LAKE_BASE_URL` na API, no
   worker e no agendador. Acesso do papel do serviço ao prefixo `automations/` do bucket; permissão
   do app do Graph para buscar usuários e grupos (a confirmar). Conferir: valores presentes.
2. Azure: 12 roles novas — `automations-flows:read`, `:create`, `:update`, `:delete`, `:run`;
   `automations-executions:read`; `automations-downloads:read`; `automations-connections:read`,
   `:create`, `:update`, `:delete`, `:test`. Conferir: roles visíveis no cadastro.
3. argocd: autoscaling do worker desligado (o HPA mantém no mínimo 3 réplicas), worker com 0 réplicas e agendador desligado. Conferir: nenhum pod de worker nem de agendador.
4. apl-shared-service: versão nova, com o Job de migration (`a6f39013f6f1` e `6063a637cfde`). Conferir: Job concluído sem erro; schema `automations` com as tabelas novas; API na versão nova; Envio de Relatórios lista fluxos, agendamentos e execuções; agendamento da limpeza `automations.purge_executions` desativado.
5. argocd: worker de volta a 3 réplicas, autoscaling religado (mínimo 3, máximo 6) e agendador ligado. Conferir: pods de pé consumindo a fila padrão; execução manual de um fluxo existente termina e grava em `execution_subflows`, `execution_steps`, `file_results` e `file_storage_deliveries`.
6. BFF. Conferir: `/automations` responde 200 com a role e 403 sem ela.
7. Front. Conferir: o menu aparece para quem tem a role; uma automação de teste, desativada e com destino interno, roda manualmente até o fim.

## Plano de Rollback

Ordem inversa.
1. Front: versão anterior. Sem deploy: tirar as roles do Azure esconde a tela.
2. BFF: versão anterior.
3. apl-shared-service: parar worker e agendador; `alembic downgrade` para a revisão anterior, que desfaz as renomeações, remove tabelas e colunas novas e devolve as contagens às colunas (a confirmar: o downgrade das conversões precisa ser escrito junto com a migration); imagem anterior; religar worker e agendador.

O que fica para trás: o que o downgrade não converter de volta, arquivos gerados no S3 e e-mails já enviados.

## Evidências de validação

(vazio até a implementação)
