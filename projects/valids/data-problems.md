# Problemas de dados

Inconsistências achadas nas views do lake. Os dados ainda não foram validados
(aviso do Heitor, 21/10/2026), então cada item é algo **a validar**, não uma
conclusão. Os problemas nas colunas de taxa (P7, P8, P10) são do time de
dados: o código não os contorna (D12). Desde a D15 (accrual por roll-forward)
eles não afetam mais o accrual. Os números saíram das consultas de
[evidence/stock-movement-redshift-2026-10-21.md](evidence/stock-movement-redshift-2026-10-21.md)
(P1 a P11), de
[evidence/rating-migration-redshift-2026-10-22.md](evidence/rating-migration-redshift-2026-10-22.md)
(P12 a P17) e de
[evidence/inconsistency-monitoring-redshift-2026-10-27.md](evidence/inconsistency-monitoring-redshift-2026-10-27.md)
(P19 a P23).

## P1 — O estoque atual não vem de uma view `administradores_*`

- **Onde:** `GET_STOCK_DATA` da data-lake-api lê `plgn.estoque_contrato`
  (`src/infra/redshift/queries/plgn/valid.py:22`), uma tabela física
  diferente de `plgn_physical.administradores_estoque_contrato`.
- **Efeito:** saldo inicial e estoque real (e a Visão Geral e o Histórico)
  saem de uma fonte fora da D1.
- **Visto:** **[C]** em 30/09/2026 as duas fontes têm os mesmos administradores
  e quase os mesmos totais (Genius R$ 1.203,22 mi nas duas; Kanastro R$ 1.682,33 mi
  × R$ 1.680,38 mi; INTERNAL R$ 11.737,56 mi × R$ 11.742,65 mi).
- **Correção decidida (D7, 23/10):** a `get_stock` passa a ler
  `plgn.administradores_estoque_contrato`. Ao implementar, comparar os dois
  lados nas datas que a tela usa.

## P2 — Fonte INTERNAL repete fundos dos administradores

- **Onde:** `administradores_estoque_contrato` tem a fonte `INTERNAL`
  (14 fundos, R$ 11,8 bi de VP em 30/09). Ela não existe em
  `administradores_estoque` (por parcela), nem em aquisição ou liquidação.
- **Efeito:** **[C]** 4 CNPJs aparecem na INTERNAL e também por um
  administrador (BGT D, Fydd A, Genius D, Genius E); os outros 10 fundos da
  INTERNAL e 21 de administrador não se repetem (30/09 e 22/10, consulta 6 de
  [internal_origin.sql](attachments/sql/internal_origin.sql)). O BFF soma todas as
  linhas na carteira consolidada (`business.py:54`), então conta esses fundos
  duas vezes; com o fundo escolhido, pega a primeira linha que casa o CNPJ
  (`business.py:152`), que pode ser a da INTERNAL. Fundo só na INTERNAL não
  tem como fechar Mov. Estoque.
- **Tamanho e divergência (23/10):** **[C]** em 30/09, a INTERNAL soma
  R$ 11,74 bi contra R$ 4,88 bi dos 6 administradores, ~70% do VP da
  carteira consolidada. Nos 4 fundos repetidos, os VPs divergem (R$ mi,
  administrador × INTERNAL): BGT D 144,77 × 162,72; Fydd A 155,51 × 174,74;
  Genius D 218,67 × 279,62; Genius E 125,17 × 125,12. **[H]** Pode ser um
  cálculo próprio da carteira, com outra metodologia.
- **Os 4 fundos repetidos em 22/10:** **[C]** o VP do administrador por
  contrato é igual ao por parcela, que é a base da Mov. Estoque. A INTERNAL
  fica acima: BGT D 171,65 × 153,42 (+11,9%); Fydd A 181,66 × 162,85
  (+11,6%); Genius D 292,20 × 229,44 (+27,4%); Genius E 128,36 × 128,33
  (igual). Pela fonte Dayvale, o Fydd A dá uma terceira versão, de 106,90
  (P5). A quantidade de contratos quase não muda, de −0,1% a +4,5% (este na
  BGT D). **[H]** A diferença é de avaliação, como taxa e método de desconto,
  e não de carteira. Para validar: casar os contratos por `id_contrato_admin`
  num dia e comparar o VP de cada um. Saldo final da Mov. Estoque × VP da
  INTERNAL: D47.
