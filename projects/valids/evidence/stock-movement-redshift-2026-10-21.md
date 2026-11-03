# Mov. Estoque — views do lake e reconciliação de set/26 (21/10/2026)

Consultas rodadas em 21/10/2026 no Redshift do lake, só leitura, sempre
filtradas por `data_ref`. Valores em R$ mi, salvo indicação. Fundos por letra
e administradores por análogo (ver `CLAUDE.md`). Os dados das views ainda não
foram validados.

## Como medir de novo

```bash
python3 -m venv <venv> && <venv>/bin/pip install redshift_connector
<venv>/bin/python -I attachments/rsq.py "$(cat consulta.sql)"
```

As consultas estão em `attachments/sql/`. Os parâmetros (`:inicio`, `:fechamento`
etc.) são substituídos à mão; o valor de `source` de cada análogo está no
`privado.md`.

## Tamanho das tabelas

[views_profile.sql](../attachments/sql/views_profile.sql), consulta 3. Todas com
sortkey `data_ref` e distribuição `AUTO(EVEN)`.

| Tabela (`plgn_physical`) | Linhas | Tamanho |
|---|---|---|
| `administradores_estoque` (por parcela) | 7,9 bi | ~989 GB |
| `administradores_estoque_contrato` | 2,6 bi | ~294 GB |
| `administradores_liquidacao` | 240 mi | ~31 GB |
| `administradores_aquisicao` | 224 mi | ~23 GB |

Um fechamento da view por parcela tem ~35 mi de linhas (31/08/2026: BGT
11,1 mi, Genius 17,9 mi, Kanastro 5,7 mi, Fydd 0,8 mi, Dayvale 12 mil), com
`id_parcela` sempre preenchido.

## As views

**[C]** As quatro views de `plgn` são `SELECT * FROM plgn_physical.<tabela>
WITH NO SCHEMA BINDING` (late-binding): não aparecem em
`information_schema.columns`; as colunas saem da tabela física (consultas 1 e 2).

## Aquisição: arquivo diário de eventos

Consulta 4, de 13 a 20/10/2026.

- **[C]** Em todos os dias e administradores, `data_ref` = `data_aquisicao`.
- **[C]** Por dia: BGT ~2,3–4,6 mil linhas em 3–5 fundos, parte por contrato
  (sem `id_parcela`); Genius ~27–60 mil; Kanastro ~24–111 mil; QY ~61–556 mil,
  não todo dia; Dayvale só em 14/10 (880 mil linhas, R$ 114,2 mi).
- Em set/26: BGT R$ 233,53 mi (7 fundos), Genius R$ 271,55 mi, QY R$ 542,99 mi,
  Kanastro R$ 73,49 mi, Fydd R$ 8,60 mi, Dayvale nada.

## Liquidação: tipos e preenchimento

Consulta 5, set/26. `vp` = soma de `vl_presente`.

| Administrador | Tipo | Linhas | Pago | Nominal | VP |
|---|---|---|---|---|---|
| BGT | `InstallmentPayment` | 77.827 | 159,17 | 150,54 | 0 |
| BGT | `Payment` | 228.384 | 46,99 | 149,41 | 0 |
| Dayvale | 4 tipos | 613 | 8,31 | 10,13 | 8,68 |
| Fydd | `BAIXA` | 34.787 | 8,10 | 6,96 | 6,91 |
| Fydd | `HONORARIOS` | 218 | 0,01 | 0,07 | 0,06 |
| Genius | 10 tipos | 1,76 mi | 289,57 | — | nulo |
| Kanastro | 3 tipos | 592.723 | 115,50 | 205,70 | nulo |
| QY | 5 tipos | 840.842 | 36,24 | — | nulo |

- **[C]** `vl_presente` só em Dayvale e Fydd (P3).
- **[C]** BGT `Payment` × `InstallmentPayment`: em 15/09, nenhum contrato com
  os dois tipos no mesmo dia.
- **[C]** QY em 15–16/10: estorno e reembolso com `vl_pago` positivo (P4).

## Estoque por administrador e fonte atual

