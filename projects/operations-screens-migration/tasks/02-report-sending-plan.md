# 02 — Envio de relatórios pela tela Envio de Relatórios

Status: planejada (13/11/2026)
Épico no Jira: Migração VM (tarefas 02 a 12)

## Objetivo

Levar para a tela Envio de Relatórios do portal os relatórios que os scripts do repositório de
automações (`plgn-automations`) geram e mandam por e-mail a partir da EC2 de automações. A tela
(o módulo `report-transfer`) hoje só move arquivos entre SFTP, FTP, S3 e GCS; passa a consultar
os microsserviços, gerar o arquivo e mandar por e-mail. Cada onda roda em paralelo com o script e,
quando anexos e totais baterem, a linha do script sai da agenda do orquestrador
(`mv_schedule_reports`, a tabela que diz quando cada script roda).

Esta tarefa é o mapa: o trabalho está quebrado nas tarefas 03 a 12.

## Escopo

13 relatórios entram, em quatro ondas e um grupo bloqueado [C]:

| Onda | Relatórios | De onde vêm os dados |
|---|---|---|
| 1 | Cessões diárias, Cessões mensais, Pendura a acrescer e Vencimentos atualizados (FIDC Fornecedores) | platform-cessao, consulta de contratos |
| 2 | Relação de baixas (FIDC Vektor); Valores processados e Liquidações rejeitadas (FIDCs Mercato Pago) | platform-cessao, consulta de liquidação |
| 3 | Estoque (FIDC VLTS I); Base de operações e estoque (FIDC FBRX3) | data-lake-api, posição de ativos |
| 4 | Projeção de valor presente (FIDC VLTS I); Renegociações (Equimedix, administrador Dayvale) | data-lake-api e uma regra em código |
| bloqueado | Valor conciliado e Resultado do processamento (FIDCs Mercato Pago) | dependem de uma planilha que outro script grava numa pasta local da EC2 |

Fora desta fase:

- Boletos pagos do FIDC Padtek: lê a API da GalaPay e grava uma cópia no SharePoint.
- Relação de fundos ativos: baixa um arquivo da CVM.
- Report do OCR: lê tabelas próprias no Lake.
- Os 10 scripts de avisos e solicitações, entre eles os Boletos mensais da Padtek, que saem por um
  botão no portal e não pela agenda.
- Os scripts apagados do repositório em 05/11 e 09/11 (T18).

## Como a tela fica

Decisões T12 a T17 de [decisions.md](../decisions.md):

- **Origem por API.** A Origem aceita uma conexão do tipo API, ligada ao platform-cessao ou ao
  data-lake-api, com o token no Parameter Store. O painel da Origem muda conforme o tipo da
  conexão: pasta para arquivos; consulta, filtros, prévia de dados e prévia SQL para API.
- **Catálogo fixo** de consultas no shared-service.
- **Prévia SQL** gerada pelo microsserviço que executa a consulta, só leitura.
- **Gerar Arquivo**, um bloco novo que transforma as linhas da consulta em xlsx ou csv.
- **E-mail como conexão** só de destino, com destinatários escolhidos de uma lista.
- **Duas rotas no platform-cessao:** contratos e liquidação.

Nenhum script faz algo depois do e-mail além de apagar o arquivo temporário [C]. O destino e-mail
fecha o subfluxo (o trecho de origem a destino dentro de um fluxo).

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
  arquivo privado do projeto (`~/.config/workspace/private/operations-screens-migration.md`).