- **Contrato a contrato, 30/09 (27/10):** **[C]** pergunta testada: a
  INTERNAL seria o saldo calculado a partir dos dados do administrador? Não
  se confirma. Os contratos são os mesmos, mas os números não.
  - **Fydd A:** 99,99% dos contratos da INTERNAL casam pelo
    `id_contrato_admin`. Batem a data de cessão (95,7%) e o valor de
    aquisição (97,1%; total 108,81 nos dois). Não batem o VP (igual em 35%
    dos contratos; 174,72 × 155,23, +12,5%) nem o nominal em aberto (igual em
    37,5%; 174,80 × 161,14, +8,5%). Pelo nominal, a INTERNAL vê mais parcelas
    em aberto do que o administrador.
  - **Genius D:** 99,2% casam e a data de cessão bate (97,9%). O nominal quase
    bate (420,87 × 423,19), mas o VP não bate em nenhum contrato (279,18 ×
    218,62, +27,7%): a diferença está no desconto. A aquisição bate em 60,6%.
  - **BGT D e Genius E:** nenhum contrato casa pelo ID (outro formato ou outra
    numeração, não conferido). Na Genius E o VP total é igual.
  - **Nos dois fundos que casam:** a `taxa_aquisicao` não bate em nenhum
    contrato (talvez outra unidade, não conferido), e o PDD da INTERNAL é
    outro (Fydd A: −171,01 × −0,01; Genius D: −134,46 × −93,37).

  Com os dados do administrador, o roll-forward chega no VP dele (Fydd A em
  set/26: 155,51, D15), e não no da INTERNAL. Os 10 fundos só-INTERNAL
  (~R$ 11,0 bi, 94% do VP dela) nem têm dado de administrador no lake.
  **[H]** A INTERNAL usa o mesmo cadastro de contratos, com saldo em aberto,
  desconto e PDD próprios. Consulta 7 de
  [internal_origin.sql](attachments/sql/internal_origin.sql).
- **Efeito na Mov. Estoque consolidada:** ela só soma fundos de administrador,
  então o saldo do waterfall consolidado não bate com o VP da Visão Geral
  enquanto a INTERNAL estiver nela.
- **Quem são os fundos da INTERNAL (23/10):** **[C]** pela planilha de fundos do
  BFF (`apl-credit-whitelabel-api/static/relacao_fidcs.xlsx`), 12 dos 14 CNPJs
  estão lá. Quase todos têm a própria empresa como **gestora**, e os
  administradores são BGT, Genius, Fydd e um sétimo, **Fynvest**, que não
  manda arquivo para o lake (não existe fonte dele). Um dos CNPJs que também
  vem pela Genius (Genius E) aparece na planilha com a Fynvest como
  administradora. **[H]** A INTERNAL seria o estoque calculado dentro de casa,
  pela gestora, e não recebido de um administrador. Isso explicaria ela existir
  só no estoque por contrato, sem parcela, aquisição nem liquidação.