Consulta 6, 30/09/2026, VP.

| Administrador | `administradores_estoque_contrato` | `plgn.estoque_contrato` |
|---|---|---|
| BGT (13 fundos) | 1.273,07 | 1.273,07 |
| Genius (8) | 1.203,22 | 1.203,22 |
| Kanastro (1) | 1.680,38 | 1.682,33 |
| QY (1) | 512,61 | 512,61 |
| Fydd (1) | 155,51 | 155,51 |
| Dayvale (1) | 53,54 | 53,54 |
| INTERNAL (14) | 11.742,65 | 11.737,56 |

**[C]** 4 CNPJs da INTERNAL também aparecem por um administrador: BGT D,
Fydd A, Genius D e Genius E (P2).

## Reconciliação residual de set/26

Consulta 7, 31/08 → 30/09/2026. Residual = estoque real − saldo inicial −
aquisições + baixas (`vl_pago`, todos os tipos).

| Fundo | Saldo inicial | Aquisições | Baixas | Estoque real | Residual | % do saldo |
|---|---|---|---|---|---|---|
| BGT A | 363,21 | 40,39 | 27,49 | 345,32 | −30,79 | −8,5% |
| BGT B | 277,67 | — | 10,96 | 270,24 | 3,52 | 1,3% |
| BGT C | 148,58 | — | 9,11 | 145,12 | 5,65 | 3,8% |
| BGT D | 142,90 | — | 4,52 | 144,77 | 6,39 | 4,5% |
| BGT E | 131,16 | 64,75 | 74,24 | 121,37 | −0,29 | −0,2% |
| BGT F | 92,04 | 48,52 | 72,45 | 101,10 | 33,00 | 35,9% |
| BGT G | 54,21 | — | 2,29 | 52,77 | 0,86 | 1,6% |
| BGT H | 46,32 | 2,64 | 4,27 | 45,43 | 0,74 | 1,6% |
| BGT I | 8,56 | 19,90 | 0,39 | 29,68 | 1,60 | 18,7% |
| BGT J | 7,68 | — | 0,37 | 7,44 | 0,12 | 1,6% |
| BGT K | 4,83 | — | 0,04 | 4,87 | 0,08 | 1,6% |
| BGT L | 2,32 | — | 0,02 | 2,33 | 0,04 | 1,6% |
| BGT M | 0,92 | 0,50 | 0,00 | 2,63 | 1,22 | 133% |
| BGT N | — | 56,84 | — | — | — | — |
| Dayvale A | 55,26 | — | 8,31 | 53,54 | 6,59 | 11,9% |
| Fydd A | 150,13 | 8,60 | 8,11 | 155,51 | 4,89 | 3,3% |
| Genius A | 2.011,86 | 153,75 | 172,77 | — | — | — |
| Genius B | 386,38 | 57,39 | 46,35 | 444,16 | 46,73 | 12,1% |
| Genius C | 347,70 | 30,05 | 37,91 | 349,64 | 9,80 | 2,8% |
| Genius D | 221,39 | 16,07 | 12,32 | 218,67 | −6,47 | −2,9% |
| Genius E | 121,27 | 11,90 | 11,80 | 125,17 | 3,81 | 3,1% |
| Genius F | 57,69 | 2,21 | 8,18 | 61,68 | 9,97 | 17,3% |
| Genius G | 2,94 | — | 0,17 | 2,96 | 0,20 | 6,8% |
| Genius H | 0,43 | 0,18 | 0,04 | 0,62 | 0,05 | 10,7% |
| Genius I | 0,30 | — | 0,01 | 0,33 | 0,04 | 12,0% |
| Kanastro A | 1.669,67 | 73,49 | 115,50 | 1.680,38 | 52,71 | 3,2% |
| QY A | — | 542,99 | 36,24 | 512,61 | — | — |

## Roll-forward por parcela

[reconciliation_by_installment.sql](../attachments/sql/reconciliation_by_installment.sql)
(sem o taxa × prazo), 31/08 → 30/09/2026.

