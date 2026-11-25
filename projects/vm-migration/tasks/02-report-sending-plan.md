+++
card = "TS-5717"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5726", "TS-5707", "TS-5709", "TS-5711", "TS-5714", "TS-5718"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-16
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 02 — Envio de relatórios pela tela Envio de Relatórios

Status: planejada (13/11/2026); escopo ampliado para os 25 scripts (16/11/2026)
Épico no Jira: Migração VM (tarefas 02 a 12)

## Objetivo

Levar para a tela Envio de Relatórios do portal os relatórios que os scripts do repositório de
automações (`pldr-automations`) geram e mandam por e-mail a partir da EC2 de automações. A tela
(o módulo `report-transfer`) hoje só move arquivos entre SFTP, FTP, S3 e GCS; passa a consultar
os microsserviços, gerar o arquivo e mandar por e-mail. Cada onda roda em paralelo com o script e,
quando anexos e totais baterem, a linha do script sai da agenda do orquestrador
(`mv_schedule_reports`, a tabela que diz quando cada script roda).

Esta tarefa é o mapa: o trabalho está quebrado nas tarefas 03 a 12.

## Escopo

Os 25 scripts de envio de relatórios saem da EC2 de automações, nos cards que já existem (T19 e
T20, 16/11/2026). Antes eram 13 relatórios nesta fase e 13 scripts fora dela [C]:

| Card | Scripts | De onde vêm os dados |
|---|---|---|
| TS-5724, Onda 1 | FIDC Fornecedores: cessões diárias e mensais, pendura a acrescer, vencimentos atualizados, cobrança diária e fee mensal; aviso mensal do Jurídico | platform-cessao (contratos, com filtro por vencimento, e liquidação por mês); modelo fixo no S3 |
| TS-5725, Onda 2 | Relação de baixas (FIDC Vektor); valores processados, liquidações rejeitadas e as três retiradas de recusados (FIDCs Mercato Pago) | platform-cessao, consulta de liquidação, com o motivo da rejeição |
| TS-5740, Onda 3 | Estoque (FIDC VLTS I); base de operações e estoque (FIDC FBRX3); report do OCR | data-lake-api, posição de ativos e consulta do OCR |
| TS-5741, Onda 4 | Projeção de valor presente e ganhos semanais (VLTS I); renegociações (Equimedix, administrador Dayvale); write-off mensal e estornos (Mercato Pago); boletos pagos e mensais (Padtek); relação de fundos ativos (CVM) | data-lake-api, regras em código, SFTP, GalaPay e download da CVM |
| TS-5727 | Valor conciliado e resultado do processamento (FIDCs Mercato Pago) | platform-cessao e o esperado do dia calculado dos File 4 do SFTP, sem a planilha da EC2 |

O que mudou na plataforma para caber tudo nos cards existentes:

- TS-5707: a conexão API usa os clientes que o shared já tem para o platform-cessao e o
  data-lake-api e passa a cobrir a GalaPay e o download da CVM.
- TS-5712: as regras nomeadas também recebem um arquivo de entrada (File 4, ganhos da VLTS I,
  cadastro da CVM).
- TS-5715 e TS-5716: cópia no SharePoint, anexo zip e disparo manual.
- TS-5743: consulta do OCR no data-lake-api.

Não entram: os scripts apagados do repositório em 05/11 e 09/11 (T18), a emissão dos boletos da
Padtek na GalaPay (é tela, não envio) e os alertas do Mercato Pago (TS-5751).

## Como a tela fica

Revisto em 17/11/2026 (T21 a T26 de [decisions.md](../decisions.md)): os envios entram na tela
nova Automações, aba de disparo de e-mails. A tela Envio de Relatórios continua até ser absorvida
pela aba de envio de arquivos.

- **Blocos separados** para Consultar API e Disparar e-mail (T22, que substitui a T12 e a T16).
  Os blocos de arquivo ficam só para pasta e bucket, com os nomes "Buscar arquivos" e "Gravar
  arquivos" (T27).