- **Por que não há parcela, aquisição nem liquidação (27/10):** **[C]** as
  quatro views `plgn.administradores_*` são só `SELECT *` de tabelas de
  `plgn_physical`, sem filtro: a falta vem da carga, não da view. As três sem
  INTERNAL têm `loaded_at` (hora da carga) e campos que só o arquivo do
  administrador traz (`fundo_nome`, `id_fundo_admin`, `id_cedente_admin`,
  `tipo_movimento`); a `administradores_estoque_contrato` não tem `loaded_at`,
  ou seja, é montada por um processo, não copiada de um arquivo. Em 30/09,
  cada administrador aparece com os mesmos fundos no estoque por contrato e
  no por parcela; a INTERNAL só no por contrato. Ela está também em
  `plgn_physical.estoque_contrato` (tabela fora das views do dashboard, por
  contrato, com IDs da plataforma de cessão), quase igual: 14 de 14 fundos,
  33,82 mi × 33,85 mi de contratos (−0,08%), R$ 11,738 bi × 11,743 bi
  (−0,04%), 7 fundos com a mesma quantidade. O `id_contrato_cessao` vem 100%
  preenchido na INTERNAL, mas também na QY e no Fydd (Genius 94,7%, BGT 9%,
  Kanastro e Dayvale 0%): é um vínculo feito para todas as fontes e não prova
  a origem. **[H]** A INTERNAL é gerada por um processo interno direto por
  contrato, para os fundos cujo administrador não manda arquivo; como as
  outras três tabelas são cópia dos arquivos dos administradores, não há o que
  carregar nelas. Consultas:
  [attachments/sql/internal_origin.sql](attachments/sql/internal_origin.sql).
- **Validar:** perguntar ao time de dados o que gera a INTERNAL (qual job e
  qual a entrada), se ele tem as parcelas e os eventos (cessão e pagamento) e
  poderia gravá-los nas outras três tabelas, qual número
  vale nos fundos repetidos e se os fundos da Fynvest vão ter arquivo de
  administrador (D8).
- **Tratamento provisório (D8, 23/10):** vale o administrador quando existe; a
  INTERNAL só cobre fundo sem administrador (opção b). Visão Geral e Histórico
  com todos os fundos; Mov. Estoque só para fundo de administrador e sem
  consolidado. A controladoria ainda vai dizer como quer apresentar.

## P3 — `vl_presente` da liquidação só em dois administradores

- **Onde:** `administradores_liquidacao.vl_presente`.
- **Efeito:** a baixa não pode ser medida a VP direto da view. Motivou a D3
  (baixa pelo `vl_pago`).
- **Visto:** **[C]** set/26 e 13–20/10: preenchido em Dayvale e Fydd; a BGT
  manda 0; Genius, Kanastro e QY mandam nulo. `vl_presente_atual` e
  `vl_saldo_nominal` seguem o mesmo padrão.

## P4 — Estornos com `vl_pago` positivo na QY

- **Onde:** `administradores_liquidacao`, fonte QY.
- **Efeito:** somar todos os tipos inflaria as baixas.
- **Visto:** **[C]** em 15 e 16/10/2026, `installment_payment_reversal` (46.784
  linhas) e `installment_partial_refund` (50.492) só têm `vl_pago` positivo;
  `gloss` só negativo; `installment_reactivation` só zero.
- **Validar:** mapa de sinal da D5 com a controladoria.

## P5 — Dayvale: aquisições faltando e um dia gigante

- **Onde:** `administradores_aquisicao`, fonte Dayvale.
- **Efeito:** a conferência de set/26 dá −11%: o estoque nominal quase não cai
  (R$ 66,3 mi → R$ 65,7 mi) com R$ 10,1 mi de nominal baixado, mas não há
  aquisição no mês.
- **Visto:** **[C]** nenhuma linha de aquisição em set/26; em 14/10/2026,
  879.974 linhas (R$ 114,2 mi), todas com `data_aquisicao` = 14/10, para um
  fundo de R$ 53 mi e ~12 mil contratos.
- **Revisão de 23/10:** **[C]** as 879.974 linhas de 14/10 são do **Fydd A**
  (mesmo final de CNPJ), rotuladas com a fonte Dayvale. Na view por parcela de
  14/10, o Fydd A aparece duas vezes, sob Fydd e sob Dayvale, com as mesmas
  879.974 parcelas e o mesmo `vl_aquisicao` (R$ 114,22 mi). Em 21/10 a fonte
  Dayvale volta a ter só o próprio fundo (11.745 parcelas). Efeitos:
  - no dia afetado, o consolidado conta o Fydd A duas vezes;
  - na Mov. Estoque diária, aparece um "fundo" Dayvale/Fydd que entra num dia
    e sai no seguinte.

  A falta de aquisições da Dayvale A em set/26 continua sem explicação.
