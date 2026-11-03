# Monitoramento de Inconsistências: views do lake (27/10/2026)

Consultas rodadas em 27/10/2026 no Redshift do lake, só leitura, sempre
filtradas por `data_ref`, foto de 30/09/2026 salvo indicação. Valores em R$ mi,
salvo indicação. Fundos por letra e administradores por análogo. Os dados das
views ainda não foram validados.

As consultas estão em
[inconsistency_monitoring.sql](../attachments/sql/inconsistency_monitoring.sql)
(como medir de novo: ver
[stock-movement-redshift-2026-10-21.md](stock-movement-redshift-2026-10-21.md#como-medir-de-novo)).

## Resumo

| Visualização | Dá para construir? | De onde |
|---|---|---|
| Performance de Pagamento | **sim** (sem a taxa média) | liquidação (valor de baixa, coluna "VP baixado", D46) + VP em carteira das parcelas que saíram, do estoque por parcela (linha "VP liquidado", D45), a mesma conta do `pv_exited` da Mov. Estoque |
| Lacunas de Parcelas | **sim, com ressalvas** | estoque por parcela (`num_parcela`, vencimento, VP, PDD) + liquidação (parcela posterior paga). Fydd fora (sem `num_parcela`); Dayvale sem casos (1 parcela por contrato); pesada |
| Análise Residual | **sim** | estoque por parcela (`vl_nominal_parcela` × `vl_aquisicao_parcela`) |

`dim_contrato` não é necessária em nenhuma das três (só para o filtro de
produto, como nas tarefas 02 e 03).

## Colunas usadas

Catálogo das tabelas físicas (`information_schema.columns`) **[C]**:

- `administradores_estoque` (por parcela): `num_parcela`, `id_parcela`,
  `data_vcto_original`, `flag_vencido`, `vl_nominal_parcela`,
  `vl_presente_parcela`, `vl_aquisicao_parcela`, `vl_pdd_parcela`,
  `taxa_recebivel`, `metodo_taxa_recebivel`.
- `administradores_liquidacao`: `num_parcela`, `id_parcela`, `data_vcto`,
  `data_pagamento`, `vl_pago`, `vl_nominal`, `vl_presente`, `tipo_movimento`.
- `administradores_estoque_contrato`: `qt_parcelas_pagas`,
  `qt_parcelas_vencidas`, `num_parcela_vigente` (ver P21).
- Nenhuma view traz o **total de parcelas do contrato** (P21).

## Análise Residual

Consulta 1, por administrador **[C]**:

| Administrador | Parcelas | Sem `num_parcela` | Nominal < aquisição | VP delas | Vencidas entre elas |
|---|---|---|---|---|---|
| BGT | 11.260.877 | 0 | 269.188 | 101,45 | 0 |
| Dayvale | 12.015 | 3.702 (31%) | 0 | — | — |
| Fydd | 836.905 | 836.905 (100%) | 1.207 | 0,05 | 1.207 |
| Genius | 6.366.216 | 1.871.799 (29%) | 13.599 | 1,12 | 12.773 |
| Kanastro | 5.706.122 | 0 | 90.787 | 11,32 | 90.787 |
| QY | 10.003.619 | 0 | 6.451 | 0,31 | 6.451 |

- **[C]** `vl_nominal_parcela` e `vl_aquisicao_parcela` sempre preenchidos; a
  BGT tem 502.423 parcelas com aquisição zero.
- **[C]** Fora da BGT, os casos são quase todos parcelas **vencidas**.
  **[H]** O nominal seria o saldo depois de pagamento parcial (o "residual");
  confirmar com uma parcela paga em parte na liquidação.

Consulta 2, parcelas por faixa de nominal ÷ aquisição (as faixas do protótipo)
**[C]**:

| Administrador | ≤ 0 | 0–10% | 10–20% | 20–30% | 30–40% | 40–50% | 50–60% | 60–70% | 70–80% | 80–90% | 90–100% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BGT | 0 | 93 | 76 | 150 | 451 | 671 | 38.675 | 8.300 | 25.225 | 48.787 | 146.760 |
| Fydd | 0 | 956 | 167 | 23 | 42 | 9 | 2 | 1 | 0 | 3 | 4 |
| Genius | 0 | 2.652 | 1.464 | 1.504 | 1.372 | 1.240 | 1.214 | 1.219 | 1.034 | 995 | 905 |
| Kanastro | 23.060 | 2.288 | 2.565 | 3.070 | 4.219 | 6.307 | 6.544 | 12.354 | 9.951 | 8.438 | 11.991 |
| QY | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 17 | 176 | 730 | 5.527 |

Consulta 3, BGT por fundo **[C]**:

| Fundo | VP | Parcelas | Nominal < aquisição | VP delas | Aquisição ÷ nominal do fundo |
|---|---|---|---|---|---|
| BGT A | 345,32 | 1.135.959 | 4.295 | 3,30 | 0,38 |
| BGT B, H e L (mesmo final de CNPJ) | 318,00 | 7.717.768 | 224.956 | 12,66 | 0,53 |
| BGT C | 145,12 | 652.936 | 0 | — | 0,22 |
| BGT D | 144,77 | 1.395.112 | 4.178 | 1,13 | 0,43 |
| BGT E e K (mesmo final) | 126,23 | 1.792 | 0 | — | 0,79 |
| **BGT F** | 106,13 | 46.102 | **35.759** | **84,35** | **1,81** |
| BGT G | 52,77 | 13 | 0 | — | 0,53 |
| BGT I | 29,68 | 274.895 | 0 | — | 0,47 |
| BGT J | 7,44 | 13 | 0 | — | 0,45 |
| BGT M | 2,63 | 36.287 | 0 | — | 0,37 |

**[C]** Na BGT F, a aquisição é 1,8× o nominal do fundo inteiro (P19). É o
fundo que recebeu carteira da BGT A em set/26 (P6). **[H]** A carteira
transferida entrou com o valor de aquisição da transferência.

### Pela view por contrato (29/10/2026)

`administradores_estoque_contrato`, foto de 30/09/2026 **[C]**:

| Administrador | Contratos | Aquisição zero | Nominal < aquisição | Desses, em atraso | VP deles | VP dos casos por parcela (consulta 1) |
|---|---|---|---|---|---|---|
| BGT | 1.818.924 | 52.264 | 102.101 | 548 | 92,75 | 101,45 |
| Dayvale | 12.015 | 0 | 0 | 0 | — | — |
| Fydd | 836.905 | 0 | 1.207 | 1.207 | 0,05 | 0,05 |
| Genius | 659.769 | 0 | 1.661 | 1.649 | 0,13 | 1,12 |
| Kanastro | 865.555 | 0 | 7.881 | 7.881 | 2,32 | 11,32 |
| QY | 2.884.549 | 0 | 282 | 282 | 0,01 | 0,31 |
| INTERNAL | 33.846.215 | 14.769 | 1.962.267 | 1.888.907 | 511,28 | (sem parcela) |

- **[C]** Os totais de nominal e de aquisição de cada administrador são iguais,
  ao centavo, aos da view por parcela (consulta 1). Contrato a contrato, na
  Genius F (39.876) e na BGT F (45.170), o nominal e a aquisição do contrato
  são a soma das parcelas em aberto em 100% dos contratos.
- **[C]** Na Genius F e na BGT F, nenhum caso se perde no contrato (1.468 e
  35.759 contratos, uma parcela-caso cada). Mas no Kanastro, na Genius e na
  QY, o VP dos contratos marcados é **menor** que o VP só das parcelas-caso:
  a maior parte delas está em contratos em que outras parcelas compensam
  (nominal acima da aquisição), e esses contratos não aparecem.
- **[C]** A INTERNAL entra (só ela tem os fundos sem administrador): 1,96 mi
  de contratos, R$ 511 mi de VP, quase todos em atraso. Ver P2 e D55, D56.
- Custo: 7 s a foto inteira por contrato. A comparação contrato × parcela
  levou 5 s na BGT F e **52 s** na Genius F, contra 8 s numa consulta
  parecida em 27/10: Redshift carregado no horário (29/10, manhã).

## Lacunas de Parcelas

Regra da D39 (controladoria, 27/10): parcela com pelo menos 2 meses de
atraso; se for a última do contrato, o contrato só está em atraso e não
entra. Nos testes, "2 meses" = vencimento original até 30/07/2026 (D40 em
aberto).

**Só pela sequência do estoque** (consulta 4: alguma parcela de número maior
falta no estoque entre a candidata e a última em estoque) **[C]**:

| Fundo | Contratos | Parcelas | 2+ meses de atraso | Desses, última no estoque | Candidatas | Contratos | VP | PDD | Tempo |
|---|---|---|---|---|---|---|---|---|---|
| BGT A | 111.188 | 1.135.959 | 68.653 | 3.577 | 1.342 | 803 | 0,683 | −0,677 | **57 s** |
| BGT E e K | 1.419 | 1.792 | 609 | 423 | 0 | 0 | — | — | 4 s |
| Genius F | 39.876 | 199.707 | 35.221 | 20.138 | 230 | 211 | 0,079 | −0,076 | 4 s |
| Dayvale A | 8.313 | 8.313 | 2.657 | 2.657 | 0 | 0 | — | — | 2 s |

- **[C]** BGT A tem 2.999 parcelas com `num_parcela` repetido no mesmo
  contrato; os demais, 0 ou 2.
- **[C]** Dayvale A: uma parcela por contrato; não há lacuna possível.
- **[C]** As candidatas têm PDD de ~100% do VP.

**Total de parcelas do contrato** (consulta 5) **[C]**: o `qt_parcelas_pagas`
da view por contrato é a primeira parcela em estoque − 1 (Genius F: 39.599 de
39.876 contratos; BGT E e K: 1.418 de 1.419). Nos 277 contratos da Genius F
com lacuna, ele não conta as parcelas da lacuna. Não dá, pelas views de
estoque, para saber se a última parcela em estoque é a última do contrato
(P21).

**A parcela que falta foi paga?** (consulta 6, Genius F, liquidação de jul a
set/26, contratos com parcela de 2+ meses de atraso) **[C]**:

| Tipo de movimento | Linhas | Contratos | Parcela paga dentro do intervalo do estoque | Depois da última em estoque (contratos) | Pago (R$ mil) |
|---|---|---|---|---|---|
| Liquidação normal | 392 | 170 | 192 | 200 (25) | 72,5 |
| Liquidação antecipada | 195 | 29 | 20 | 175 (12) | 9,8 |

- **[C]** As lacunas são pagamentos: 145 dos 170 contratos com liquidação
  normal de parcela posterior também têm a lacuna na foto.
- **[C]** Em 37 contratos (em 3 meses), a parcela paga é **posterior à
  última em estoque**: só a liquidação mostra. Pela foto, a parcela atrasada
  pareceria a última do contrato e sairia pela D39 (D41).

### Só pela view por contrato (29/10)

Pergunta do Heitor: dá para achar as lacunas só com a
`administradores_estoque_contrato`? Genius F, foto de 30/09/2026, contra a
foto por parcela do mesmo dia (consultas 10 a 12) **[C]**.

**O que os campos guardam** (39.876 contratos; tudo sai das parcelas em
aberto, nada lembra o que saiu do estoque):

| Campo | É | Contratos |
|---|---|---|
| `qt_parcelas_pagas` | primeira parcela em aberto − 1 (P21) | 100% |
| `qt_parcelas_vencidas` | parcelas vencidas em aberto (`flag_vencido`) | 100% |
| `num_parcela_vigente` | primeira parcela em aberto; nulo em 8.193 (os em dia) | 100% |
| `data_vcto_original` | vencimento da última parcela em aberto | 100% |
| `dias_atraso` | dias desde a vencida mais antiga em aberto | 21.371 exatos; 10.312 com 1 a 4 dias a menos |
| `prazo_contrato`, `prazo_original_contrato` | dias até a última em aberto; nenhum dá o total de parcelas | 67% |

- **[C]** O número da parcela acompanha o mês (parcelas mensais) em 39.340
  contratos (98,7%).

**Regra só com a view por contrato** (consulta 11): a vencida mais antiga
sai do `dias_atraso`, alinhada ao dia de vencimento do contrato
(`data_vcto_original`); com parcelas mensais, conta-se quantas deveriam estar
vencidas até a última em aberto ou até o dia. Se há menos vencidas em aberto,
uma parcela posterior já vencida saiu do estoque.

| Contratos com parcela de 60+ dias | Lacuna na foto por parcela | Regra acha | Escapam | Marca a mais |
|---|---|---|---|---|
| 27.097 | 214 | 191 (89%) | 23: parcelas fora do padrão mensal | 12: 11 mensais sem lacuna, 1 fora do padrão |

- **[C]** Sem o alinhamento, a regra acha 186 e não marca nenhum a mais.
- **[C]** A regra classifica as candidatas (60+ dias) igual à foto por parcela.
- **Não vê:** lacuna só entre parcelas a vencer (antecipação) e contrato com
  todas as posteriores já pagas (exemplo da D73). Também não dá o mês, o VP
  e a PDD de cada parcela não paga além da mais antiga: a view só tem o VP e
  a PDD do contrato e os vencidos por faixa de atraso.

**Contrato com todas as posteriores já pagas** (consulta 12; foto anterior
de 31/07, porque não há foto da Genius F em 30/06; liquidação de 01/08 a
30/09) **[C]**: dos 26.883 contratos com candidata e sem lacuna na foto, 653
não estavam na foto de 31/07; 17 tinham uma parcela de número maior em 31/07
que saiu até 30/09, e são exatamente os mesmos 17 com parcela posterior
liquidada no intervalo.

- **[H]** Pela view por contrato, o mesmo caso apareceria como o vencimento
  da última em aberto (`data_vcto_original`) recuando de uma foto para a
  outra. Não medido: a consulta foi abortada aos 60 s (Redshift carregado à
  tarde, 29/10).

## Performance de Pagamento

### Fórmula do `vl_pago` (time de dados, 29/10)

O time de dados disse ao Heitor que `vl_pago = vl_vencimento + vl_juros −
vl_ajuste`. Conferido na liquidação de 30/09/2026 (arquivo de um dia, todos
os administradores; consultas 13 e 14; R$ mil) **[C]**:

| Administrador | Momento do pagamento | Linhas | Fórmula fecha | `vl_pago` | `vl_vencimento` |
|---|---|---|---|---|---|
| BGT | antes | 26.488 | 80% | 7.254 | 6.421 |
| BGT | no dia | 1.912 | 3% | 3.970 | 4.094 |
| BGT | depois | 1.025 | 3% | 1.258 | 883 |
| Dayvale | antes e no dia | 9 | 0% | 25 | 23 |
| Dayvale | depois | 41 | 100% | 344 | 341 |
| Genius | antes | 9.230 | 1% | 2.413 | 3.526 |
| Genius | no dia | 431 | 100% | 125 | 126 |
| Genius | depois | 12.296 | 98% | 3.636 | 3.691 |
| Kanastro | antes | 2.112 | 0% | 458 | 660 |
| Kanastro | depois | 31.639 | 0,3% | 3.899 | 11.969 |
| Kanastro | sem vencimento | 4.861 | 5% | 689 | 1.759 |
| QY | antes | 63.654 | 0% | 2.817 | 3.525 |
| QY | depois | 49.756 | 66% | 2.335 | 3.389 |

- **[C]** `vl_juros` não vem em ninguém (nulo; zero na Dayvale). `vl_ajuste`
  só na Dayvale e na Genius. `vl_vencimento` vem em todos (534 nulos na BGT)
  e é igual ao `vl_nominal`.
- **[C]** Onde fecha: pagamento no dia ou depois na Genius (liquidação
  normal 100%) e na Dayvale; na QY, 86% da liquidação depois do vencimento;
  na BGT, 84% do `Payment` antecipado (pago = vencimento).
- **[C]** Antecipação: o desconto não está no `vl_ajuste`. Liquidação normal
  antecipada da Genius: pago 24% abaixo do vencimento, 30 de 6.037 linhas
  fecham; QY: 20% abaixo, 1 de 63.441; Kanastro: 31% abaixo, nenhuma.
- **[C]** Baixa parcial: o `vl_vencimento` é o da parcela inteira (Kanastro
  `partial_liquidation`: pago 1.950 × vencimento 9.233; QY
  `installment_partial_refund`: 119 × 867; Genius `LIQUIDACAO PARCIAL`).
- **[C]** Tipos que não são pagamento do sacado (glosa, renegociação,
  troca, resolução de cessão) também têm pago abaixo do vencimento.
- Consequência: a diferença `vl_pago − vl_vencimento` dá juros menos
  desconto por linha de pagamento integral, mesmo sem os campos de juros e
  ajuste; baixa parcial e tipos que não são pagamento precisam sair da
  conta (D5, P25).

### Consulta da carga conferida (29/10)

A consulta da execução diária (`valid_payment.py` da data-lake-api, branch
`feature/TS-5467-pdd-performance-pagamento`), compilada com o mapa de sinal da
Mov. Estoque e rodada no arquivo de liquidação de 30/09/2026, deu o mesmo
resultado, linha a linha, que uma consulta independente (faixas por
`data_pagamento - data_vcto` com `BETWEEN` e sinal por `DECODE`): 42
combinações de administrador e faixa, 1 s cada **[C]**. Totais (R$ mil):

| Administrador | Linhas | Valor de liquidação | Sem faixa |
|---|---|---|---|
| BGT | 29.425 | 12.481,7 | 0 |
| Dayvale | 50 | 368,9 | 0 |
| Genius | 21.957 | 6.174,5 | 0 |
| Kanastro | 38.612 | 5.046,0 | 4.861 linhas (688,6) |
| QY | 113.412 | 4.913,7 | 0 |

- **[C]** Batem com a soma do `vl_pago` da consulta 13 por administrador; na
  QY, 238,6 a menos = 2 × 119,3 do `installment_partial_refund`, que entra
  com sinal negativo (P4, D5).

### Escada por faixa

**Valor de baixa** (`vl_pago`; coluna "VP baixado", D46), liquidação de set/26 por faixa de dias entre pagamento e
vencimento (consulta 8, faixas do protótipo, `ESC_LAB`), sobre o `vl_pago` de
todos os tipos (ainda sem o mapa de sinal da D5) **[C]**:

| Administrador | Linhas | Sem `data_vcto` | >60 antes | 31–60 antes | 16–30 antes | 1–15 antes | No dia | 1–15 após | 16–30 após | 31–60 após | 61–90 após | >90 após | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BGT | 306.211 | 0 | 51,80 | 5,31 | 4,80 | 33,38 | 91,84 | 14,99 | 3,00 | 0,19 | 0,06 | 0,78 | 206,16 |
| Dayvale | 613 | 0 | 4,70 | 0,27 | 0,31 | 0,26 | 0,08 | 1,40 | 0,28 | 0,42 | 0,13 | 0,48 | 8,31 |
| Fydd | 35.005 | 0 | 0,11 | 0,02 | 0,04 | 0,40 | 0,04 | 0,70 | 0,20 | 1,15 | 0,95 | 4,51 | 8,11 |
| Genius | 1.759.327 | 0 | 31,13 | 11,39 | 13,22 | 50,71 | 24,00 | 122,91 | 13,52 | 9,99 | 3,61 | 9,06 | 289,57 |
| Kanastro | 592.723 | 102.047 | 9,24 | 3,22 | 1,08 | 4,46 | 1,18 | 38,05 | 11,90 | 7,36 | 1,82 | 25,90 | 115,50 |
| QY | 1.112.645 | 15.106 | 10,03 | 5,87 | 9,25 | 9,76 | 1,48 | 9,53 | — | — | — | — | 48,16 |

- **[C]** `id_parcela` preenchido em toda a liquidação, menos 15.106 linhas da
  QY. `vl_presente` só em Dayvale e Fydd (P3). `num_parcela` nulo em todo o
  Fydd, 83% da Genius e 38% da Dayvale.
- **[C]** QY: nada pago mais de 15 dias depois do vencimento (P13).
- **[C]** A liquidação da QY de set/26 mudou desde 22/10 (P23).

**Valor de baixa × VP em carteira das parcelas que saíram** num dia (consulta 7, Genius F, saídas entre as
fotos de 29/09 e 30/09 × liquidação de 30/09; R$ mil) **[C]**:

| Série | Linhas | >60 antes | 31–60 antes | 16–30 antes | 1–15 antes | No dia | 1–15 após | 16–30 após | 31–60 após | 61–90 após | >90 após | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VP em carteira das parcelas que saíram (todas, sem a D45) | 486 | 22,4 | 12,5 | 11,2 | 23,9 | 0,5 | 72,3 | 12,9 | 9,8 | 8,3 | 2,9 | 176,7 |
| Valor de baixa (`vl_pago`) | 502 | 21,0 | 11,4 | 12,0 | 24,1 | 0,5 | 73,9 | 13,1 | 9,0 | 1,9 | 31,6 | 198,6 |

- **[C]** As duas séries ficam próximas até 31–60 dias após. A diferença em
  ">90 após" (R$ 31,6 mil de valor de baixa × R$ 2,9 mil de VP que saiu)
  bate com baixa parcial de parcela vencida que continua no estoque (o
  `paid_on_remaining` da Mov. Estoque).
- Nomes revistos em 27/10 (D46): esta evidência foi escrita chamando o
  `vl_pago` de "VP liquidado" e o VP que saiu de "VP baixado"; as tabelas
  acima já usam os nomes novos.

**Taxa média ponderada** (consulta 9, parcelas a vencer, regra do protótipo:
BGT em %, fora de 0–500% a.a. descartada) **[C]**:

| Administrador | VP a vencer | Sem taxa | Taxa fora de 0–500% | Taxa média (a.a.) |
|---|---|---|---|---|
| BGT | 1.095,42 | 0 | 4,94 | 64,7% |
| Dayvale | 39,77 | 0 | 0 | 23,0% |
| Fydd | 17,53 | 0 | 1,62 | 112,7% |
| Genius | 750,07 | 0,02 | **263,33 (35%)** | 188,4% |
| Kanastro | 415,90 | **66,52** | **279,94 (67%)** | 483,8% |
| QY | 503,42 | 0 | 0 | 12,3% |

**[C]** Na Genius e no Kanastro, a taxa média sai de uma parte pequena do VP e
fica perto do teto do filtro (P7, P10): o número não é confiável (D44).

## Custo das consultas (27/10/2026)

| Consulta | Escopo | Tempo |
|---|---|---|
| Residual por administrador (1, 2) | foto inteira, agregada | 5–10 s |
| Residual BGT por fundo (3) | 1 administrador, 1 foto | 3 s |
| Lacunas pela sequência (4, com uma janela a mais) | fundo pequeno | 2–4 s |
| A mesma | **BGT A (1,1 mi de parcelas)** | **57 s** |
| Total de parcelas (5) | fundo pequeno | 6–8 s |
| Parcela posterior paga (6) | Genius F, 3 meses de liquidação | 6 s |
| A mesma ideia com janela e subconsulta correlacionada | Genius F, 12 meses | **abortada aos 60 s** |
| Escada de um dia (7) | Genius F | 11 s |
| Escada do liquidado (8) | todos, 1 mês | 4 s |
| Taxa média (9) | foto inteira, agregada | 7 s |
| Campos e regra da view por contrato (10, 11), 29/10 | Genius F, 1 foto | 2–6 s |
| Última em aberto recuando, view por contrato, 29/10 | Genius F, 2 fotos | **abortada aos 60 s** |
| Fórmula do `vl_pago` (13, 14), 29/10 | liquidação de 1 dia, todos | 1–2 s |

Lacunas na hora não cabem no limite de 50 s do BFF nem para um fundo do
tamanho da BGT A (D43).