- **Catálogo fixo** de consultas no shared-service (T13): Consultar API só chama o que está nele.
- **Prévia SQL** gerada pelo microsserviço que executa a consulta, só leitura (T14).
- **Gerar Arquivo**, que transforma as linhas da consulta em xlsx ou csv (T15), na família de
  blocos de planilha.
- **Disparar e-mail** pelo `email_dispatch` do shared: um e-mail só, com Para, Cópia, Cópia oculta
  e anexos (T26), para grupos e endereços do Entra ID, inclusive os clientes (T28, D11).
- **Duas rotas no platform-cessao:** contratos e liquidação (T17).
- **Cálculo na tela:** a conta (fee, valor desembolsado, rótulos) é escrita pelo usuário num bloco
  de cálculo, sobre as colunas que existem, sem regra fixa em código (T30, detalhes na D12).
- **Linha reta com contexto** entre os blocos (T24), na mesma tabela de fluxos do Envio de
  Relatórios, com a aba como filtro (T25).

Nenhum script faz algo depois do e-mail além de apagar o arquivo temporário [C]. O bloco Disparar
e-mail fecha o subfluxo (o trecho do primeiro ao último bloco dentro de um fluxo).

As descrições das TS-5707, TS-5710, TS-5714 a TS-5716 e TS-5719 a TS-5721 ainda falam em Origem
por API e conexão E-mail, e as das TS-5714, TS-5719 e TS-5723 num cadastro de contatos no shared
(T28), e as das TS-5711 e TS-5712 em regras nomeadas em código (T30): atualizar pelo `/card`.

## Tarefas

Estimativa em dias de trabalho de uma pessoa que conhece o repositório, com testes e revisão.

| # | Tarefa | Sem IA | Com IA |
|---|---|---|---|
| 03 | [Especificação do catálogo de consultas](03-query-catalog-spec.md) | 2 | 1 |
| 04 | [Rotas de consulta no platform-cessao](04-cessao-report-queries.md) | 15 | 7,5 |
| 05 | [Posição de ativos no data-lake-api](05-lake-stock-position.md) | 10 | 5,5 |
| 06 | [Shared: conexão de API e catálogo](06-shared-api-connection.md) | 8 | 4 |
| 07 | [Shared: Origem com consulta e Gerar Arquivo](07-shared-query-source-and-file.md) | 16,5 | 8 |
| 08 | [Shared: conexão de e-mail e envio](08-shared-email-destination.md) | 14 | 6,5 |
| 09 | [Shared: calendário, agenda e aviso de falha](09-shared-calendar-schedule-alerts.md) | 6 | 3 |
| 10 | [BFF](10-bff-report-sending.md) | 5 | 2,5 |
| 11 | [Front da tela](11-front-report-sending.md) | 27,5 | 12,5 |
| 12 | [Migração em ondas e desligamento](12-report-migration-waves.md) | 21,5 | 15 |
| D5 a D8 | Decisões pendentes | 2,5 | 2,5 |
| | **Total** | **128** | **68** |

- Com contingência: 154 dias sem IA (20%) e 85 com IA (25%, porque o retrabalho em código gerado
  é mais difícil de prever).
- Até a Onda 1 em produção: 98 dias sem IA e 49,5 com IA. A base da plataforma custa três quartos
  do total; depois dela, cada onda custa poucos dias.
- Com três pessoas, uma por trilha (rotas de dados, shared-service, BFF e front): cerca de 12
  semanas sem IA e 7,5 com IA, sem contingência. O shared-service é o caminho crítico.
- Fora da estimativa: espera por deploy, aprovação de GMUD e infraestrutura. O paralelo de cada
  onda dura pelo menos uma semana corrida, com ou sem IA.

## Fontes

- Leitura do código do repositório de automações em 05/11 e 13/11/2026 [C].
- Inventário dos scripts de e-mail e backlog interativo com as estimativas no claude.ai: links no
  arquivo privado do projeto (`~/.config/workspace/private/vm-migration.md`).