- **Revisão de 26/10:** **[C]** na simulação da semana de 16 a 22/10, o Fydd A
  ainda aparece também sob a fonte Dayvale, em 15, 19, 20, 21 e 22/10, com o
  VP pulando de R$ 160,4 mi para quase zero, depois R$ 106,9 mi, de novo quase
  zero e R$ 106,9 mi. A rota fica com a fonte que tem mais dias (Fydd) e o
  Fydd A fecha sem diferença, mas a tabela da movimentação guarda também as
  linhas Dayvale do fundo.
- **Validar:** com o time de dados, por que a carga de 14/10 duplicou o Fydd A
  sob a fonte Dayvale, em que outros dias isso aconteceu, e como a aquisição da
  Dayvale A entra.

## P6 — Fundos que não fecham no mês

Reconciliação de set/26 por fundo (residual = estoque real − saldo inicial −
aquisições + baixas). Fundos sem aquisição no mês dão de 1,3% a 4,5%, o que é
coerente com accrual; os casos abaixo não. **[C]** nos números, **[H]** nas
causas:

| Caso | Visto | Causa provável |
|---|---|---|
| BGT A e BGT F | residual de −8,5% e +35,9%; somados, ~0,5% | transferência de carteira entre os dois fundos, sem aquisição e baixa casadas |
| Genius A | R$ 2,01 bi em 31/08 e fora do arquivo em 30/09 | fundo trocou de administrador ou saiu do lake |
| QY A | sem estoque em 31/08; R$ 543 mi de aquisição e R$ 513 mi de estoque em 30/09 | início da carga da QY; a carteira migrada veio como aquisição |
| BGT N | R$ 56,8 mi de aquisição em set/26 e nenhum estoque | fundo ainda sem estoque no lake |
| BGT I, BGT M | residual de +18,7% e +133% | fundos pequenos; aquisição registrada em outra data ou valor |
| Genius D, Genius F | conferência de +9,7% e −10,0% com o accrual mensal | a investigar com a conferência por parcela |

- **Validar:** para cada caso, a
  [conferência por parcela](attachments/sql/reconciliation_by_installment.sql) mostra se
  o desvio está em parcelas que entraram, saíram ou ficaram.

## P7 — Taxas inconsistentes

- **Onde:** `administradores_estoque_contrato.taxa_aquisicao` e, para alguns
  fundos BGT, `administradores_estoque`.
- **Efeito:** a taxa da view por contrato não serve para o accrual; os fundos
  BGT sem taxa ficam sem accrual.
- **Visto:** **[C]** em 31/08/2026:
  - **View por contrato:** a BGT varia de 0 a 22; Genius, Kanastro e Fydd
    chegam a 1e+298, com taxas negativas (−1).
  - **View por parcela:** BGT G, J, K e L têm parcelas a vencer sem taxa ou
    sem método (14, 14, 2 e 2 parcelas, respectivamente), e o accrual delas
    sai nulo.
- **Dono:** time de dados (D12). Até a correção, esses fundos ficam sem accrual
  e o efeito aparece na conferência.
