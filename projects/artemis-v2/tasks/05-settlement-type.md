+++
card = "TS-5734"
type = "improvement"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-24
sprint = "TETRIS - Sprint 16.6.41"
synced = 2026-11-16
+++
# 05 — Tipo de baixa na tabela de pagamentos

- **Status:** mapeado; falta conferir o caso da Dots no banco.
- **Repos:** platform-cessao, front (o BFF só repassa).

## Item original

> Revisar campo "tipo de baixa" na tabela de pagamentos. Exemplo: Dots —
> 23/09/2026 — Lote ID 1828920

## Como o valor nasce

- Coluna `liquidacao_pagamento.tipo_liquidacao`, enum `EnumTipoRemessa`,
  padrão `baixa_sacado` (`cessao/database/models.py:6311-6313`).
- O parser coloca o nome do tipo no `data_raw` (CNAB500:
  `"03"`/`"13"` → baixa_sacado, `"14"` → pag_parcial, `"71"` → cancelamento,
  `cessao/parsers/cnab500/liquidacao.py:60-69`).
- A regra de pagamento do produto decide o tipo final
  (`cessao/framework/regras/liquidacao/tipo_pagamento.py`). Exemplo: no
  `PmtSaldo`, se a parcela fecha dentro de `MARGEM_FECHAMENTO = 2.00`, vira
  baixa_sacado; senão, pag_parcial.

## Como chega na tela

1. Cessão, `GET /liquidacao/pagamentos/query`: rotula como `tipo_baixa` e
   converte para o **valor** do enum (`cessao/api/liquidacao/service.py:1579-1584`).
2. BFF: repassa como `write_off_type` (`schemas.py:257`).
3. Front: `paymentWriteOffTypeLabel(...)` usa o mapa `PaymentWriteOffTypeLabels`,
   que está **vazio**, e cai num formatador que não mexe em dígitos. Resultado:
   a tela mostra o código cru.

Os códigos confundem:

| Nome | Valor |
|---|---|
| pag_parcial_critico | `04` |
| pag_parcial | `14` |
| baixa_aditamento | `77` |
| **baixa_sacado** | **`077`** |
| **cancelamento** | **`0077`** |
| **baixa_sem_financeiro** | **`00077`** |
| **baixa_seguro** | **`000077`** |
| estorno | `99` |

E cada endpoint devolve num formato:

| Endpoint | Formato |
|---|---|
| `/pagamentos/query` | valor (`"077"`) |
| `/baixa/pagamento` | nome (`baixa_sacado`) |
| `/pagamentos/rejeitados` | o que veio no `data_raw` |

## Conferir o caso da Dots

Consulta barata (índice em `liquidacao_lote_id`):

```sql
SELECT tipo_liquidacao, count(*)
FROM liquidacao_pagamento
WHERE liquidacao_lote_id = 1828920
GROUP BY 1;
```

Se o banco tiver o tipo certo e a tela mostrar errado, é só exibição. Se o
banco tiver o tipo errado, o problema está na regra do produto da Dots — aí
vale olhar as regras com a [consulta de configs](../attachments/sql/product_fund_configs.sql).

## Proposta

1. Cessão devolve o **nome** do enum em todos os endpoints da tela.
2. Front preenche `PaymentWriteOffTypeLabels` com rótulos legíveis.
3. Atenção à ordenação por `tipo_baixa` (`repository.py:1095-1099`), que hoje
   ordena pelo enum.

## Relacionado

- [B3 — Cancelamento gravado como liquidação](../bugs-found.md): usa o
  mesmo campo.

## Validação

- Teste do serializer com cada membro do enum.
- Na tela, o lote 1828920 mostrando o rótulo que bate com o banco.
