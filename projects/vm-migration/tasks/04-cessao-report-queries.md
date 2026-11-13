# 04 — Rotas de consulta no platform-cessao

Status: a começar (13/11/2026)

## Objetivo

Criar duas rotas de consulta no platform-cessao, contratos e liquidação (T17), que substituem o
SQL direto dos scripts no banco. Cada rota devolve as linhas paginadas e, num endpoint irmão, o
SQL que executaria com aqueles filtros (a prévia, T14).

Estimativa: 15 dias sem IA, 7,5 com IA.

## Contexto

- Não existe rota que consolide esses dados hoje. A mais próxima, `GET /cessao/query`, filtra
  pela data do processo e não pela data de cessão [C].
- A rota `/fundo/produtos` devolve os identificadores de acesso dos parceiros, que funcionam como
  credencial [C]. As opções dos filtros precisam de uma rota própria.
- Pagamento e processo: uma linha recebida para liquidar vira um processo e, quando traz o número
  da parcela (`pmt`), um pagamento só [C]: `cessao/conciliacao/conciliador_liquidacao.py:59` e
  `cessao/database/models.py:3293`. Sem a parcela, ou num cancelamento de contrato, o valor é
  repartido entre as parcelas abertas (`cessao/framework/regras/liquidacao/tipo_pagamento.py:269`
  e `:549`). A importação de contratos e a renegociação do administrador BGT criam pagamentos sem
  linha recebida [C].
- Só o pagamento tem a parcela, o lote e o tipo de liquidação aplicado [C]; o relatório do Vektor
  depende dos três.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| PC1 | Base: namespace novo, paginação com teto e cursor, SQL da prévia compilado do mesmo objeto de consulta que é executado | 3 | 1,5 | 03 |
| PC2 | Consulta Contratos: produto, fundo, estado do processo, intervalo de data de cessão, com parcela aberta | 2,5 | 1 | PC1 |
| PC3 | Consulta Liquidação: granularidade processo ou pagamento (junta parcela, contrato e lote), janela, estado, extratos, identificador, `agrupar_por` | 5 | 2,5 | PC1 |
| PC4 | Opções dos filtros (produtos, fundos, estados) sem identificadores de acesso | 1,5 | 0,5 | PC1 |
| PC5 | Token de serviço nas rotas novas, se D5 decidir que a validação é do serviço | 1 | 0,5 | D5 |
| PC6 | Validação na réplica, só leitura e com trava: linhas e totais iguais ao SQL dos scripts na mesma data; contar processos com mais de um pagamento por produto | 2 | 1,5 | PC2, PC3 |

## Pronto quando

- [ ] As duas rotas e a de opções têm testes e documentação.
- [ ] A comparação com o SQL dos scripts bate para a Onda 1 (contratos) e a Onda 2 (liquidação).
- [ ] A contagem de processos com mais de um pagamento está registrada em `evidence/`, sem dado de
      cliente.