| Fundo | Ficaram: variação do VP | Saíram: VP em 31/08 | Entraram: VP em 30/09 |
|---|---|---|---|
| Fydd A | +1,28 (777.550 parcelas) | 6,10 (30.554) | 10,20 (59.355) |
| BGT G | +0,38 (13) | 1,81 (1) | — |

**[C]** Fydd A fecha exato com a baixa a VP: 150,13 + 8,60 (aquisições) −
6,98 (VP baixado) + 3,76 = 155,51. Os 3,76 = 1,28 (ficaram) + 1,60 (VP em 30/09
das que entraram − `vl_aquisicao`) + 0,88 (`vl_presente` na baixa − VP em 31/08
das que saíram). Com a baixa pelo `vl_pago` (8,11), sobram 1,13, que batem com
o `vl_ajuste` (−1,18).

## Taxa × prazo × variação real do VP

[reconciliation_by_installment.sql](../attachments/sql/reconciliation_by_installment.sql),
31/08 → 30/09/2026, `:du_periodo` = 21 e `:dc_periodo` = 30. Só parcelas
presentes nos dois fechamentos. "BGT B+H+L" = filtro pelo final de CNPJ comum
aos três fundos.

| Fundo | Grupo | Parcelas | VP em 31/08 | Variação real | Taxa × prazo |
|---|---|---|---|---|---|
| Fydd A | a vencer | 57.663 | 14,84 | 1,09 | 1,09 |
| Fydd A | venceu no mês | 5.391 | 1,85 | 0,19 | 0,19 |
| Fydd A | vencida em 31/08 | 714.496 | 127,34 | 0,00 | 0,00 |
| Dayvale A | a vencer | 8.485 | 33,19 | 0,58 | 0,57 |
| Dayvale A | venceu no mês | 205 | 0,96 | 0,01 | 0,01 |
| Dayvale A | vencida em 31/08 | 3.122 | 12,75 | 0,00 | 0,00 |
| Kanastro A | a vencer | 1,46 mi | 287,44 | 49,57 | 49,53 |
| Kanastro A | venceu no mês | 206.880 | 66,83 | 1,19 | 1,97 |
| Kanastro A | vencida em 31/08 | 3,60 mi | 1.198,48 | −2,03 | 0,00 |
| Genius C | a vencer | 889.938 | 169,47 | 10,84 | 12,62 |
| Genius C | venceu no mês | 42.147 | 10,90 | 0,48 | 0,44 |
| Genius C | vencida em 31/08 | 530.597 | 128,62 | 0,36 | 0,00 |
| BGT B+H+L | a vencer | 7,72 mi | 300,02 | 4,46 | 5,53 |
| BGT B+H+L | venceu no mês | 57 | 1,44 | 0,03 | 0,03 |
| BGT B+H+L | vencida em 31/08 | 402 | 2,95 | −0,02 | 0,00 |

Métodos vistos: Fydd, Dayvale e Kanastro `expb252_aa`; Genius `exp360_aa`;
BGT `expb252_aa` e `exp360_aa` (e `exp365_aa` em outros fundos).

**Taxa implícita (amostra):** 4 parcelas a vencer por administrador em
30/09/2026, comparando `(nominal ÷ VP)^(base ÷ prazo) − 1` com as colunas de
taxa. **[C]**
- **Kanastro:** a taxa implícita é igual à `taxa_cessao`.
- **Dayvale:** a implícita fica entre a `taxa_cessao` e a `taxa_recebivel`.
- **Fydd e Genius:** a implícita é igual à `taxa_recebivel`.
- **BGT:** não bate; a implícita cai com o prazo (P8).

## Conferência com o accrual mensal

[accrual_by_day.sql](../attachments/sql/accrual_by_day.sql), numa foto só, sobre
31/08/2026 (`:du_periodo` = 21, `:dc_periodo` = 30), cruzado com a tabela de
reconciliação acima. Baixas pelo `vl_pago`, ainda sem o mapa de sinal (D5).
Conferência = (saldo calculado − estoque real) ÷ estoque real.

