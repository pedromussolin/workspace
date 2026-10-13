# Bugs encontrados no mapeamento

Achados durante o mapeamento de 05/10/2026 que ainda não têm tarefa. Cada um
diz como foi confirmado; ao virar tarefa, mover para `tarefas/`.

## B1 — Filtro com mais de um status volta vazio

- **Onde:** BFF `src/modules/operations/liquidation_batches/business.py:240`
  manda `status=a,b` numa string só. A cessão declara `status` com
  `action="append"` (`cessao/api/liquidacao/viewer.py:174-180`), espera o
  parâmetro repetido e filtra `estado_atual IN ('a,b')`
  (`repository.py:685`, `966`).
- **Efeito:** escolher dois ou mais status na tela não traz nenhum lote.
- **Confirmado:** leitura do código dos dois lados.
- **Correção:** no BFF, um `("status", valor)` por status.

## B2 — Paginação instável em `pagamentos/query`

- **Onde:** o viewer lê `sort` mas não repassa
  (`cessao/api/liquidacao/viewer.py:1131-1144`); o repositório só ordena se
  houver `sort` (`repository.py:1094-1101`).
- **Efeito:** LIMIT/OFFSET sem ORDER BY; o Postgres não garante ordem, então
  linhas podem repetir ou sumir entre páginas.
- **Confirmado:** leitura do código.
- **Correção:** repassar `sort` e ter uma ordenação padrão com desempate por id.

## B3 — Cancelamento gravado como liquidação

- **Onde:** `atualiza_status_contrato_task`
  (`cessao/tasks/liquidacao_lote.py:151-227`) lê `tipo_liquidacao` com o tipo
  do model (`.columns(..., LiquidacaoPagamento.tipo_liquidacao)`), que devolve
  `EnumTipoRemessa.cancelamento`, e compara com a string `"cancelamento"`.
- **Efeito:** a comparação é sempre falsa; todo contrato vira
  `contrato_transacao` do tipo `liquidacao`, inclusive os cancelados.
- **Confirmado:** teste no SQLAlchemy 1.3.24 (a versão de produção) contra
  Postgres: o valor volta como `<EnumTipoRemessa.cancelamento: '0077'>` e
  `== "cancelamento"` dá `False`.
- **Correção:** comparar com `EnumTipoRemessa.cancelamento`. Avaliar se é
  preciso corrigir dados antigos.

## B4 — Lote fake visível que não fecha

- **Onde:** o fechamento exige o processo do contrato em `cadastrado`
  (`groups_pagamentos_aptos`, `cessao/database/models.py:6097`); a listagem
  fake não exige.
- **Efeito:** a linha aparece, o usuário clica em fechar e recebe 400
  "nenhum pagamento apto para liquidar".
- **Confirmado:** leitura do código. As ~3.300 respostas 400 do
  `POST /liquidacao/` em 30 dias vêm quase todas da varredura (3.274), que não
  passa pela tela; pela tela foram 4 em 7 dias. O bug existe, mas o impacto
  na tela é pequeno.
- **Correção:** alinhar o critério da listagem com o do fechamento, ou mostrar
  na linha por que ela não pode fechar.
- **13/10:** resolvido pela D9 (o fechamento deixa de exigir a cessão
  concluída), quando o P5 da tarefa 03 entrar.
- **Relacionado:** o status da linha fake é `min(estado_atual)` (ordem
  alfabética, `repository.py:933`), o que pode esconder pagamentos em
  processamento.

## B5 — Fechar lote não confere se o produto é do parceiro (segurança)

- **Onde:** BFF `POST /operations/liquidation/fake-batches/consolidate`
  (`src/modules/operations/liquidation_batches/viewer.py:324-359`) só checa o
  papel `liquidation-fake-batches:update`/`admin:update`. As listagens
  restringem aos produtos do parceiro; o fechamento não.
- **Efeito:** um usuário de parceiro com `update` pode fechar lotes de outro
  parceiro chamando a API direto.
