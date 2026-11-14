# 05 — Posição de ativos no data-lake-api

Status: a começar (13/11/2026)

## Objetivo

Ampliar a rota de posição de ativos do data-lake-api para servir os quatro relatórios de estoque
das ondas 3 e 4, em vez de criar uma rota por relatório.

Estimativa: 10 dias sem IA, 5,5 com IA.

## Contexto

- A rota `POST /funds/{fund_legal_id}/assets/position` devolve o estoque de um fundo numa data e
  escolhe a tabela pelo administrador do fundo (`src/modules/funds/business/funds.py:207`) [C].
- Hoje ela exige a lista de contratos e só tem o ramo de um administrador [C]. Uma consulta sobre
  `credit_portfolio` já está escrita no arquivo de queries, mas a camada de negócio não a usa [C].
- O relatório do VLTS I usa o valor presente da métrica e a consulta pronta usa o valor presente
  justo; ela também junta a parcela pelo contrato, e não pela parcela da métrica [C]. Conferir
  qual valor o cliente recebe hoje antes de trocar.
- A Base de operações do FBRX3 junta o estoque do administrador BGT com pagamentos e taxas [C]:
  pode virar um ramo da rota ou uma consulta dedicada.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| DL1 | Lista de contratos opcional e resposta paginada | 1,5 | 0,5 | 03 |
| DL2 | Ramo `credit_portfolio` (VLTS I) | 2 | 1 | DL1 |
| DL3 | Ramo Dayvale, provavelmente no mesmo layout do ramo existente [H] | 1,5 | 1 | DL1 |
| DL4 | FBRX3: ramo da rota ou consulta dedicada | 2,5 | 1,5 | DL1 |
| DL5 | Endpoint da prévia SQL | 1 | 0,5 | DL1 |
| DL6 | Validação contra o SQL atual dos relatórios de estoque na mesma data | 1,5 | 1 | DL2, DL3, DL4 |

## Pronto quando

- [ ] Os ramos têm testes e o SQL fica em `src/infra/redshift/queries`.
- [ ] A comparação com os scripts bate para os quatro relatórios.