| Fundo | Accrual | Saldo calculado | Estoque real | Conferência |
|---|---|---|---|---|
| BGT A | 16,17 | 392,28 | 345,32 | +13,6% |
| BGT B | 4,77 | 271,49 | 270,24 | +0,5% |
| BGT C | 5,75 | 145,22 | 145,12 | +0,1% |
| BGT D | 5,93 | 144,31 | 144,77 | −0,3% |
| BGT E | 1,31 | 122,97 | 121,37 | +1,3% |
| BGT F | 1,51 | 69,61 | 101,10 | −31,1% |
| BGT G, J, K, L | sem taxa | — | — | — |
| BGT H | 1,03 | 45,71 | 45,43 | +0,6% |
| BGT I | 0,41 | 28,49 | 29,68 | −4,0% |
| BGT M | 0,05 | 1,46 | 2,63 | −44,7% |
| Dayvale A | 0,69 | 47,64 | 53,54 | −11,0% |
| Fydd A | 1,34 | 151,96 | 155,51 | −2,3% |
| Genius A | 52,61 | 2.045,45 | fora do arquivo | — |
| Genius B | 43,69 | 441,12 | 444,16 | −0,7% |
| Genius C | 14,72 | 354,57 | 349,64 | +1,4% |
| Genius D | 14,78 | 239,91 | 218,67 | +9,7% |
| Genius E | 3,26 | 124,62 | 125,17 | −0,4% |
| Genius F | 3,81 | 55,52 | 61,68 | −10,0% |
| Genius G | 0,20 | 2,96 | 2,96 | 0,0% |
| Genius H | 0,03 | 0,60 | 0,62 | −2,8% |
| Genius I | 0,03 | 0,32 | 0,33 | −2,8% |
| Kanastro A | 55,35 | 1.683,02 | 1.680,38 | +0,2% |
| QY A | sem estoque em 31/08 | — | 512,61 | — |

## Taxa do recebível × taxa de cessão (22/10/2026)

Mesma consulta da seção "Taxa × prazo × variação real do VP", calculando o
accrual com cada coluna de taxa (e o método correspondente), parcelas a vencer
que ficaram no estoque de 31/08 a 30/09/2026.

| Fundo | Parcelas | Variação real | Com `taxa_recebivel` | Com `taxa_cessao` |
|---|---|---|---|---|
| Fydd A | 57.663 (nenhuma sem uma das taxas) | 1,092 | 1,088 (−0,3%) | 1,073 (−1,7%) |

Genius C e Dayvale A: consultas paradas em ~59,9 s, no limite de 60 s do
cliente de teste (`statement_timeout` do `attachments/rsq.py`); a mensagem foi
"system requested abort", código 1020. Nenhuma regra do Redshift agiu nelas
(ver estimativa de custo abaixo). Não repetidas.

## Plano de execução: fórmula × roll-forward (22/10/2026)

`EXPLAIN` (não executa a consulta) de um dia, todos os fundos, fotos de 29 e
30/09/2026. O `attachments/rsq.py` passou a aceitar `EXPLAIN`.

- **Fórmula** ([accrual_by_day.sql](../attachments/sql/accrual_by_day.sql)):
  `HashAggregate` sobre um `Seq Scan` filtrado por `data_ref`. Sem junção e sem
  redistribuição.
- **Roll-forward** (junção das duas fotos por `source`, `cnpj_classe` e
  `id_parcela`): `Hash Full Join DS_DIST_BOTH`, com as duas fotos
  redistribuídas pela chave `id_parcela` antes da junção.
- O planejador estima `rows=1` para a tabela, então os números de custo não
  servem para comparar. O tempo real só sai de um teste executado.

## Consulta única por intervalo: teste no Fydd A (22/10/2026)

[movement_by_interval.sql](../attachments/sql/movement_by_interval.sql),
`:foto_anterior` = 31/08/2026, `:foto` = 30/09/2026, com filtro de
administrador e fundo em todas as CTEs (só para o teste). Estornos e tipos
ignorados com as listas da QY (não afetam o Fydd).