- **Visto em 27/10:** **[C]** na view por parcela, 30/09/2026, parcelas a
  vencer: 35% do VP da Genius e 67% do Kanastro com `taxa_recebivel` fora de
  0–500% a.a., e mais 16% do Kanastro sem taxa. Afeta o KPI de taxa média da
  Performance de Pagamento (D44).
  ([evidência](evidence/inconsistency-monitoring-redshift-2026-10-27.md#performance-de-pagamento))

## P8 — BGT: VP não reproduz pela taxa informada

- **Onde:** `administradores_estoque`, fonte BGT.
- **Efeito:** o accrual da BGT é o menos confiável (+24% sobre a variação real
  em BGT B+H+L).
- **Visto:** **[C]** 4 parcelas a vencer de um mesmo contrato em 30/09: taxa
  informada de 75,32% a.a. (`exp365_aa`), mas a taxa implícita no VP cai de
  114% para 85% a.a. conforme o prazo aumenta. Um desconto exponencial por taxa
  única daria a mesma taxa implícita em todas.
- **Dono:** time de dados (D12), confirmando com a BGT como o VP é calculado
  (taxa, base, se é linear ou apropriado desde a aquisição).

## P9 — Genius: VP de parcela vencida sobe

- **Onde:** `administradores_estoque`, fonte Genius.
- **Efeito:** o taxa × prazo dá zero para vencidas, e a diferença vai para a
  conferência.
- **Visto:** **[C]** Genius C em set/26: as parcelas já vencidas em 31/08 que
  continuaram no estoque somaram +R$ 0,36 mi de VP. Em Fydd e Dayvale a
  variação foi exatamente zero. No Kanastro, −R$ 2,03 mi (pagamentos sobre
  vencidas).
- **Validar:** perguntar à Genius se apropria juros depois do vencimento.

## P10 — Taxas a confirmar

- **Kanastro:** **[C]** `taxa_cessao` ~6,3 com `expb252_aa`, ou seja ~630% a.a.
  (~17,7% a.m.). Reproduz o VP exatamente, mas é alto; confirmar que é a taxa
  certa e não um campo trocado.
- **Fydd, Dayvale, Genius:** **[C]** numa amostra de 4 parcelas por
  administrador, o VP sai da `taxa_recebivel`, não da `taxa_cessao` (nas
  parcelas da amostra do Fydd: ~0,50 × 0,68). **[H]** Se a carteira é avaliada
  a uma taxa menor que a da aquisição, o VP já nasce acima do valor pago; no
  Fydd A, o VP em 30/09 das parcelas novas de set/26 foi de R$ 10,20 mi contra
  R$ 8,60 mi de aquisição. Confirmar com a controladoria se esse é o critério.
- **Revisão de 22/10:** **[C]** no agregado das parcelas a vencer do Fydd A, a
  taxa de cessão dá accrual de R$ 1,073 mi e a do recebível R$ 1,088 mi (real
  R$ 1,092 mi). A de cessão não é sistematicamente maior, como a amostra
  sugeria, então a causa dos R$ 1,60 mi na entrada fica em aberto.
- **Dono:** time de dados (D12), com a controladoria para o critério.

## P11 — PDD com sinal ou tamanho estranho

- **Onde:** `plgn.estoque_contrato.vl_pdd` (a fonte atual da Visão Geral).
- **Efeito:** afeta a Visão Geral e o Histórico, não a Mov. Estoque.
- **Visto:** **[C]** em 30/09/2026, a BGT soma −R$ 292 mi de PDD (negativo) e
  o Kanastro R$ 1.416 mi de PDD sobre R$ 1.682 mi de VP (84%).
- **Visto em 22/10:** **[C]** em `administradores_estoque_contrato`, o
  `vl_pdd` vem negativo em todos os administradores (30/09/2026). O tamanho do
  Kanastro vem da faixa D: 594.836 contratos, R$ 1.335,75 mi de VP, 99,99%
  provisionados.
- **Validar:** com a controladoria, o sinal e a base do `vl_pdd` por
  administrador.

## P12 — Fydd sem PDD

- **Onde:** `administradores_estoque_contrato.vl_pdd`, fonte Fydd.
- **Efeito:** na Abertura de Rating, o Fydd A aparece com PDD zero.
- **Visto:** **[C]** em 30/09/2026, faixa A com 836.891 contratos, R$ 155,50 mi
  de VP e PDD zero; só a faixa `CM` (14 contratos) tem PDD. PDD zero também
  em 31/03, 30/06, 31/07 e 20/10/2026, com 92% dos contratos em atraso.
- **Validar:** perguntar ao time de dados se o Fydd manda PDD em outro campo
  ou arquivo.

## P13 — QY: atraso contado desde a migração

- **Onde:** `administradores_estoque_contrato.dias_atraso` e `vl_pdd`, fonte QY.
- **Efeito:** a QY aparece quase toda em dia e não rola de faixa na Análise
  de Migração; PDD irrisório na Abertura de Rating.
- **Visto:** **[C]** máximo de 2 dias de atraso em 30/09/2026 e de 22 em
  20/10 (cresce com os dias corridos desde o fim de set/26); ratings só AA e
  A; PDD zero em 30/09 e R$ 32,6 mi em 20/10 sobre R$ 883 mi. Na liquidação de
  set/26, 0% pago mais de 30 dias após o vencimento.
- **Validar:** perguntar se o atraso da QY é contado do vencimento original
  ou da data da migração (ver também P6, carteira migrada como aquisição).

## P14 — Kanastro: atraso começa em 15 dias e liquidação sem vencimento

- **Onde:** `administradores_estoque_contrato.dias_atraso` e
  `administradores_liquidacao.data_vcto`, fonte Kanastro.
- **Efeito:** a faixa 1–30 do Kanastro só tem 15–30 dias (quem tem 1–14 dias
  conta como em dia?); o % pago em dia perde as linhas sem vencimento.
- **Visto:** **[C]** em 30/09/2026, nenhum contrato com 1 a 14 dias (mínimo 15);
  rating A = todos em dia. Na liquidação de set/26, 102.047 de 592.723 linhas
  (17%) sem `data_vcto`.
- **Validar:** perguntar se o Kanastro só marca atraso a partir do 15º dia
  (carência) e por que parte da liquidação vem sem vencimento.

## P15 — Último dia pode vir parcial

- **Onde:** `administradores_estoque_contrato`, data mais recente.
- **Efeito:** a tela abre na data mais recente e pode mostrar uma carteira
  incompleta.
- **Visto:** **[C]** em 21/10/2026 (consultado em 22/10), a BGT tem 1 fundo e
  R$ 261,79 mi; em 20/10, 12 fundos e R$ 1.139,0 mi.
- **Validar:** saber do time de dados a que horas a carga do dia termina; até
  lá, o dia corrente da tela é provisório.

## P16 — `dim_contrato` não cobre metade do VP

- **Onde:** `plgn.dim_contrato`, junção com o estoque (D17).
- **Efeito:** ~49% do VP de 30/09/2026 fica sem produto no filtro (D18).
- **Visto:** **[C]** Kanastro A, Dayvale A e BGT B, C, F, G, J, K, L não têm
  nenhuma linha em `dim_contrato`; Genius C (~21% do VP) e Genius E (~4%)
  casam só em parte. Os números de contrato colidem entre fundos, então a
  junção sem `cnpj_classe` acharia produtos errados.
- **Validar:** perguntar se `dim_contrato` só tem os contratos da plataforma
  de cessão e se há previsão de incluir os demais.

## P17 — Rating do administrador não segue só o atraso do contrato

- **Onde:** `administradores_estoque_contrato.faixa_pdd` × `dias_atraso`.
- **Efeito:** a faixa de dias de cada rating, medida nos dados, sai larga e
  não serve de régua (D19).
- **Visto:** **[C]** em 30/09/2026: BGT H com 2.713 contratos em dia e 44.315
  acima de 180 dias; Genius A com 14.130 contratos acima de 180 dias;
  Kanastro D de 15 a 3.408 dias. No Genius E, produto 713, a régua aparece
  limpa em parte dos ratings (B 1–15, C 16–30, F 91–120) e sobreposta em
  outros (E 9–90, I 1–359).
- **Explicado em 26/10 [C]:** efeito vagão por sacado. Entre os sacados com
  contrato em dia e contrato atrasado no mesmo fundo, um rating só em 100%
  (Dayvale, Kanastro, QY, Fydd), 87% (Genius) e 84% (BGT)
  ([evidência](evidence/rating-migration-redshift-2026-10-22.md#efeito-vagão-26102026)).
  O que sobra na BGT e na Genius ainda não tem explicação.

## P18 — Foto do dia anterior incompleta na BGT

- **Onde:** `administradores_estoque`, fonte BGT, foto de 22/10/2026 lida em
  23/10.
- **Efeito:** **[C]** só 1 fundo da BGT na foto (7,6 mi de parcelas), contra
  12 fundos e 10,6 mi de parcelas em 21/10. As demais fontes estavam
  completas. Uma movimentação com 22/10 como ponta mostraria os fundos da BGT
  saindo inteiros do estoque. A consolidação diária confere só se a foto
  existe (`LIMIT 1`), então gravaria o dia pela metade até o reprocesso.
- **Visto:** contagem por fonte nas fotos de 21 e 22/10, em 23/10. É o mesmo
  padrão do [P15](#p15--último-dia-pode-vir-parcial), visto um dia antes (foto
  de 21/10 lida em 22/10, também com 1 fundo da BGT): a carga de D-1 da BGT
  costuma estar incompleta no dia seguinte.
- **Validar / corrigir:** perguntar ao time de dados até que horas a carga da
  BGT termina. Proposta: consolidar só até D-2 dias úteis, como a
  consolidação de estoque da data-lake-api (`target_lag_business_days`).

## P19 — BGT: aquisição acima do valor de face

- **Onde:** `administradores_estoque.vl_aquisicao_parcela` ×
  `vl_nominal_parcela`, fonte BGT.
- **Efeito:** a Análise Residual (tarefa 04) fica dominada pela BGT: 269.188
  parcelas **a vencer** com nominal < aquisição (R$ 101,45 mi de VP), quase
  todas na faixa de 50% a 100%.
- **Visto:** **[C]** em 30/09/2026, BGT F com 35.759 de 46.102 parcelas nesse
  caso (R$ 84,35 mi de VP) e aquisição 1,8× o nominal do fundo inteiro (nos
  outros fundos da BGT, de 0,2× a 0,8×). BGT B, H e L (mesmo final de CNPJ):
  224.956 parcelas, nominal médio de 89% da aquisição. A BGT também tem
  502.423 parcelas com aquisição zero.
  ([evidência](evidence/inconsistency-monitoring-redshift-2026-10-27.md#análise-residual))
- **[H]** BGT F recebeu carteira da BGT A em set/26 (P6) e a parcela
  transferida entrou com o valor da transferência.
- **Validar:** com o time de dados, como a BGT preenche a aquisição da
  parcela em carteira transferida e por que há parcelas com aquisição zero.

## P20 — `num_parcela` nulo em três administradores

- **Onde:** `administradores_estoque.num_parcela` e
  `administradores_liquidacao.num_parcela`.
- **Efeito:** as Lacunas de Parcelas (tarefa 04) precisam da sequência das
  parcelas: o Fydd fica fora, e parte da Genius e da Dayvale também.
- **Visto:** **[C]** estoque de 30/09/2026: Fydd 100% nulo, Genius 29%,
  Dayvale 31%; BGT, Kanastro e QY preenchidos. Liquidação de set/26: Fydd
  100%, Genius 83%, Dayvale 38%. Na Dayvale A, cada contrato tem uma parcela
  só.
- **Validar:** se o Fydd e a Genius mandam o número da parcela em outro campo
  (por exemplo, dentro do `id_parcela`).

## P21 — `qt_parcelas_pagas` não conta as parcelas pagas

- **Onde:** `administradores_estoque_contrato.qt_parcelas_pagas`.
- **Efeito:** as views não dão o total de parcelas do contrato; pela foto,
  não dá para saber se a última parcela em estoque é a última do contrato
  (D39, D41).
- **Visto:** **[C]** em 30/09/2026, o campo é sempre a primeira parcela em
  estoque − 1 (Genius F: 39.599 de 39.876 contratos; BGT E e K: 1.418 de
  1.419). Nos 277 contratos da Genius F com lacuna, as parcelas da lacuna não
  entram na conta, embora a liquidação mostre parcelas posteriores pagas.
- **Visto (29/10):** **[C]** os outros campos de parcela da view por contrato
  também saem das parcelas em aberto (Genius F, 30/09): `qt_parcelas_vencidas`
  são as vencidas em aberto, `num_parcela_vigente` a primeira em aberto,
  `data_vcto_original` o vencimento da última em aberto e
  `prazo_original_contrato` os dias até ela. O `dias_atraso` vem 1 a 4 dias
  abaixo do vencimento da vencida mais antiga em 10.312 de 31.683 contratos
  em atraso.
- **Validar:** com o time de dados, como o campo é calculado e se há a
  quantidade total de parcelas em algum arquivo do administrador.

## P22 — Kanastro: parcelas com nominal zero ou negativo no estoque

- **Onde:** `administradores_estoque.vl_nominal_parcela`, fonte Kanastro.
- **Efeito:** na Análise Residual, uma faixa "nominal ≤ 0" à parte.
- **Visto:** **[C]** em 30/09/2026, 23.060 parcelas vencidas com nominal ≤ 0.
- **Validar:** se são parcelas já quitadas que deveriam ter saído do estoque.

## P23 — Liquidação da QY de set/26 mudou depois de carregada

- **Onde:** `administradores_liquidacao`, fonte QY, set/26.
- **Efeito:** um mês já consolidado pode mudar depois. A consolidação (D34)
  precisa reprocessar o dia quando o `loaded_at` mudar, e o mesmo vale para a
  escada da tarefa 04.
- **Visto:** **[C]** em 22/10/2026, 840.842 linhas e R$ 36,24 mi pagos; em
  27/10/2026, 1.112.645 linhas e R$ 48,16 mi (linhas sem `data_vcto`: 9.468 →
  15.106).
- **Validar:** com o time de dados, se foi recarga retroativa da QY e se é
  esperado.

## P24 — BGT: `num_parcela` repetido no mesmo contrato

- **Onde:** `administradores_estoque.num_parcela`, fonte BGT.
- **Efeito:** nas Lacunas (tarefa 04), a falta na sequência sai da
  comparação entre quantas parcelas há depois da candidata e a distância até
  a última em estoque; um número repetido conta duas vezes e pode esconder
  uma lacuna. Contar os números distintos acerta a conta, mas não diz qual
  das linhas vale. Se for linha duplicada, a Análise Residual também conta a
  parcela duas vezes.
- **Visto:** **[C]** foto de 30/09/2026: BGT A com 2.999 parcelas com
  `num_parcela` repetido no mesmo contrato; os outros fundos testados, 0 ou
  2 ([evidência](evidence/inconsistency-monitoring-redshift-2026-10-27.md#lacunas-de-parcelas)).
- **Validar:** com o time de dados, se são parcelas diferentes com o mesmo
  número (renegociação, por exemplo) ou a mesma parcela duplicada.

## P25 — Liquidação: juros e ajuste não fecham o `vl_pago`

- **Onde:** `administradores_liquidacao`: `vl_pago`, `vl_vencimento`,
  `vl_juros`, `vl_ajuste`.
- **Efeito:** a fórmula do time de dados (`vl_pago = vl_vencimento +
  vl_juros − vl_ajuste`) não serve para abrir juros e desconto na
  Performance de Pagamento (tarefa 04). Só a diferença `vl_pago −
  vl_vencimento` é usável, e só em pagamento integral.
- **Visto:** **[C]** arquivo de 30/09/2026: `vl_juros` nulo em todos (zero na
  Dayvale); `vl_ajuste` só na Dayvale e na Genius; na antecipação, o desconto
  não está no `vl_ajuste` (Genius, QY e Kanastro pagam 20% a 31% abaixo do
  vencimento sem ajuste); na baixa parcial, o `vl_vencimento` é o da parcela
  inteira; no Kanastro, a fórmula quase nunca fecha
  ([evidência](evidence/inconsistency-monitoring-redshift-2026-10-27.md#fórmula-do-vl_pago-time-de-dados-2910)).
- **Validar:** com o time de dados, se juros e ajuste vêm de outro campo nos
  administradores que não os preenchem, e quais tipos de movimento são baixa
  parcial em cada administrador (a BGT não tem tipo parcial explícito).