- **Confirmado:** leitura do código.
- **Correção:** aplicar a mesma restrição de produtos das listagens.

## B6 — Baixa de um lote roda a cessão do produto inteiro

- **Onde:** `EstadoCallback.liberacao_processos`
  (`cessao/framework/liquidacao/estados_baixa.py:94-106`), na esteira de baixa
  do lote. Busca **todos** os `ProcessoEstado` do produto em `liberando` e roda
  a `ManagerCessao` sobre eles, dentro da task do lote.
- **Efeito:** a baixa de um lote faz trabalho de cessão sem relação com ele. O
  tempo da task cresce com o volume de cessões pendentes do produto, e uma
  falha nessa cessão cai no tratamento de erro da baixa (`:115-116`).
- **Confirmado:** leitura do código (achado da análise de 09/10). Custo em
  produção não medido.
- **Validar:** no Datadog, a duração dos spans de `esteira_baixar` que passam
  por `liberacao_processos` e quantos processos ela pega por execução.
- **Correção:** entender por que a cessão é liberada aqui (histórico ou regra
  de negócio) antes de mexer; se não houver motivo, mover para a esteira de
  cessão.

## B7 — Laço sem pausa na baixa do registro

- **Onde:** `EstadoBaixandoRegistro.aplica_transicao_estado`
  (`cessao/framework/liquidacao/estados_baixa.py:151-166`). Enquanto houver
  requisição de arranjo não registrada (`emissores/registro.py:98-104`), ele
  devolve o próprio estado com `is_estado_async() = False`. O laço da
  `ManagerBase.iniciar` (`cessao/framework/base.py:28-33`) repete na hora, sem
  pausa.
- **Efeito:** um `COUNT` atrás do outro no mesmo worker, dentro da mesma
  transação, até a contagem zerar. Se a requisição nunca for registrada, o
  worker fica preso.
- **Confirmado:** leitura do código. Não se sabe se acontece em produção: o
  emissor de registro não se aplica a produtos de arranjo
  (`registro.py:69-77`), então depende de existir requisição de arranjo
  pendente em lote de produto que usa registro.
- **Validar:** no Datadog, tasks `esteira_baixar` longas com muitas execuções
  da consulta de contagem.
- **Correção:** tratar o estado como assíncrono (pausa e retoma por
  callback ou reagendamento), ou limitar as tentativas.

## B8 — Status de contrato pode não ser gravado (corrida)

- **Onde:** `EstadoLiberar.aplica_transicao_estado`
  (`cessao/framework/liquidacao/estados_baixa.py:78-88`) enfileira
  `atualiza_status_contrato_task` (`:86`) **antes** de gravar o lote como
  `concluido` (`:87`). A task só grava `contrato_transacao` se todos os lotes
  do contrato estiverem `concluido` (`tasks/liquidacao_lote.py:209-214`).
- **Efeito:** se o worker pegar a task antes do commit, o lote ainda aparece
  como `liberado`, o contrato é descartado e nada tenta de novo. O contrato
  quitado fica sem o marco de liquidação, que é usado para permitir nova
  cessão do título, nas regras de duplicidade e na baixa do registro.
- **Confirmado:** a ordem está no código. Se acontece em produção, não foi
  medido.
- **Validar:** contar lotes `concluido` com contratos de parcelas todas
  fechadas e sem `contrato_transacao` de liquidação ou cancelamento.
- **Correção:** enfileirar depois do commit. Relacionado ao B3 (mesma task) e
  ao opcional O3 da [tarefa 03](tarefas/03-analise-do-fechamento.md).

## Menores

- `export_batches` no BFF está sem `self` (`business.py:326-328`); a rota
  `GET .../fake-batches/export` daria 500. O front não chama.
- `GET .../real-batches//statement` no BFF tem barra dupla no caminho; o
  front não chama.
- O BFF cria um `httpx.AsyncClient` novo a cada chamada à cessão, sem reuso de
  conexão (`src/services/platform_cessao/__init__.py:29-90`).
