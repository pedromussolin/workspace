Status: rascunho (aguarda confirmação do Heitor)
Data: 05/11/2026
Tags: valids, gmud, ecl, mov-estoque

# GMUD: feature VALIDs (Mov. Estoque, Abertura de Rating e Análise de Migração), não programada, já em produção

## Tipo

Mudança não programada (já executada em produção, horário de Brasília; ver Contexto).

## Summary

Conciliação de Estoques e VALIDs: 3 abas novas com dados diários

## Descrição

**Contexto**
- A tela "Conciliação de Estoques e VALIDs" ganha três abas: Mov. Estoque, Abertura de Rating e Análise de Migração, com a integração entre elas. Elas leem um Postgres próprio (a "poça"), preenchido por cargas diárias, em vez de consultar o Redshift a cada acesso.
- Em produção (Datadog): o código das três abas e das rotas chegou primeiro, com a release 20261029 (data-lake-api `prod-219c8f3`, front `prod-cc77a03`). As cargas diárias, o worker e a fila do valid só existem a partir da release 20261030 (worker no ar às 19:45Z). Datas a confirmar com o responsável pela subida.
- Não foi programada: subiu sem janela de mudança aberta.

**O que muda**
- data-lake-api:
  - rotas `/valid/pdd`, `/valid/aging`, `/valid/stock-movement` e `/valid/stock-movement/dates` (release 20261029), depois `/valid/ecl` e `/valid/ecl/dates` (release 20261030, nomes PDD trocados por ECL);
  - cargas diárias de ECL (17:00) e Mov. Estoque (17:20, horário de Brasília), enfileiradas pelo beat;
  - fila e worker próprios do valid, disparo manual e período de histórico configurável em dias;
  - migrations 0009 a 0016; a 0016 renomeia `valid_pdd_*` para `valid_ecl_*` e para com erro se alguma tiver linhas.
  - releases `219c8f3` e `479fccb`.
