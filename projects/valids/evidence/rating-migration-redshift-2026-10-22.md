# Abertura de Rating e Análise de Migração: views do lake (22/10/2026)

Consultas rodadas em 22/10/2026 no Redshift do lake, só leitura, sempre
filtradas por `data_ref` no lado `administradores_*`. Valores em R$ mi, salvo
indicação. Fundos por letra (ordem do VP em 31/08/2026, calculada na própria
`administradores_estoque_contrato`) e administradores por análogo. Os dados
das views ainda não foram validados.

As consultas estão em `attachments/sql/` (como medir de novo: ver
[stock-movement-redshift-2026-10-21.md](stock-movement-redshift-2026-10-21.md#como-medir-de-novo)).

## `plgn.dim_contrato`

Catálogo (`information_schema`, `pg_views`, `svv_table_info`) **[C]**:

- View late-binding: `SELECT *` de uma tabela física do SQLMesh
  (`sqlmesh__plgn.plgn__dim_contrato__<hash>`). O hash muda a cada plano do
  SQLMesh; há quatro versões físicas no schema.
- 332 mi de linhas, ~28 GB, **sem sortkey** (`AUTO(SORTKEY)`), distribuição
  `AUTO(EVEN)`. Todo filtro nela lê a coluna inteira; a junção precisa partir
  de um lado pequeno (uma foto do estoque) e ser por igualdade.
- Não tem `data_ref`: é o estado atual do contrato (`data_atualizacao`).
- Colunas úteis aqui: `cnpj_classe`, `id_contrato_cessao`, `num_controle`,
  `identificador`, `produto_id`, `rating`, `score`. Não tem nome de produto.

## Chave entre o estoque e `dim_contrato`

[rating_product_key.sql](../attachments/sql/rating_product_key.sql), foto de
30/09/2026.

**Primeiro teste, 20 contratos por administrador, sem exigir o mesmo fundo
[C]:** os números colidem entre fundos (contratos da BGT, do Kanastro e da
Dayvale casaram com linhas de **outros** fundos). A junção precisa de
`cnpj_classe` dos dois lados.

**Amostra de até 2.000 contratos por fundo, exigindo o mesmo fundo [C]:**

| Fundo | Amostra | Por `num_controle` | Por `identificador` | Casou | % do VP casado |
|---|---|---|---|---|---|
| BGT A | 2.000 | 2.000 | 0 | 2.000 | 100% |
| BGT B, C, F | 2.000 cada | 0 | 0 | 0 | 0% |
| BGT D | 2.000 | 2.000 | 0 | 2.000 | 100% |
| BGT E | 1.417 | 1.417 | 0 | 1.417 | 100% |
| BGT G, J, K, L | 3, 3, 2, 2 | 0 | 0 | 0 | 0% |
| BGT H | 79 | 78 | 0 | 78 | 98,4% |
| BGT I | 2.000 | 2.000 | 0 | 2.000 | 100% |
| BGT M | 850 | 850 | 0 | 850 | 100% |
| Fydd A | 2.000 | 2.000 | 2.000 | 2.000 | 100% |
| Genius B | 2.000 | 2.000 | 2.000 | 2.000 | 100% |
| Genius C | 2.000 | 1.510 | 1.510 | 1.510 | 79,4% |
| Genius D | 2.000 | 2.000 | 2.000 | 2.000 | 100% |
| Genius E | 2.000 | 1.971 | 0 | 1.971 | 96,3% |
| Genius F | 2.000 | 1.549 | 2.000 | 2.000 | 100% |
| Genius G | 1.171 | 1.163 | 1.163 | 1.163 | 99,9% |
| Genius H | 2.000 | 2.000 | 2.000 | 2.000 | 100% |
| Genius I | 92 | 92 | 92 | 92 | 100% |
| QY A | 2.000 | 0 | 2.000 | 2.000 | 100% |

- **[C]** Em nenhum fundo um contrato casou com mais de uma linha de
  `dim_contrato`, nem com produtos diferentes pelas duas chaves.
- **[C]** Kanastro A, Dayvale A e BGT B, C, F, G, J, K, L não têm nenhuma linha
  em `dim_contrato` (contagem por `cnpj_classe`).
- **[C]** O `rating` de `dim_contrato` não é o `faixa_pdd`: igual em 0 de
  2.000 na maioria dos fundos (só Genius F, 1.098 de 2.000, por coincidência
  de letras). Os valores (A, B, C, F com `score`) são o rating da originação.

**Cobertura estimada em VP (30/09/2026)**, aplicando o % casado da amostra ao
estoque de cada fundo ([tabela de 30/09](stock-movement-redshift-2026-10-21.md#reconciliação-residual-de-set26)):

| Administrador | VP | Com produto | Sem produto |
|---|---|---|---|
| BGT | 1.273,07 | 688,47 (54%) | 583,87 (B, C, F, G, J, K, L) |
| Genius | 1.203,22 | 1.126,57 (94%) | 76,65 (C e E) |
| Kanastro | 1.680,38 | 0 | 1.680,38 |
| QY | 512,61 | 512,61 | 0 |
| Fydd | 155,51 | 155,51 | 0 |
| Dayvale | 53,54 | 0 | 53,54 |
| **Total** | **4.878,33** | **2.483,16 (51%)** | **2.394,82 (49%)** |

## Produtos por fundo

Mesma amostra, `produto_id` de `dim_contrato` **[C]**:

| Fundo | Produtos (% do VP da amostra) |
|---|---|
| BGT A | 1 (77,1%), 69 (17,2%), 36 (5,7%) |
| Genius C | 1145 (57,5%), 1143 (21,9%), sem produto (20,6%) |
| Genius E | 713 (93,9%), 449 (1,9%), 1043 (0,4%), sem produto (3,7%) |
| Demais fundos com produto | um produto cada |

O nome do produto não está nas views. A rota `controllership/valid/funds` do
BFF, que a tela já chama, devolve os produtos de cada fundo (`id`, `nome`) da
plataforma de cessão. **[H]** Esse `id` é o mesmo `produto_id` de
`dim_contrato`; validar com a resposta da rota para BGT A (esperado: 1, 36 e
69).

## Rating do administrador (`faixa_pdd`)

`administradores_estoque_contrato`, 30/09/2026, por administrador e
`faixa_pdd` **[C]**:

- Ratings vistos: BGT AA, A–H, `GLOSA`, `PJ` (e 1 contrato sem rating);
  Dayvale A, B, D–G; Fydd A, `CM`; Genius A–M, `WOP`; Kanastro A–D; QY AA, A.
- `vl_pdd` vem **negativo** em todos os administradores. Em % do VP (módulo),
  por exemplo BGT: AA 0,5%, B 7,6%, C 28,4%, H e `PJ` 100%.
- Fydd: PDD zero na faixa A (836.891 contratos, R$ 155,50 mi); só `CM` (14
  contratos) tem PDD (P12).
- QY: PDD zero em 30/09; R$ 32,6 mi em 20/10 (P13).

**Rating × atraso do contrato** (contratos por faixa de `dias_atraso`) **[C]**:
o rating acompanha o atraso, com exceções que alargam a faixa de dias
observada de cada rating (P17). Exemplos: BGT H tem 2.713 contratos em dia e
44.315 acima de 180 dias; Genius A tem 14.130 contratos acima de 180 dias;
Kanastro D vai de 15 a 3.408 dias.

**Fundo inteiro, Genius E** ([rating_by_product.sql](../attachments/sql/rating_by_product.sql),
~11 s) **[C]**: a soma do VP (125,17) é igual ao estoque do fundo em 30/09; a
junção não duplica. No produto 713, o PDD/VP é estável por rating (régua): A
1,2%, B 2,1%, C 6,2%, D 15,2%, E 33,1%, F 47,0%, G 66,0%, H 86,0%, I e `WOP`
100%. As faixas de dias também aparecem (B 1–15, C 16–30, F 91–120, G
121–149, `WOP` a partir de 362), mas com sobreposição (E de 9 a 90; I de 1 a
359).

## `dias_atraso`

`administradores_estoque_contrato`, 30/09/2026 **[C]**:

| Administrador | Em dia (nulo): contratos / VP | Em atraso: contratos / VP | Atraso mín.–máx. |
|---|---|---|---|
| BGT | 1.679.105 / 919,78 | 139.819 / 353,28 | 1–943 |
| Dayvale | 8.678 / 39,77 | 3.337 / 13,76 | 1–1.406 |
| Fydd | 63.522 / 17,53 | 773.383 / 137,97 | 1–3.338 |
| Genius | 234.656 / 406,17 | 425.113 / 797,05 | 1–3.445 |
| Kanastro | 170.064 / 207,00 | 695.491 / 1.473,38 | **15**–3.408 |
| QY | 2.728.941 / 487,52 | 155.608 / 25,09 | 1–**2** |

- **[C]** `dias_atraso` nulo ⟺ `qt_parcelas_vencidas` = 0 e `vl_vencidos_*`
  = 0, em todos os administradores. Nulo = em dia.
- **[C]** QY: máximo de 2 dias em 30/09 e de 22 em 20/10 (P13).
- **[C]** Kanastro: nenhum contrato com 1 a 14 dias (P14).

## Histórico disponível

Contagem por administrador em fechamentos **[C]**:

- Nada em 30/06/2025 nem em 31/12/2025. Há foto em 30/01/2026 e 27/02/2026
  para BGT (11 fundos), Dayvale, Fydd, Genius (5) e Kanastro. QY só a partir
  de set/26.
- O dia mais recente pode vir parcial: em 21/10/2026 a BGT tem 1 fundo
  (R$ 261,79 mi), contra 12 em 20/10 (P15).

## Estabilidade do contrato entre fechamentos

Amostra de 2.000 contratos de 31/08 por administrador, procurados em 30/09
pelo mesmo fundo e `id_contrato_admin` **[C]**:

| Administrador | Presentes em 30/09 | Atrasados que andaram 25–35 dias |
|---|---|---|
| BGT | 1.938 (96,9%) | 134 de 140 |
| Dayvale | 1.900 (95,0%) | 495 de 495 |
| Fydd | 1.927 (96,4%) | 1.770 de 1.770 |
| Kanastro | 1.935 (96,8%) | 1.399 de 1.579 |
| Genius (fundos presentes nas duas datas, 300 por fundo) | 2.103 de 2.192 (95,9%) | 1.216 de 1.395 |

Sem o filtro de fundos presentes, a Genius dá 13%: a amostra cai no Genius A,
que saiu do arquivo em set/26 (P6).

## Matriz de rolagem: prova de conceito

[migration_matrix.sql](../attachments/sql/migration_matrix.sql), Dayvale A,
31/08 → 30/09/2026, contratos (VP em 31/08; para "(novo)", VP em 30/09)
**[C]**:

| De \ Para | Em dia | 1–30 | 31–60 | 61–90 | 91–180 | 181+ | (saiu) |
|---|---|---|---|---|---|---|---|
| Em dia | 8.485 (33,19) | 205 (0,96) | | | | | 484 (7,31) |
| 1–30 | | | 128 (0,63) | | | | 33 (0,38) |
| 31–60 | | | | 127 (0,56) | | | 19 (0,18) |
| 61–90 | | | | | 130 (0,58) | | 9 (0,18) |
| 91–180 | | | | | 235 (1,00) | 111 (0,44) | 20 (0,12) |
| 181+ | | | | | | 2.391 (9,53) | 29 (0,20) |
| (novo) | 193 (6,01) | 2 | 1 | 1 | 3 | 3 | |

Na Dayvale nenhum contrato atrasado voltou a ficar em dia no mês: ou rolou de
faixa ou saiu.

## Pagamento em dia × após 30 dias

[monthly_payment.sql](../attachments/sql/monthly_payment.sql), liquidação de
set/26, sobre o `vl_pago` de todos os tipos (ainda sem o mapa de sinal da D5)
**[C]**:

| Administrador | Linhas | Sem `data_vcto` | Pago | % pago até o vencimento | % pago > 30 dias após |
|---|---|---|---|---|---|
| BGT | 306.211 | 0 | 206,16 | 90,8% | 0,5% |
| Dayvale | 613 | 0 | 8,31 | 67,4% | 12,4% |
| Fydd | 35.005 | 0 | 8,11 | 7,4% | 81,5% |
| Genius | 1.759.327 | 0 | 289,57 | 45,1% | 7,8% |
| Kanastro | 592.723 | 102.047 (17%) | 115,50 | 16,6% | 30,4% |
| QY | 840.842 | 9.468 | 36,24 | 69,8% | 0,0% |

**[C]** `data_pagamento` = `data_ref` em todas as linhas.

## Efeito vagão (26/10/2026)

[drag_effect.sql](../attachments/sql/drag_effect.sql), foto de 30/09/2026
**[C]**.

**Por sacado** (consulta 1, todos os contratos): sacados que, no mesmo fundo,
têm ao mesmo tempo contrato em dia e contrato atrasado, e quantos deles têm um
rating só em todos os contratos.

| Administrador | Sacados com 2+ contratos | Com um rating só | Em dia e atrasado ao mesmo tempo | Desses, com um rating só |
|---|---|---|---|---|
| BGT | 403.727 | 402.656 | 1.322 | 1.108 (84%) |
| Dayvale | 420 | 420 | 151 | 151 (100%) |
| Fydd | 34.392 | 34.387 | 6.333 | 6.332 (100%) |
| Genius | 11.640 | 11.229 | 1.200 | 1.049 (87%) |
| Kanastro | 10.676 | 10.676 | 5.974 | 5.974 (100%) |
| QY | 546.012 | 546.012 | 23.571 | 23.571 (100%) |

**Dentro do contrato** (consulta 2, view por parcela, 200 contratos atrasados
por administrador, um administrador por consulta):

| Administrador | Parcelas por contrato (média) | Com parcela vencida e a vencer | Mesmo rating em todas | Mesmo % de PDD em todas | Parcela a vencer com PDD |
|---|---|---|---|---|---|
| BGT | 10 | 113 | 111 | 113 | 112 |
| Genius | 8 | 116 | 116 | 115 | 105 |
| Kanastro | 6 | 66 | 66 | 66 | 66 |
| Dayvale | 1 | 0 | — | — | — |

A mesma consulta com os quatro administradores juntos foi abortada pelo
Redshift aos 60 s ("system requested abort").

**Conclusão [C]:** os administradores aplicam o rating do pior atraso ao
contrato inteiro (parcelas a vencer inclusive) e, quase sempre, a todos os
contratos do mesmo sacado. Explica boa parte do P17.

## Réguas de PDD na plataforma (26/10/2026)

Espelho das tabelas do platform-cessao no lake (consulta 3 e contagens; só
configuração) **[C]**:

- `regua_pdd` e `regua_pdd_faixa`: 0 linhas.
- `regra` com `tipo_regra` = `pdd`: 255 regras, 131 ativas, 98 produtos. O
  tipo vem gravado em minúsculas (`pdd`), não como o valor do enum (`PDD`).
- `regra_pdd_prazo_devedor`: 14,6 mi de linhas, todas criadas em 24/10/2023,
  2 fundos; atraso de −2.310 a +1.463 dias, por sacado e por cedente.
- Produto 713 (régua ativa): limites 0, −15, −30, −60, −90, −120, −150, −180,
  −360, −99999 e taxas 1%, 1,9%, 6%, 15%, 33%, 47%, 66%, 86%, 100%, 100%,
  iguais ao % de PDD por rating medido no Genius E (seção "Rating do
  administrador").

## Cadeia estoque → produto → régua (26/10/2026)

[product_scale_chain.sql](../attachments/sql/product_scale_chain.sql), Genius E,
foto de 30/09/2026 **[C]**:

- **Fundo:** o fundo 209 da plataforma tem o CNPJ do Genius E.
- **Produtos:** 449, 713 e 1043 ligados ao fundo 209 em `produto_fundo`, todos
  como fundo padrão.
- **Régua:** para (713, 209) há uma regra de PDD ativa (a da seção anterior)
  e uma inativa com outras taxas. São registros diferentes: a inativa foi
  criada em 21/07/2023 e desativada em 05/02/2026, quando a ativa foi criada
  (o mesmo em 449 e 1043). Não há campo de vigência; as datas dão uma
  aproximação de qual régua valia numa data passada.
- **`prazo_pdd` em toda a plataforma:** 125 regras ativas `devedor` e 6
  `contrato`. O par produto 72 + fundo 37 tem duas regras ativas iguais.
- **Contrato a contrato:** 20 contratos com rating C, 16 a 30 dias de atraso,
  uma parcela vencida e sacado com um contrato só: PDD de 6,00% do VP em
  todos, o % da faixa 16–30 da régua. Num deles (36 parcelas, 6 pagas, 1
  vencida há 19 dias, 29 a vencer até 2029), cada uma das 30 parcelas em
  aberto tem PDD de 6% do seu VP; sem o vagão, o contrato teria ~1,4%. O
  produto em `dim_contrato` (por `num_controle`) é o 713. A parcela vencida
  tem VP igual ao valor de face.
- **Arrasto por sacado:** 5 sacados com um contrato em dia (rating D ou E) e
  outro atrasado (40 a 72 dias): nos 5, o contrato em dia tem o mesmo % do
  atrasado (15% ou 33%). Pela D29 (vagão só no contrato), o contrato em dia
  ficaria com 1%.

## Como a régua muda (26/10/2026)

`captalys_trusted.platform_cessao_master_regra_history`, alterações das regras
de PDD gravadas pela ingestão do lake **[C]**:

- Começa em 15/08/2026 (carga inicial de todas as 255 regras como inserção);
  até 01/10/2026, 8 alterações.
- 5 alterações só desativaram regras (produtos 80, 81, 15 e 1901).
- 3 editaram o `kwargs` de uma regra ativa, na mesma linha: produto 1670 em
  01/09 e produto 1901 em 12/09 e 15/09. Na tabela da plataforma, essas
  versões anteriores não existem mais.
- Genius E: as regras antigas de 449, 713 e 1043 foram desativadas em
  05/02/2026 às 16h51, e as novas têm `data_atualizacao` às 16h50 do mesmo dia.
- No mesmo schema há `platform_cessao_master_regra_pdd_matriz` (fundo, produto,
  faixa, valor de aquisição, data de referência), com as colunas do modelo
  `RegraPddFaixa`. Não investigada.

## Custo das consultas (26/10/2026)

Tempos medidos nesta sessão (do envio ao fim, com a conexão) **[C]**:

| Consulta | Escopo | Tempo |
|---|---|---|
| Rating por produto e rating ([rating_by_product.sql](../attachments/sql/rating_by_product.sql)) | 1 fundo (Genius E), 1 dia, com `dim_contrato` | ~11 s |
| Busca em `dim_contrato` | 1 contrato, filtrado por fundo | ~15 s |
| Contratos por sacado ([drag_effect.sql](../attachments/sql/drag_effect.sql), consulta 1) | todos os fundos, 1 dia | ~12 s |
| Amostra de cobertura ([rating_product_key.sql](../attachments/sql/rating_product_key.sql)) | 2.000 contratos por fundo, com `dim_contrato` | ~21 s |
| Parcelas de 200 contratos ([drag_effect.sql](../attachments/sql/drag_effect.sql), consulta 2) | 1 administrador | 4–12 s |
| A mesma, com 4 administradores juntos | — | abortada aos 60 s |

- **[H]** Rating da carteira consolidada com produto: 20–40 s (a varredura de
  `dim_contrato` não depende de quantos fundos entram). Não medido: a medição
  com todos os fundos (Rating, faixas, matriz e pagamento) foi bloqueada pelo
  controle de permissões da sessão, por risco de carga no Redshift.
- O BFF espera a data-lake-api por 50 s por padrão
  (`apl-credit-whitelabel-api/src/services/data_lake_api/__init__.py:23`; a
  conciliação usa 300 s). A `/valid/stock` guarda o resultado no Redis por 24 h
  (`data-lake-api/src/modules/valid/repository.py:11`). O BFF já tem um
  pré-aquecimento diário às 5h30 para a conciliação CERC, com trava no Redis
  (`apl-credit-whitelabel-api/src/modules/controllership/cerc_reconciliation/prewarm.py`).

