# Depois da V2 — possibilidades

Melhorias levantadas durante a V2 que **ficaram para depois** de concluir as
tarefas. Não estão na [estimativa](estimate.md) nem no calendário. Cada
item diz de onde veio, quando foi adiado e o que falta para retomar.

| Item | Origem | Adiado em | Para retomar |
|---|---|---|---|
| P1 — Q1 recebe a origem pedida | [tarefa 03](tasks/03-closing-analysis.md#problemas), 5 h | 13/10/2026 | substituição do legado pelo `refact.py`; só afeta a rota antiga, o Atlas, a varredura e o automático |
| P3 — trava expirada (`@max_calls`) não vira 500 | [tarefa 03](tasks/03-closing-analysis.md#8-proposta-consolidada), 3 h | 13/10/2026 | idem; vale também para as outras 3 rotas com o decorator |
| P4 — `EXISTS` em vez de `lote.pagamentos` na `esteira_baixar` | [tarefa 03](tasks/03-closing-analysis.md#8-proposta-consolidada), 2 h | 13/10/2026 | idem; esteira compartilhada por todos os fluxos |
| [Índices para o fechamento de lote](#índices-para-o-fechamento-de-lote) | [tarefa 03](tasks/03-closing-analysis.md), antigo P6 (12 h) | 13/10/2026 | DBA; medir o efeito das etapas 1 e 2 da tarefa 03 antes |

## Índices para o fechamento de lote

As consultas Q1 (agrupamento) e Q2 (busca de ids) estão descritas na
[análise da tarefa 03](tasks/03-closing-analysis.md#2-as-duas-consultas).
Retomar depois que a tarefa 03 estiver em produção, comparando os números com
a [evidência de 09/10](evidence/batch-closing-datadog-2026-10-09.md): o
P1 e o UPDATE único reduzem o número de buscas, e o que sobrar é o custo que
um índice atacaria.


#### Problema

A Q1 e a Q2 precisam achar "os pagamentos **sem lote** de um produto,
originador, fundo e origem, com liquidação em `cadastrado`". Hoje isso leva
minutos (p95 de 5,6 a 8,1 min).

#### Como é hoje

Índice é uma estrutura que deixa o banco achar linhas sem ler a tabela
inteira.

- **No código e nas migrations [C]:**
  - `liquidacao_pagamento` tem índices de **uma coluna** em
    `liquidacao_lote_id`, `origem_pagamento`, `liquidacao_processo_uuid` e
    `parcela_id`;
  - `liquidacao_processo` tem índices em `produto_id`, `proc_id` e
    `data_criacao::date`;
  - **`estado_atual` não tem índice.**
  - Confirmar no banco: pode haver índice criado à mão.
- **Plano de execução:** não temos. O plano é o caminho que o Postgres escolhe
  para responder.
  - [H] Ele parte de um conjunto grande (todos os pagamentos do produto, ou
    todos os sem lote) e cruza 4 tabelas linha a linha.

#### O que mudaria

Candidatos, a fechar com a DBA depois do `EXPLAIN`:

- **Índice parcial** em `liquidacao_pagamento`, só com as linhas
  `WHERE liquidacao_lote_id IS NULL`, nas colunas de junção e de filtro
  (`liquidacao_processo_uuid`, `parcela_id`, `origem_pagamento`).
  - Índice parcial guarda só as linhas que atendem à condição. Como um
    pagamento sai dele ao entrar em lote, ele contém só o que está pendente.
- **Índice composto** em `liquidacao_processo (produto_id, estado_atual)`.
- **Como criar:** numa migration **nova**, com `CREATE INDEX CONCURRENTLY`, que
  cria o índice sem bloquear as gravações na tabela.

#### Benefício esperado

A Q1 e a Q2 leem só os pendentes, em vez do histórico inteiro. **Sem número
até o `EXPLAIN`**: o ganho depende de quantos pagamentos estão sem lote, que
ainda não medimos.

#### Riscos

- **Escrita mais cara:** todo índice pesa no INSERT e no UPDATE. A entrada de
  pagamentos já custa 1,1 s por INSERT em `liquidacao_processo` ([baseline](evidence/baseline-datadog-2026-10-05.md)).
  - O índice parcial só é mexido enquanto o pagamento está pendente, o que
    reduz o efeito. Medir antes e depois.
- **Criação:** o `CONCURRENTLY` não pode rodar dentro de transação e, se
  falhar, deixa um índice inválido, que precisa ser apagado.
- **Uso:** o Postgres pode não usar o índice. Só o `EXPLAIN` antes e depois
  prova.
- **Dono:** a DBA (decisão de 05/10).

#### Como obter as métricas (na réplica)

```sql
-- tamanho das tabelas
SELECT relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid))
  FROM pg_stat_user_tables
 WHERE relname IN ('liquidacao_pagamento', 'liquidacao_processo',
                   'contrato_parcela', 'contrato', 'contrato_processo');

-- quantos pagamentos estão sem lote (define o tamanho do índice parcial)
SELECT count(*) FILTER (WHERE liquidacao_lote_id IS NULL) AS sem_lote,
       count(*) AS total
  FROM liquidacao_pagamento;

-- índices reais e quanto são usados
SELECT relname, indexrelname, idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid))
  FROM pg_stat_user_indexes
 WHERE relname IN ('liquidacao_pagamento', 'liquidacao_processo');
```

Depois, `EXPLAIN (ANALYZE, BUFFERS)` da Q1 e da Q2 com um caso real (produto
713, originador 1282, fundo 209). O SQL completo está nos spans do APM, hashes
`9544189cfdc7d6a9` e `af6c090c7fa63323`.

## Acúmulo de liquidações e a cessão (B12)

**Prioridade alta**: a correção é importante, vira tarefa nova quando as
tarefas atuais acabarem, junto com os outros itens deste documento.

- **Problema:** o acúmulo (`acumula_liquidacoes`) vincula o pagamento ao lote
  vigente quando a liquidação vira `cadastrado`, sem olhar a cessão. Detalhes
  em [B12](bugs-found.md#b12--acúmulo-de-liquidações-ignora-o-estado-da-cessão-importante).
- **Correção proposta:** em `insert_pagamento_into_lote`, só vincular se a
  cessão do contrato estiver `cadastrado`; senão o pagamento fica sem lote e
  entra pelo fechamento novo (D9 revista). Atenção: o lote vigente passa a
  acumular menos e mais devagar; o negócio precisa aceitar.
- **Antes de abrir a tarefa:** medir na réplica quantos pagamentos estão em
  lote vigente com a cessão diferente de `cadastrado`. Se der zero, o risco é
  só teórico; se não, o número justifica a urgência.

```sql
SELECT count(*)
  FROM liquidacao_pagamento lp
  JOIN liquidacao_lote_processo l ON l.id = lp.liquidacao_lote_id
  JOIN liquidacao_lote_vigente v ON v.liquidacao_lote_id = l.id
  JOIN contrato_parcela cp ON cp.id = lp.parcela_id
  JOIN contrato c ON c.id = cp.contrato_id
  JOIN contrato_processo cpr ON cpr.uuid = c.processo_uuid
 WHERE cpr.estado_atual <> 'cadastrado'
   AND cpr.data_delete IS NULL;
```

(Os nomes das colunas de ligação entre lote e vigente precisam ser
conferidos no modelo antes de rodar.)