| Coluna | R$ mi |
|---|---|
| `opening_balance` | 150,13 |
| `acquisitions` | 8,60 |
| `liquidations` | 8,11 |
| `interest_accrual` | 1,28 |
| `closing_balance` | 155,51 |
| `paid_on_remaining` | 0,00 |
| `pv_entered` | 10,20 |
| `pv_exited` | 6,10 |

**[C]** Bate com a reconciliação e o roll-forward de 21/10. Conferência:
155,51 − (150,13 + 8,60 − 8,11 + 1,28) = 3,61 = (10,20 − 8,60) + (8,11 − 0 − 6,10).
Custo com todos os fundos ainda não medido (D23).

## Fydd A duplicado sob a fonte Dayvale em 14/10 (23/10/2026)

**[C]** Consultas de um dia, agrupadas por fonte e final de CNPJ:

| View | Data | Fonte | Fundo | Linhas | `vl_aquisicao` |
|---|---|---|---|---|---|
| aquisição | 14/10 | Dayvale | Fydd A | 879.974 | 114,22 |
| estoque (parcela) | 14/10 | Fydd | Fydd A | 879.974 | 114,22 |
| estoque (parcela) | 14/10 | Dayvale | Fydd A | 879.974 | 114,22 |
| estoque (parcela) | 14/10 | Dayvale | Dayvale A | 11.843 | 37,29 |
| estoque (parcela) | 21/10 | Dayvale | (1 fundo) | 11.745 | — |
| estoque (parcela) | 21/10 | Fydd | (1 fundo) | 879.974 | — |

Em 21/10, a view por parcela tem as 6 fontes: BGT (12 fundos), Dayvale (1),
Fydd (1), Genius (8), Kanastro (1) e QY (1, 15,6 mi de parcelas). A fonte
INTERNAL não existe nesta view.

## Roll-forward por contrato × por parcela: Kanastro A (23/10/2026)

31/08 → 30/09/2026, consultas filtradas na fonte do Kanastro. Por contrato:
`administradores_estoque_contrato` juntado por `id_contrato_admin`, com os
pagamentos da liquidação por contrato. Por parcela:
[movement_by_interval.sql](../attachments/sql/movement_by_interval.sql).

| | Por contrato | Por parcela |
|---|---|---|
| Contratos / parcelas na junção | 890.153 contratos | — |
| Saldo inicial / estoque real | 1.669,67 / 1.680,38 | 1.669,67 / 1.680,38 |
| Aquisições / baixas | 73,49 / 115,50 | 73,49 / 115,50 |
| Variação do VP de quem ficou | −33,01 | +48,73 |
| Pagamentos de quem ficou | 91,80 | 6,07 |
| Accrual | 58,78 | 54,80 |
| VP das entradas / saídas | 62,58 / 18,86 | 78,90 / 116,93 |
| Conferência | −6,07 | −2,09 |

## Estimativa de custo pelo histórico do Redshift (23/10/2026)

Tempo, linhas e bytes das consultas já rodadas, lidos de `stl_query`,
`svl_query_summary` e `stl_scan` (só leitura do log). Nenhuma gravou em disco
no meio (`is_diskbased` falso).

| Consulta (query id) | Tempo | Lido nas views | Maior volume num passo |
|---|---|---|---|
| Uma foto inteira, todos os fundos, agregada (48166630) | 2,8 s | 37 mi de linhas, 2,25 GB | 23,5 mi |
| Um intervalo de movimentação, Kanastro filtrado, 31/08→30/09 (49309029) | 4,8 s | 33 mi de linhas, 0,95 GB | 6,1 mi |
| Um intervalo, Fydd filtrado (49088226) | 2,9 s | — | 0,9 mi |
| Roll-forward por contrato, Kanastro (49308996) | 2,3 s | — | 1,3 mi |

- **[C]** As consultas que pararam em 22/10 (48190494, 48196752, 48196966)
  levaram 59,9 s: o `statement_timeout` de 60 s do cliente de teste. Não há
  ação de regra do Redshift para elas em `stl_wlm_rule_action`. As regras
  configuradas (`stv_wlm_qmr_config`) não são visíveis para este usuário.
