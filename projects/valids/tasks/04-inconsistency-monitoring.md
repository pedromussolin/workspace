# 04 — Monitoramento de Inconsistências

- **Status:**
  - 27/10/2026: viabilidade conferida no lake. **Dá para construir as três
    visualizações** só com as views `administradores_*` (sem `dim_contrato`,
    que só entra para o filtro de produto). Ressalvas: a taxa média
    ponderada não é confiável; Lacunas sem o Fydd e sem casos na
    Dayvale, e pesada demais para rodar na hora (D43); a última parcela do
    contrato precisa da liquidação (D41). D39 tomada (regra da Lacuna, com a
    controladoria).
  - 27/10/2026: D44 tomada: a taxa média ponderada sai por enquanto. Custo
    da comparação das duas fotos conferido: a consolidação da Mov. Estoque já
    a faz (ver "Performance de Pagamento").
  - 27/10/2026: D46 tomada: o `vl_pago` da liquidação é o **valor de baixa**
    (coluna "VP baixado" da escada), como as "Baixas" da Mov. Estoque. A
    leitura inicial estava invertida.
  - 29/10/2026: **Análise Residual implementada e commitada nas três pontas,
    sem push**, branch `feature/TS-5466-pdd-analise-residual` (ver
    [Implementação da Análise Residual](#implementação-da-análise-residual-2910)).
    D59 a D66 tomadas. Performance de Pagamento e Lacunas não iniciadas. Pendentes:
    D40 a D43 e D45 (o que entra na linha "VP liquidado").
  - 29/10/2026: Performance de Pagamento **em espera**: o Heitor está
    validando com o time de dados como puxar os valores de liquidação e de
    baixa (D45, D67). Iteração passa para as Lacunas: D71 e D72 abertas, P24
    registrado, perguntas ao time de dados listadas em
    [Lacunas de Parcelas](#lacunas-de-parcelas).
  - 29/10/2026: Lacunas: D40 (60 dias), D42 (sem a visão de glosa), D71
    (modelo da Residual) e D73 (contrato conta só na competência da parcela
    não paga) tomadas. Faltam D41, D72, D74 e a TS.
  - 29/10/2026: **Performance de Pagamento implementada e commitada nas três
    pontas, sem push**, branch `feature/TS-5467-pdd-performance-pagamento` (criada da
    `feature/TS-5442-pdd-integracao`, pedido do Heitor), só com o valor de
    liquidação (D67, D75). Ver
    [Implementação da Performance de Pagamento](#implementação-da-performance-de-pagamento-2910).
    D76 aberta (indicadores da aba). Nada da Lacuna de Parcelas no código
    (pedido do Heitor).
- **Repos:** data-lake-api (consulta e consolidação), BFF (rotas), front (a
  aba ainda não existe: `pdd/pdd.view.ts:20-26`).
- **Evidência:** [inconsistency-monitoring-redshift-2026-10-27.md](../evidence/inconsistency-monitoring-redshift-2026-10-27.md).

## Item original

Pedido do Heitor, 27/10/2026: construir as três visualizações da aba
"Monitoramento de Inconsistências" do protótipo, "Performance de Pagamento",
"Lacuna de Parcelas" e "Análise Residual", e verificar antes se dá para
construí-las com o que o banco tem hoje, só com as views `administradores_*`
e `dim_contrato`.

## O que a tela precisa

Protótipo `dashboard_fundos.html` **[C]**. A aba é um menu com três itens
(`monSub`, `:500`), cada um com a sua view:

- **Performance de Pagamento** (`viewVenc`, `:294`; `renderVenc`, `:931`):
  - KPIs: VP, quantidade de contratos, taxa média ponderada (`metricasFor`,
    `:367`) e PDD com o %.
  - "Escada de vencimentário" (`escadaChart`, `:952`): para os pagamentos do
    período, 10 faixas de dias entre o pagamento e o vencimento (>60 antes,
    31–60, 16–30, 1–15 antes, no dia, 1–15, 16–30, 31–60, 61–90, >90 após),
    com o **VP baixado** em coluna e o **VP liquidado** em linha. Por fundo ou
    consolidado, mês a mês, com o filtro de período do Histórico. O que cada
    série é: D46 e D45.
- **Lacunas de Parcelas** (`viewBuracos`, `:332`; `renderBuracos`, `:1217`):
  - KPIs: fundos com lacuna, contratos com lacuna, VP e PDD em aberto.
  - Por fundo: barras de contratos por competência (mês de vencimento), com
    o pico em destaque ("indício de repasse"), e tabela por competência
    (parcelas, contratos, VP, PDD, % provisionado; `burTableV1`, `:1266`).
  - Alternância "Qualquer lacuna" × "Glosa (antes da 1ª lacuna)"
    (`burTableV2`, `:1274`, com % do universo de glosa e VP e PDD do contrato
    inteiro).
  - Exportação dos casos por contrato e parcela (`exportLacunas`, `:1294`).
- **Análise Residual** (`viewNominal`, `:341`; `renderNominal`, `:1310`):
  - KPIs: fundos afetados, parcelas com nominal < aquisição, VP envolvido,
    nominal ÷ aquisição médio.
  - Por fundo: barras de parcelas por faixa de 10% de nominal ÷ aquisição
    (`nomChart`, `:1335`) e tabela com parcelas, VP, nominal e aquisição.
  - Exportação dos casos (`exportNominal`, `:1300`).

## O que o lake tem

| Elemento | Situação | De onde |
|---|---|---|
| Valor de baixa por faixa (coluna "VP baixado", D46) | **[C]** todos os administradores | `data_pagamento − data_vcto` e `vl_pago` da liquidação. Kanastro com 17% sem `data_vcto` (P14) |
| VP em carteira das parcelas baixadas por faixa (linha "VP liquidado", D45) | **[C]** todos | VP na foto anterior das parcelas que saíram do estoque, pela distância do dia ao `data_vcto_original`: a conta do `pv_exited` da Mov. Estoque (D15), aberta por faixa |
| KPIs VP, contratos, PDD | **[C]** já na `/valid/stock` | Visão Geral |
| Taxa média ponderada | **[C]** não confiável; fora por enquanto (D44) | Genius com 35% e Kanastro com 83% do VP a vencer sem taxa ou fora de 0–500% a.a. (P7, P10) |
| Sequência de parcelas | **[C]** BGT, Kanastro, QY; Genius em parte; Fydd não | `num_parcela` nulo: Fydd 100%, Genius 29%, Dayvale 31% (P20). Dayvale: uma parcela por contrato |
| Atraso da parcela | **[C]** | `data_vcto_original` × data da foto |
| Parcela posterior paga | **[C]** | lacuna na sequência da foto **ou** `num_parcela` maior na liquidação (D41) |
| Total de parcelas do contrato | **[C]** não existe nas views | `qt_parcelas_pagas` não é contagem de pagas (P21) |
| Nominal e aquisição da parcela | **[C]** todos | `vl_nominal_parcela`, `vl_aquisicao_parcela`; BGT com 502 mil parcelas com aquisição zero |

### Ressalvas por administrador

- **Fydd:** sem `num_parcela` no estoque e na liquidação; fica fora das
  Lacunas.
- **Dayvale:** uma parcela por contrato; nada a mostrar nas Lacunas; nenhum
  caso na Residual.
- **QY:** atraso contado desde a migração (P13): nada pago mais de 15 dias
  depois do vencimento, e quase nenhuma parcela com 2+ meses de atraso.
- **Kanastro:** 17% da liquidação sem vencimento fica fora da escada (P14);
  23 mil parcelas com nominal ≤ 0 no estoque (P22).
- **BGT F:** aquisição 1,8× o nominal do fundo (P19); vai dominar a Residual.

## Prontidão (29/10/2026)

| Visualização | Pronta para implementar? | O que falta decidir |
|---|---|---|
| **Análise Residual** | **em implementação (TS-5466)** | nada: D59 a D65 tomadas (29/10) |
| Performance de Pagamento | **commitada (TS-5467, 29/10), sem push**, só com o valor de liquidação | D76 (indicadores). Valor de baixa adiado (D45, [later.md](../later.md)) |
| Lacunas de Parcelas | não | D41 (de onde vem a lacuna: foto, view por contrato, liquidação ou maior parcela já vista), D72 (administradores); TS. D40, D42, D71, D73 e D74 tomadas (29/10) |

## Proposta

### Performance de Pagamento

- **Nomes (D46):** na conciliação da controladoria, o `vl_pago` que o
  administrador informa na `administradores_liquidacao` é o **valor de
  baixa**: o valor pelo qual a parcela saiu da carteira. É o mesmo número das
  "Baixas" da Mov. Estoque (D3), e a liquidação é o arquivo de baixas do
  administrador (liquidação pelo sacado, antecipação, estorno, glosa...).
- **Coluna "VP baixado" = valor de baixa:** soma do `vl_pago` (com o mapa de
  sinal da D5) por faixa de `data_pagamento − data_vcto`, por fundo e dia.
  Linha sem `data_vcto` fica fora da escada, com a contagem informada. Não
  precisa das fotos: é um agrupamento da liquidação do fundo (todos os
  fundos, um mês: ~4 s).
- **Linha "VP liquidado" [H], a confirmar com o Heitor:** o VP, na foto
  anterior, das parcelas que saíram do estoque **e** tiveram baixa no
  intervalo (D45), por faixa de `dia − data_vcto_original`: o valor a que a
  carteira carregava as parcelas baixadas. Na Dayvale e no Fydd, o
  `vl_presente` da liquidação daria o mesmo dado direto (P3).
- **Como ler:** em cada faixa, coluna − linha = resultado na baixa (valor de
  baixa − VP em carteira): deságio na antecipação, juros e multa no atraso. É
  a parte "baixas − VP das saídas" da conferência da Mov. Estoque. Baixa
  parcial (a parcela continua no estoque) entra só na coluna.
- **Pista do protótipo [C]:** sem dados, a escada diz "Sem dados de
  liquidação no período" (`:950`): as duas séries vinham do arquivo de
  liquidação do administrador. Nos dados de exemplo vistos (2 fundos, 1 mês),
  a coluna fica acima da linha em todas as faixas, o que combina com valor de
  baixa ≥ VP em carteira.
- **Fórmula do time de dados (29/10):** `vl_pago = vl_vencimento + vl_juros
  − vl_ajuste`. Abre uma leitura nova da linha (D45 c): o `vl_vencimento`,
  valor devido no vencimento, das mesmas linhas da coluna. Coluna − linha =
  juros − desconto: abaixo da linha na antecipação, acima no atraso. Sai da
  liquidação sozinha, sem comparar fotos. Nos dados de 30/09, juros e ajuste
  quase não vêm preenchidos (P25): usar a diferença, não os campos; tirar da
  linha a baixa parcial (o vencimento é o da parcela inteira) e os tipos que
  não são pagamento.
- **KPIs:** VP, contratos e PDD da `/valid/stock`. Sem a taxa média por
  enquanto (D44).
- **Custo da linha:** saber quais parcelas saíram exige comparar a foto do
  dia com a anterior, parcela a parcela. Na hora, na tela, seria pesado (um
  mês do Kanastro A levou 33,7 s em 23/10). Mas a consolidação da Mov. Estoque
  já faz essa comparação para cada dia e fundo, e não por junção: um
  agrupamento por foto e parcela com marcadores de presença
  (`data-lake-api`, branch `feature/TS-5441-pdd-mov-estoque`, commit `9a6a158`,
  `src/infra/redshift/queries/plgn/valid.py:83-195`; o `pv_exited` em `:162`),
  que já liga cada parcela ao pagamento dela (`pago_foto`). A escada só
  acrescenta o `data_vcto_original` na leitura do estoque e divide o
  `pv_exited` das parcelas com baixa em 10 somas por faixa. **[H]** Custo
  extra pequeno (uma coluna de data a mais); medir num fundo com e sem a
  escada. O teste de 27/10 usou `LEFT JOIN ... IS NULL` só por ser mais
  simples para uma consulta avulsa.
- **Testado num dia da Genius F (30/09):** valor de baixa R$ 198,6 mil × VP em
  carteira das parcelas que saíram R$ 176,7 mil, próximos em quase todas as
  faixas; em ">90 após", R$ 31,6 mil × R$ 2,9 mil, baixa parcial de parcela
  que continua no estoque. O teste contou toda saída, ainda sem a D45.

### Lacunas de Parcelas

- **Candidata (D39):** parcela em estoque com 60 dias corridos de atraso ou
  mais, do vencimento original até a data da foto (D40).
- **Entra** se alguma parcela **posterior** do mesmo contrato já foi paga:
  falta na sequência do estoque ou aparece liquidada (D41). Se não há
  parcela posterior paga e a atrasada é a última, o contrato só está em
  atraso e não entra.
- **Competência (D73):** mês do vencimento da parcela não paga. O contrato
  conta +1 só nessa barra; os meses das parcelas posteriores pagas não
  contam. Mais de uma parcela não paga em meses diferentes: +1 no mês de
  cada uma (D74).
- **Só a view por contrato (teste de 29/10, D41 d):** acha 89% dos contratos
  com lacuna na Genius F, mas não dá o mês, o VP e a PDD de cada parcela não
  paga além da mais antiga. Ver a
  [evidência](../evidence/inconsistency-monitoring-redshift-2026-10-27.md#só-pela-view-por-contrato-2910).
- **Medidas:** parcelas, contratos distintos, VP e PDD das candidatas; % =
  PDD ÷ VP.
- "Glosa (antes da 1ª lacuna)": fora por enquanto (D42, em
  [later.md](../later.md)).
- **Modelo da tela (D71, tomada):** como a Residual: só a organização
  interna, uma foto por data (o protótipo também: `buracosData`, `:492`),
  fundo opcional (Carteira Consolidada), execução diária própria, sem
  exportação na primeira versão.
- **Administradores (D72, proposta):** todo fundo com número de parcela, com
  aviso por fundo. Cobertura vista em 30/09 **[C]**: BGT, Kanastro e QY com
  número; Genius com 29% das parcelas sem número; Fydd sem número; Dayvale
  com uma parcela por contrato. QY com quase nenhuma parcela com 2+ meses de
  atraso (P13).
- **Eixo de competências:** pela D39, só competências até a data de
  referência menos 2 meses têm caso. O protótipo vai até o mês da data
  (dados fictícios, `DADOS.buracos`, `:353`, com PDD de 24% a 48% do VP;
  no lake, as candidatas têm PDD de ~100%).
- **Exemplo de cada decisão** (fictício, foto de 30/09, contratos de 10
  parcelas):
  - Contrato X: em estoque 4, 6, 7, 8, 9 e 10; a 4 venceu em 15/07 (77
    dias); a 5 falta. A 4 entra, competência jul/26. Pela foto basta.
  - Contrato Y: em estoque só a 4 (venceu em 15/07); 5 a 10 antecipadas em
    agosto. Pela foto, a 4 parece a última do contrato e não entra; com a
    liquidação, entra (D41). Na Genius F foram 37 contratos assim em 3 meses.
  - Parcela vencida em 31/07: 61 dias em 30/09. Pela D40 (b) entra; pela (a)
    ("até 30/07"), não. A diferença é só na borda.
  - Exemplo do Heitor (D73): parcelas 1 a 4 e 6 a 10 pagas, a 5 não. Conta
    +1 só no mês da 5. Na foto só sobra a 5, que parece a última do
    contrato: só entra com a liquidação (D41 b).

#### Perguntas ao time de dados (29/10)

1. Desde quando a `administradores_liquidacao` tem dado de cada
   administrador? Define até onde a D41 (b) enxerga parcela posterior paga.
2. Quais `tipo_movimento` são pagamento da parcela e quais são outra baixa
   (estorno, glosa, recompra)? Vale para a D41 e para a escada (D45, D5).
3. O Fydd, a Genius e a Dayvale mandam o número da parcela em outro campo
   (P20)?
4. Existe a quantidade total de parcelas do contrato em algum arquivo do
   administrador (P21)? Resolveria a "última do contrato" sem a liquidação.
5. As 2.999 parcelas com número repetido no mesmo contrato da BGT A são
   parcelas diferentes ou linha duplicada (P24)?

### Análise Residual

- Parcela em estoque com `vl_nominal_parcela < vl_aquisicao_parcela` e
  aquisição maior que zero, por faixa de 10% de nominal ÷ aquisição (nominal
  ≤ 0 numa faixa à parte). Medidas: parcelas, VP, nominal e aquisição.
- **Por parcela (D62, 29/10):** a base por contrato foi descartada porque
  perde as parcelas compensadas dentro do contrato. Situação da parcela pelo
  `flag_vencido` (D61); sem a faixa "nominal ≤ 0" (D59). A INTERNAL fica de
  fora (sem estoque por parcela). Contrato da rota proposto: D63.
- Leve (uma foto agregada em ~5 s), mas por parcela. Pela D43, entra na
  execução diária da Rating (D58), numa tabela nova por fundo, fonte, dia e
  faixa (parcelas, VP, nominal, aquisição). Faixas: D59. Exportação dos casos:
  D60.

### Onde calcular (D43)

Recomendação: em segundo plano, com o resultado no Postgres, como a D22 e a
D34. As Lacunas levaram 57 s num fundo só (BGT A), acima do limite de 50 s do
BFF. A escada entra na consolidação da Mov. Estoque, que já lê as duas fotos
de cada dia.

## Implementação da Análise Residual (29/10)

Branch `feature/TS-5466-pdd-analise-residual` nos três repositórios, criada
da `feature/TS-5442-pdd-integracao` local, sem upstream. Commits de 29/10,
**sem push**, cada um compilando e passando nos seus testes sozinho
(conferido num `git worktree` por commit):

| Repositório | Commits |
|---|---|
| data-lake-api | `cb5e224` configuração · `24727d5` modelos e migration 0012 · `2df0810` carga diária · `adfbd0e` rotas |
| BFF | `0dfee8d` escopo · `18ecd07` rotas, só da organização interna |
| front | `e0022246` data-access · `27db4c22` aba · `c9178174` dados fictícios do mock |

O hook do pre-commit da data-lake-api e do BFF foi instalado no devcontainer
(`/usr/local/bin/python3.12`) e não roda fora dele: os commits saíram com
`--no-verify`, depois de `black`, `ruff`, sintaxe, fim de arquivo, espaços e
`test_arch` rodados à mão.

- **data-lake-api:** execução diária própria (D64), no modelo da Rating:
  config `CFG_VALID_RESIDUAL_*` (desligada por padrão, sem horário), tabelas
  `valid_residual_run`, `_day`, `_fund_day` e `_band` (migration `0012`,
  **não aplicada**), consulta em `src/infra/redshift/queries/plgn/valid_residual.py`
  (uma leitura da view por parcela por bloco, já agregada; fundo sob duas
  fontes fica com a de mais parcelas), tasks `dispatch`, `consolidate` e
  `reprocess_valid_residual`, rotas `/valid/residual` e `/valid/residual/dates`.
  Carteira = os fundos do último dia com foto até a data.
- **BFF:** escopo `pdd-residual-analysis` (catálogo, página e rotas comuns de
  fundos e estoque), rotas `controllership/valid/residual` e `/dates`, totais
  (parcelas, VP, nominal, aquisição e a razão) por fundo e do escopo. Só a
  organização interna: o parceiro recebe 403 antes de qualquer chamada ao
  data lake (D66).
- **Front:** aba "Análise residual" com escopo (sai das pendentes), KPIs da
  D65, gráfico das parcelas por faixa (a vencer × vencidas), uma tabela por
  fundo com caso, calendário limitado aos dias da Residual, dados fictícios
  no mock.

**Verificado [C]:**
- data-lake-api: 88 testes passaram (novos e vizinhos, com dublês); o de
  repositório foi pulado (Postgres do devcontainer inacessível de fora); só
  falha o `test_arch` do `day_cache`, como na master. `ruff` e `black` limpos.
- Consulta no Redshift: 30/09/2026 bate com a evidência de 27/10 (BGT 269.188
  a vencer, R$ 101,45 mi; Kanastro 67.727, sem as 23.060 de nominal ≤ 0;
  aquisição zero 502.423), **41 s por dia** às 11h. Por isso 2 dias por
  consulta.
- BFF: 247 testes passaram (depois da D66) (pasta `valid`, mapa de permissões, arquitetura e
  escopo de parceiro), num venv próprio em `~/venvs/apl-credit-whitelabel-api`.
  Falham 2 testes da `/pdd/dates` (500 em vez de 502 quando o data lake cai),
  que **já falham na branch de integração** sem a Residual.
- Front: `tsc` dos specs, `eslint` dos arquivos mexidos e o build de teste
  passaram; `check-patterns` só acusa o protótipo local. **Os specs do Karma
  não rodaram:** o Chromium do Playwright precisa da `libnspr4` do sistema.

**Para ter dado na tela:** aplicar a migration `0012`, configurar
`CFG_VALID_RESIDUAL_RUN_AT` e `CFG_VALID_RESIDUAL_SCHEDULE_ENABLED=true`,
liberar o escopo `pdd-residual-analysis` nos perfis. O deploy da data-lake-api
roda migration sozinho (`RUN_MIGRATIONS=1` no `entrypoint.sh`).

## Implementação da Performance de Pagamento (29/10)

Branch `feature/TS-5467-pdd-performance-pagamento` nos três repositórios,
criada da `feature/TS-5442-pdd-integracao` local, sem upstream. Só o valor de
liquidação (`vl_pago`, D75) por faixa de dias entre o pagamento e o
vencimento; sem a série do valor de baixa (D67). Commits de 29/10, **sem
push**, cada um conferido sozinho num `git worktree` (checagens do pre-commit,
imports e testes):

| Repositório | Commits |
|---|---|
| data-lake-api | `055e097` configuração · `3dbb3cb` modelos, schemas e migration 0013 · `aeebb20` carga diária · `db7fc20` rotas |
| BFF | `cb022aa` escopo · `6119821` rotas, só da organização interna |
| front | `29d8728b` data-access · `ab311bd3` aba · `cc5527f9` dados fictícios do mock |

O hook do pre-commit da data-lake-api e do BFF só roda no devcontainer: os
commits saíram com `--no-verify`, depois das mesmas checagens à mão (fim de
arquivo, espaços, sintaxe, `black`, `ruff`). O front não tem hook.

- **data-lake-api:** execução diária própria, no modelo da Residual (D64):
  config `CFG_VALID_PAYMENT_*` (desligada por padrão, sem horário; um mês por
  consulta, porque só lê a liquidação), tabelas `valid_payment_run`, `_day` e
  `_band` (migration `0013`, **não aplicada**), consulta em
  `src/infra/redshift/queries/plgn/valid_payment.py` (uma linha por dia do
  arquivo, fundo, fonte e faixa; o sinal por tipo de movimento é o da Mov.
  Estoque, D5; sem data de vencimento ou de pagamento, faixa nula), tasks
  `dispatch`, `consolidate` e `reprocess_valid_payment`, rotas
  `/valid/payment` (período e fundo opcional) e `/valid/payment/dates`. Todas
  as fontes ficam gravadas; na leitura, fundo sob dois administradores fica
  com a fonte de mais dias no período, como a Mov. Estoque.
- **Migration:** a `0013` aponta para a `0011`, porque a base não tem a `0012`
  da Residual (TS-5466). Ao juntar as duas branches, apontar a `0013` para a
  `0012` (o teste `test_migration_is_the_only_head...` falha até isso).
- **BFF:** escopo `pdd-payment-performance` (catálogo, página e rotas comuns de
  fundos e estoque), rotas `controllership/valid/payment` e `/dates`, totais
  antes (faixas 0 a 3), no dia (4) e depois (5 a 9), por fundo e do escopo, e
  as faixas somadas da carteira. Só a organização interna (D70): parceiro
  recebe 403 antes de qualquer chamada. Período invertido: 422.
- **Front:** aba "Performance de pagamento" com escopo (sai das pendentes),
  filtro de período como o da Mov. Estoque (D68: padrão o último mês até a
  referência, limitado aos dias consolidados), KPIs (D76), escada (uma barra
  por faixa), tabela das faixas com o % do valor, nota das linhas sem
  vencimento, tabela por fundo e aviso da INTERNAL na Carteira Consolidada
  (D69), dados fictícios no mock.

**Verificado [C]:**
- data-lake-api: 44 testes novos passaram (modelo × migration sem banco,
  restrições na tabela, consulta compilada, regras, runner, agendamento
  desligado, rotas); o de repositório foi pulado (sem Postgres). Vizinhos:
  165 passaram; só falha o `test_arch` do `day_cache`, como antes.
- **Dados:** a consulta da carga, rodada no lake (só leitura, arquivo de
  30/09/2026, 1 s), deu o mesmo resultado, linha a linha, que uma consulta
  independente (42 combinações de administrador e faixa), e os totais por
  administrador batem com a conferência da fórmula (consulta 13); na QY, a
  diferença é o estorno parcial com sinal negativo.
- BFF: 233 testes da pasta `valid` e do mapa de permissões e 881 de
  arquitetura, escopo de parceiro e controle de acesso passaram; falham os 2
  da `/pdd/dates` que já falhavam na integração.
- Front: Karma rodou pela primeira vez neste ambiente (bibliotecas do
  Chromium extraídas em `~/.local/opt/chromium-libs`, sem `sudo`): suíte
  inteira com 5.042 specs ok; falham 4 specs de permissões das abas que **já
  falham na branch de integração** (esperam Rating e Migração sem escopo).
  Build de produção ok. Aba conferida no modo mock (Chromium headless): sem
  erro de console e sem rolagem lateral em 390 px.

**Para ter dado na tela:** aplicar a migration `0013`, configurar
`CFG_VALID_PAYMENT_RUN_AT` e `CFG_VALID_PAYMENT_SCHEDULE_ENABLED=true`,
liberar o escopo `pdd-payment-performance` nos perfis.

## Validação

- Escada: a soma das faixas da coluna (valor de baixa) = baixas da Mov.
  Estoque no mesmo período e fundo; a soma da linha ≤ `pv_exited`.
- Lacunas: amostra de contratos com a parcela posterior encontrada na
  liquidação (tipo e data).
- Residual: a soma por faixa = total da consulta 1 da evidência.

## Pendências

- D41, D43 (escada), D45, D67 e D72 em [decisions.md](../decisions.md);
  D40, D42, D44, D46, D71, D73 e D74 tomadas.
- P19 a P24 em [data-problems.md](../data-problems.md).
- D8 (INTERNAL): a INTERNAL não tem estoque por parcela nem liquidação; as
  três visualizações só têm fundo de administrador, como a Mov. Estoque.

## Histórico

- **27/10/2026:** protótipo mapeado. Viabilidade conferida no lake (foto de
  30/09/2026 e liquidação de set/26). Heitor trouxe a regra da Lacuna,
  combinada com a controladoria (D39). D40 a D44 abertas; P19 a P23
  registrados.
- **27/10/2026 (2):** explicada ao Heitor a leitura da Performance de
  Pagamento (baixado = queda do estoque a VP, liquidado = valor pago; a
  confirmar). D44 tomada: taxa média fora por enquanto. Heitor perguntou se a
  comparação das duas fotos é pesada: na tela sim, na consolidação ela já
  existe.
- **27/10/2026 (3):** Heitor corrigiu os nomes: o `vl_pago` é o valor de
  baixa, não o de liquidação (D46). A escada foi relida no contexto da
  conciliação da controladoria: coluna = valor de baixa; linha = VP em
  carteira das parcelas baixadas (a confirmar); a diferença é o resultado na
  baixa.
- **29/10/2026:** prontidão das três avaliada: a Análise Residual é a mais
  pronta. D59 e D60 abertas; D43 detalhada (cada visualização na carga que
  já lê o que precisa).
- **29/10/2026 (2):** levantado o que falta para a Residual. D61 aberta: os
  casos são de dois tipos (a vencer na BGT, vencidas nos demais), com causas
  diferentes. Parcelas com aquisição zero (BGT, 502 mil) ficam de fora da
  regra sem aparecer: mostrar a contagem.
- **29/10/2026 (3):** D61 (os dois tipos, separados por situação) e D59
  (sem a faixa "nominal ≤ 0") tomadas. Heitor perguntou se dá para usar a
  `administradores_estoque_contrato`: dá, com perda dos casos compensados
  dentro do contrato. D62 aberta.
- **29/10/2026 (4):** D62 tomada: por parcela. D63 (contrato da rota)
  proposta.
- **29/10/2026 (5):** D60, D63, D64 e D65 tomadas (Heitor). TS-5466; Heitor
  pediu para começar a implementar a Análise Residual.
- **29/10/2026 (6):** Análise Residual implementada nas três pontas, sem
  commit, seguindo as convenções pedidas pelo Heitor no meio do trabalho
  (sem `__all__`, Pydantic onde der, sem comentário desnecessário nem tag de
  decisão no código, SQL em `src/infra/redshift/queries`). D66 aberta.
- **29/10/2026 (7):** D66 tomada (Heitor): parceiro não vê a Análise
  Residual. BFF ajustado: 403 para sessão de parceiro nas duas rotas, sem a
  consulta fundo a fundo que existia para o parceiro.
- **29/10/2026 (8):** commits nas três pontas, sem push (Heitor pediu).
- **29/10/2026 (9):** levantado o que falta para a Performance de Pagamento:
  D67 a D70 abertas; D43 detalhada para a escada. D68, D69 e D70 tomadas
  no mesmo dia (Heitor); explicação da D45 e da D67 pedida.
- **29/10/2026 (10):** D45 e D67 em espera (Heitor validando com o time de
  dados como puxar os valores de liquidação e de baixa). Heitor passou para
  as Lacunas: levantado o que falta. D71 (modelo da Residual) e D72
  (administradores) abertas; P24 (número de parcela repetido na BGT A)
  registrado; D41 detalhada (a liquidação depende do histórico e dos tipos de
  movimento); pista para a D42 (rating `GLOSA` da BGT, [H]); perguntas ao time
  de dados listadas.
- **29/10/2026 (11):** D40 (b), D42 (b) e D71 (a) tomadas (Heitor). Heitor
  definiu a contagem por competência com um exemplo (D73). O exemplo é o caso
  que a foto sozinha não mostra (D41). D74 aberta: contrato com mais de uma
  parcela não paga em meses diferentes.
- **29/10/2026 (12):** D74 (a) tomada. Heitor propôs achar a lacuna pela
  variação diária de `qt_parcelas_pagas` e `qt_parcelas_vencidas` e depois
  descartou; pediu para verificar se dá só com a view por contrato. Testado
  na Genius F (30/09): os campos de parcela dessa view saem todos das
  parcelas em aberto (P21); uma regra de vencidas esperadas acha 191 dos 214
  contratos com lacuna. A "maior parcela já vista" numa foto anterior achou
  os mesmos 17 contratos que a liquidação. A consulta do histórico pela view
  por contrato foi abortada aos 60 s (Redshift carregado); consultas paradas.
- **29/10/2026 (13):** Heitor trouxe do time de dados a fórmula do `vl_pago`
  (`vl_vencimento + vl_juros − vl_ajuste`). Conferida num dia de liquidação
  (Redshift de volta ao normal, 1–2 s): fecha só onde o administrador
  preenche os campos; juros nunca vem; o desconto da antecipação não está no
  ajuste (P25). D45 ganhou a opção (c): a linha é o `vl_vencimento`.
- **29/10/2026 (14):** Heitor perguntou se o `vl_pago` é valor de baixa ou de
  liquidação. Pela fórmula, é o valor de liquidação (o que o sacado pagou);
  D75 aberta (revisão da D46), com o valor de baixa como `vl_vencimento` ou
  VP em carteira.
- **29/10/2026 (15):** D75 (b) e D67 tomadas (Heitor): o `vl_pago` é o valor
  de liquidação, e a Performance de Pagamento sai só com ele, sem o valor de
  baixa (adiado). Implementação no modelo da Residual: execução diária
  própria e leve, só a liquidação. Falta o número da TS para criar a branch.
- **29/10/2026 (16):** TS-5467. Heitor pediu a base na
  `feature/TS-5442-pdd-integracao` (branches refeitas antes de qualquer
  código), só a Performance de Pagamento (nada da Lacuna) e testes caprichados
  para os dados e os modelos. Implementada nas três pontas, sem commit;
  consulta da carga conferida no lake; front servido em `localhost:4200`
  (modo mock) para o Heitor ver. D76 aberta.
- **29/10/2026 (17):** commits nas três pontas, sem push (Heitor pediu).