- BFF (apl-credit-whitelabel-api): rotas `controllership/valid/*` das três abas (release 20261029) e a troca para `/valid/ecl` (`ee9d113`, em produção como `074349f`). Sobe junto com a data-lake-api.
- Front (apl-credit-whitelabel): as três abas da tela (em produção desde `prod-cc77a03`).
- platform-cessao: rota `GET /pdd/regua-vigente`, régua de PDD por produto (versão em produção a confirmar).
- data-lake-api-argocd (PR #8, tag `prod-479fccb`): deployment `valid` (1 réplica, limite de 1 CPU e 1 GiB) e fila SQS nova. As variáveis de fila, horário e liga/desliga das cargas ficam no Parameter Store.

**O que não muda**
- Visão Geral e Histórico VP e PDD seguem lendo o Redshift, até `CFG_VALID_ECL_STOCK_FROM_POOL` ser ligada (valor em produção: a confirmar).
- Workers e fila padrão existentes da data-lake-api: seguem como estavam.
- Redshift: só leitura (SELECT), nenhuma escrita.

## Prioridade

Medium (proposta; confirmar).

## Link Tarefa

<link do Jira da tarefa>

## Risco

Nível: Médio.

- Worker único ocupado por uma carga longa → os ticks do beat e a outra carga esperam atrás → a primeira carga de ECL durou 52 min (3148 s) e os ticks acumularam até 20:52Z → segura: concorrência 1 de propósito, um tick quando executa não faz nada se a carga já está na fila ou rodando; duração dos runs dos outros dias: a confirmar.
- Deploy do worker com imagem antiga ou nome de fila errado → o pod reinicia e não consome → no deploy, o worker subiu com a imagem anterior (`prod-219c8f3`) às 19:45Z e reiniciou 5 vezes até as 19:54Z, quando a variável do nome da fila foi corrigida; sem consumidor, as cargas não rodam e a tela segue com o último dado → segura: tela lê a poça, sem quebrar; o horário seguinte da carga reprocessa.
- Task interrompida no deploy ou na troca de pod → run fica `running` → o tick seguinte a marca como falha depois de `stale_run_minutes` (120 min) e a carga é repetida em 30 min (`retry_every_minutes`). Sem `acks_late` no código (a mensagem é confirmada antes de executar) e sem grace period no argocd (padrão do Kubernetes, 30 s, a confirmar).
- Renomeação das tabelas (0016) e das rotas → BFF e data-lake-api fora de sincronia dão erro nas abas de PDD → subiram com 1 min de diferença (16:44 e 16:45); a 0016 só roda com as tabelas vazias; o job de migration não apareceu nos logs do Datadog, então a aplicação das 0014 a 0016 é a confirmar pelo banco (as rotas `/valid/ecl` respondem 200 e as cargas gravam runs, o que só funciona com as tabelas novas).
- Carga diária no Redshift (consultas de 5 dias, limite de 900 s cada) → concorre com outras leituras → a execução de Mov. Estoque levou de 11 a 15 min por dia (6 execuções) → segura: horário fora do expediente, só SELECT filtrado por data.

## Impacto

- Tela/usuário: três abas novas na Conciliação de Estoques e VALIDs (Mov. Estoque, Abertura de Rating e Análise de Migração), lendo a poça; a Visão Geral e o Histórico VP e PDD só leem a poça com `CFG_VALID_ECL_STOCK_FROM_POOL` ligada (valor em produção: a confirmar). Antes da primeira carga, a poça está vazia e as abas aparecem sem dados.
- Banco: Postgres da data-lake-api com as migrations 0009 a 0016; tabelas `valid_ecl_*`, da movimentação e de controle de runs novas.
- Infra: 1 pod novo (`valid`), 1 fila SQS nova com DLQ (3 tentativas, 14 dias de retenção), uso de Redis pelo dedupe das tasks.
- Deploy: sem downtime esperado para a API; variáveis novas `CFG_AWS_SQS_TASKS_VALID_QUEUE_NAME`, `CFG_AWS_SQS_TASKS_VALID_QUEUE_URL`, `CFG_VALID_ECL_*` e `CFG_VALID_MOVEMENT_*` no Parameter Store.

## Plano de implantação

Já executado em dois momentos (release 20261029: código das três abas; release 20261030: cargas, worker e fila; horário de Brasília). Ordem segura, e o que aconteceu na segunda:
1. Criar a fila SQS do valid (`resources.yaml`) e as variáveis no Parameter Store, antes do pod. Na prática o nome da fila foi corrigido só às 16:54.
2. Publicar a imagem da data-lake-api (`prod-479fccb`, PR #126, 16:44) e rodar o job de migration (0014 a 0016).
3. Subir o deployment `valid` do argocd (PR #8, 16:42; tag da imagem às 16:50). Conferir: pod `ready`, log "Celery queue" com o nome da fila do valid. O pod subiu com a imagem anterior às 16:45 e reiniciou até as 16:54.
4. Publicar o BFF (PR #241, 16:45). Conferir: `GET /valid/ecl` e `/valid/ecl/dates` com 200.
5. Conferir o beat: `dispatch_valid_ecl` com run id (17:00) e `dispatch_valid_movement` com run id (17:20); `run N succeeded` no log do worker.

## Plano de Rollback

1. Sem deploy: desligar `CFG_VALID_ECL_SCHEDULE_ENABLED` e `CFG_VALID_MOVEMENT_SCHEDULE_ENABLED` no Parameter Store e reiniciar o beat; desligar `CFG_VALID_ECL_STOCK_FROM_POOL` para a Visão Geral voltar ao Redshift. Valores atuais e onde estão: a confirmar.
2. Esperar a run em andamento terminar (até ~52 min) antes de derrubar o worker `valid`; depois, drenar a fila do valid.
3. Rollback completo, na ordem inversa: BFF (`074349f` para o anterior), depois data-lake-api para `prod-219c8f3` com o downgrade da 0016 (testado local antes do deploy), depois remover o deployment `valid`. A imagem antiga não conhece `/valid/ecl` nem as tabelas `valid_ecl_*`; sem o downgrade e a volta do BFF, as abas de PDD quebram.
4. Fica para trás: tabelas `valid_ecl_*` com dados, runs, a fila SQS e sua DLQ (remover só se o argocd não for reaplicado).

## Evidências de validação

Testes (rodados em 30/10, não de novo na data desta GMUD):
- data-lake-api `5d284f6`: 491 testes passando; a falha é a do `day_cache`, igual na release; migrations a partir da 0011 num banco novo, ida e volta da 0016.
- BFF `ee9d113`: 94 testes do módulo.

Produção, 29/10 (Datadog, `env:production`, de 27/10 a 30/10 19:50Z, data-lake-api `prod-219c8f3`, rotas das três abas): `/valid/pdd` 19 × 200, `/valid/aging` 31 × 200, `/valid/stock-movement` 9 × 200, `/valid/stock-movement/dates` 8 × 200, sem erro; BFF `prod-bf8882b`: as mesmas rotas `controllership/valid/*` com 200. Nessa janela, as rotas `/valid/stock` e do BFF `controllership/valid/stock` tiveram 500 e 404 em versões anteriores do BFF (`0e736d8`, `bb877db`, `bf8882b`); não investiguei.

Produção, 30/10 em diante (Datadog, `env:production`, UTC):
- Versões: data-lake-api `prod-479fccb` (ancestral confirmado de `5d284f6`); BFF `prod-074349f` (ancestral confirmado de `ee9d113`); worker do valid `prod-219c8f3` às 19:45Z e `prod-479fccb` depois.
- Worker do valid: pod `ready` às 19:54:22Z, sem reinício depois.
- ECL: run 1 queued às 20:00:01Z de 30/10 e `succeeded` às 20:52:29Z (3148 s); runs 67, 133, 199, 265 e 331 enfileiradas às 20:00Z de 31/10 a 04/11.
- Mov. Estoque: runs 34, 100, 166, 232, 298 e 364 `succeeded`, de 11 a 15 min cada (30/10 a 04/11).
- Rotas desde 30/10 19:00Z (data-lake-api): `/valid/ecl` 30 × 200; `/valid/ecl/dates` 51 × 200; `/valid/stock-movement` 14 × 200; `/valid/stock-movement/dates` 11 × 200; `/valid/stock` 56 × 200 e 1 × 404.
- 5xx: 1 no BFF em `/controllership/valid/stock` (03/11 17:53Z, trace `15609844535359287539`); causa a investigar.