- **[C]** Filtrar por fonte e fundo reduz também a leitura: as duas fotos do
  Kanastro leram 33 mi de linhas, menos que uma foto inteira (37 mi). As
  linhas parecem gravadas agrupadas por fonte, e os blocos de outras fontes
  são pulados.
- **[H]** Extrapolação, linear nas linhas, sem gravar em disco:
  - período de 5 dias, um fundo do tamanho do Kanastro: 10 a 30 s;
  - período de 5 dias, todos os fundos: alguns minutos (3 a 10), com risco de
    gravar em disco na junção;
  - um dia na consolidação, todos os fundos: ~30 a 60 s;
  - backfill de 2 anos (~500 dias, um por vez): ~4 a 8 h de worker.
- Para medir uma execução real, consultar `stl_query` e `svl_query_summary`
  pelo id da consulta (`SELECT pg_last_query_id()` na mesma sessão).

### Execuções reais da consulta do período (23/10/2026)

[period_movement_test.sql](../attachments/sql/period_movement_test.sql),
rodada pelo Heitor; tempos de `stl_query`, volume de `svl_query_summary`.

| Execução (query id) | Tempo | Maior volume num passo | Gravou em disco |
|---|---|---|---|
| Kanastro A filtrado, 16 a 22/10 (49946135) | 19,4 s | 58,7 mi | sim |
| **Todos os fundos, 16 a 22/10 (49955340)** | **166,3 s** | 389 mi | sim |
| Kanastro A, leitura do estoque desde 15/08, mesmos 5 pares (49960439) | 20,1 s | 58,7 mi | sim |
| Kanastro A, leitura do estoque de 1 ano, mesmos 5 pares (49962596) | 23,3 s | 58,7 mi | sim |

- **[C]** Todos os fundos, 5 intervalos: ~33 s por intervalo diário. Confirma
  ~30 a 60 s por dia na consolidação e ~4 a 5 h de backfill para 2 anos.
- **[C]** A execução "1 ano" só alargou o filtro da CTE `estoque`; a CTE
  `pares` ficou com os 5 pares de 16 a 22/10, então o resultado é o da mesma
  semana. Um ano de verdade pede ~250 pares.
- **[H]** Um ano numa consulta só: ~15 a 20 min ou mais filtrado num fundo do
  tamanho do Kanastro, e mais de 2 h com todos os fundos. Por isso a
  consolidação calcula um dia por vez.

## Otimização da consulta da movimentação (23/10/2026)

Cada consulta foi rodada com `enable_result_cache_for_session` desligado, em
transação só de leitura. Tempos do `stl_query`; volume e disco do
`svl_query_summary`. Os resultados das versões são idênticos até o centavo.

| Consulta | Fundo | Tempo | Processado | Redistribuído | Passos em disco |
|---|---|---|---|---|---|
| Intervalo v0 (atual até 23/10) | Kanastro A | 6,9 s | 4,89 GB | 1,78 GB | 0 |
| Intervalo v2 (chave numérica) | Kanastro A | 5,9 s | 3,24 GB | 0,93 GB | 0 |
| Intervalo v0 | QY A | 14,9 s | 11,56 GB | 4,19 GB | 1 |
| Intervalo v2 | QY A | 7,7 s | 7,77 GB | 2,22 GB | 1 |
| Intervalo v3 (v2 + chave do fundo numérica) | QY A | 7,8 s | 9,04 GB | 2,22 GB | 0 |
| Intervalo v4 (agrupando por texto) | QY A | 13,9 s | 11,95 GB | 3,18 GB | 0 |
| Período B0 (atual), semana | Kanastro A | 24,3 s | 61,66 GB | 10,59 GB | 3 |
| Período P2 (janela), semana | Kanastro A | 17,3 s | 16,85 GB | 2,63 GB | 0 |
| Período P1, semana | Kanastro A | 5,9 s | 10,20 GB | 2,19 GB | 0 |
| Período P1 com datas descobertas na consulta, semana | Kanastro A | 25,4 a 30,3 s | 24 a 26 GB | 2,18 GB | 0 |
| Período P1, mês (22 intervalos) | Kanastro A | 33,7 s | 42,59 GB | 9,31 GB | 0 |

- **[C] Execuções do Heitor no DBeaver (23/10, ~18h20 a 18h35, horário de
  Brasília), lidas de `stl_query` e `stl_wlm_query`:** a consulta P1 do último
  mês do Kanastro A (22/09 → 22/10) levou **26,7 s** (50174743), sem espera
  na fila. Os `SELECT *` das CTEs `estoque` e `lados` (centenas de milhões de
  linhas para o cliente) levaram de 100 a 500 s, quase todos cancelados; o
  `COUNT(*)` da `estoque`, 1,6 s.
- **Como medir uma parte da consulta:** agregar o resultado numa linha
  (`COUNT(*)`, `MAX` da chave, `SUM` dos valores). `SELECT *` de uma CTE mede
  sobretudo a devolução das linhas pelo nó líder até o cliente: no teste do
  Heitor (23/10), o `COUNT(*)` da CTE `estoque` de um mês do Kanastro A foi
  rápido e o `SELECT *` (~130 mi de linhas) demorou. Só `COUNT(*)` também
  engana para menos: o Redshift nem lê as colunas que não usa.
- O passo que gravava em disco na v2 da QY é a tabela da junção (15,6 mi de
  linhas, ~1,25 GB contra ~823 MB de memória do passo).
- Alertas do Redshift na versão antiga de período: 24 de "muitas linhas
  redistribuídas para a agregação" e 1 de junção em laço.

## Tempo da tela ao trocar o fundo (23/10/2026)

Só a CPU da data-lake-api, medida localmente com dados sintéticos no formato
real ([measure_fund_switch.py](../attachments/measure_fund_switch.py)); sem rede
e sem o lake.

| Parte | Volume | Tempo |
|---|---|---|
| Mov. Estoque: ler 2 anos do Redis (`MGET`), filtrar o fundo e somar | 502 dias × 24 fundos, 3,6 MB | 32 ms |
| Estoque com cache: ler, aplicar a D8 e montar a resposta de todos os fundos | 15 mil linhas, 3,3 MB (resposta de 2,0 MB) | 203 ms |

- **[H]** Com a rede (Redis e BFF, alguns MB) e o BFF, trocar o fundo leva
  ~0,5 a 1 s. O front chama o estoque e, depois dele, a movimentação, porque o
  início do período vem do estoque.
- **[H]** Cache do estoque frio (primeira chamada do dia ou data fora da
  janela): a rota lê 2 anos de todos os fundos no Redshift. Tempo com a fonte
  da D7 não medido.
- Calcular a movimentação na hora, sem a consolidação (consulta P1, fundo do
  tamanho do Kanastro A): semana 5,9 s e mês 33,7 s (medidos); 2 anos ≥ 12 a
  15 min (projeção).

## Simulação da "poça", semana de 16 a 22/10 (26/10/2026)

A tabela `valid_stock_movement` simulada para todos os fundos, sem gravar nada:
[simulate_fund_movement.py](../attachments/simulate_fund_movement.py) `todos
2026-10-16 2026-10-22 --csv`, fundo a fundo, como a consolidação (só leitura
no Redshift). O CSV ficou fora da pasta (tem CNPJ).

- **[C]** 24 fundos de administrador na foto de 22/10: BGT 12, Genius 8,
  Kanastro, QY, Dayvale e Fydd 1 cada. 124 linhas: 5 dias por fundo, mais 4
  do Fydd A sob a fonte Dayvale (P5).
- **[C]** ~2,2 min no total, um fundo depois do outro: de 3 a 6 s por fundo
  pequeno, 11 s no Fydd A, 17 s na QY A (o Kanastro A saiu do cache de
  resultado). É o custo de um dia novo para todos, vezes 5.
- **[C]** Diferença da conferência acima de 1% do estoque real em 5 fundos,
  todos BGT: o BGT A (−1,7%), três fundos entre R$ 7 mi e R$ 52 mi (−1,6% a
  −4,5%) e um que está acabando (R$ 0,6 mi, −25%). Os demais ficaram abaixo
  de 1%; o Fydd A, em zero.

