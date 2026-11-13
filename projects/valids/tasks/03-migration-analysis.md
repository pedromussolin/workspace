+++
card = "TS-5739"
type = "feature"
epic = "TS-5690"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
relates = ["TS-5442"]
+++
# 03 — Análise de Migração

- **Status:**
  - 22/10/2026: viabilidade conferida no lake. **Dá para construir** os dois
    blocos do protótipo (VP por faixa de atraso mês a mês e o comportamento
    de pagamento) e também a matriz de rolagem entre faixas, só com
    `administradores_estoque_contrato`, `administradores_liquidacao` e
    `dim_contrato` (produto). Ressalvas: histórico só a partir de 2026; atraso
    da QY e do Kanastro com problema (P13, P14); produto com a mesma cobertura
    da tarefa 02.
  - 25/10/2026: D18 tomada (sem grupo "Sem produto" no filtro). D20, D21 e
    D22 em explicação ao Heitor.
  - 26/10/2026: D17 e D20 tomadas (matriz na visualização "Estudo de
    Migração"); D22 provisória (Postgres). D33 aberta (faixas e escopo da
    matriz).
  - 27/10/2026: matriz de migração adiada para a próxima versão (D20 revista);
    D33 vai junto para [later.md](../later.md).
  - 27/10/2026: D49 aberta (contrato da rota).
  - 28/10/2026: faixas mensais integradas na branch
    `feature/TS-5442-pdd-integracao`. Integração local de `valid/pdd/dates`
    concluída no BFF e no front para limitar o calendário ao intervalo
    consolidado. Pagamento continua pendente da D21; matriz na próxima versão.
- **Repos:** data-lake-api (consulta e consolidação), BFF (rotas), front
  (tabela por faixa e limites do calendário).
- **Evidência:** [rating-migration-redshift-2026-10-22.md](../evidence/rating-migration-redshift-2026-10-22.md).

## Item original

Ver [tarefa 02](02-rating-breakdown.md#item-original) (pedido de 22/10/2026,
o mesmo para as duas abas).

## O que a tela precisa

Protótipo `dashboard_fundos.html` **[C]**. No protótipo, a aba "Análise de
migração" (`tabsDisponiveis`, `:507`) abre a view `viewFaixas`:

- **Segregação por faixa de atraso, evolução mensal** (`renderFaixas`,
  `:971`): tabela com o VP (R$ mi) de cada faixa (em dia, 1–30, 31–60, 61–90,
  91–120, 121–150, 151–180, 181+) por fechamento mensal.
- **Comportamento de pagamento** (`pgtoChart`, `:998`): linhas mensais de
  "% pago em dia" e "% pago > 30 dias após o vencimento".
- **Filtro de período**, como no Histórico.

À parte, o protótipo tem a aba "Estudo de Migração" (`renderMig`, `:680`):
um link para uma planilha de roll rate por fundo, feita fora do sistema. O
front atual chama a aba de "Análise de migração entre faixas"
(`pdd/pdd.view.ts:31-36`), que é a rolagem. Ver D20.

## O que o lake tem

| Elemento | Situação | De onde |
|---|---|---|
| Faixa de atraso do contrato | **[C]** disponível | `dias_atraso`; nulo = sem parcela vencida |
| VP por faixa e fechamento | **[C]** disponível | uma foto de `administradores_estoque_contrato` por fechamento |
| Rolagem entre faixas | **[C]** disponível | mesmo contrato (`cnpj_classe` + `id_contrato_admin`) em dois fechamentos; ~96% seguem no mês seguinte |
| % pago em dia / > 30 dias | **[C]** disponível, sobre o pago | `data_vcto` × `data_pagamento` de `administradores_liquidacao` |
| Produto | **[C]** parcial | igual à [tarefa 02](02-rating-breakdown.md#produto) |
| Histórico | **[C]** desde jan/26 | nada em 30/06/2025 nem em 31/12/2025 |

### Ressalvas por administrador

- **QY:** o `dias_atraso` parece contado a partir da migração da carteira
  (máximo de 2 dias em 30/09 e de 22 em 20/10). Até corrigir, a QY aparece
  quase toda em dia e não rola de faixa (P13).
- **Kanastro:** nenhum contrato com 1 a 14 dias; a faixa 1–30 dele só tem
  15–30. 17% da liquidação de set/26 sem `data_vcto` (P14).
- **Fydd:** 81,5% do pago em set/26 foi pago mais de 30 dias após o
  vencimento; 92% dos contratos estão em atraso. Coerente com a carteira
  (muita parcela vencida, ver tarefa 01), mas vale confirmar.

## Retrato por faixa × matriz de rolagem (D20)

São duas perguntas diferentes sobre o mesmo dado.

- **Retrato por faixa** (o que a aba do protótipo mostra): quanto da
  carteira está em cada faixa de atraso no fim de cada mês. Responde "o
  atraso está crescendo?".
- **Matriz de rolagem** (o "Estudo de Migração" do protótipo, hoje uma
  planilha): para onde foram os contratos de cada faixa de um mês para o
  outro. Responde "de quem atrasou, quantos pagaram e quantos pioraram?". O
  protótipo descreve a planilha como "análise de migração entre faixas de
  atraso e validação da régua de PDD por roll rate" (`dashboard_fundos.html:688`).

Analogia: o retrato é a contagem de alunos por série no fim de cada ano; a
matriz mostra quantos passaram de ano, repetiram ou saíram da escola.

Exemplo, Dayvale A, contratos **[C]** (mesma consulta da
[prova de conceito](../evidence/rating-migration-redshift-2026-10-22.md#matriz-de-rolagem-prova-de-conceito);
a tela mostraria VP):

| Faixa | Retrato em 31/08 | Retrato em 30/09 | O que a matriz mostra |
|---|---|---|---|
| Em dia | 9.174 | 8.678 | 205 passaram a atrasar; 484 saíram; 193 novos |
| 1–30 | 161 | 207 | nenhum dos 161 ficou: 128 pioraram, 33 saíram; os 207 vieram quase todos de "em dia" |
| 31–60 | 146 | 129 | 127 pioraram, 19 saíram |
| 61–90 | 139 | 128 | 130 pioraram, 9 saíram |
| 91–180 | 366 | 368 | parece parada, mas 111 pioraram, 20 saíram e 130 chegaram de 61–90 |
| 181+ | 2.420 | 2.505 | 2.391 ficaram, 29 saíram, 111 chegaram |

Só o retrato sugere que a faixa 91–180 não mudou; a matriz mostra que um
terço dela rolou para 181+ no mês. É essa taxa de rolagem (roll rate) que diz
se o % de PDD da régua está coerente com a perda.

## Pergunta à controladoria (D21)

O Heitor vai levar à controladoria (26/10). Texto:

> **Gráfico "Comportamento de pagamento" do dashboard de PDD**
>
> A aba "Análise de migração" do protótipo tem um gráfico mensal com duas
> linhas: "% pago em dia" e "% pago após 30 dias do vencimento". Para
> implementar, precisamos saber sobre qual base os percentuais são
> calculados. Vemos duas leituras:
>
> **A — sobre o que foi recebido no mês.** Tudo o que entrou de pagamento
> no mês, separado pela data do pagamento em relação ao vencimento da
> parcela. Exemplo: em setembro o fundo recebeu R$ 100; R$ 80 eram de
> parcelas pagas até o vencimento e R$ 5 de parcelas pagas mais de 30 dias
> depois (vencidas em junho, por exemplo). Resultado: 80% em dia, 5% após 30
> dias. Mostra de onde veio o caixa do mês, inclusive a recuperação de
> atrasos antigos.
>
> **B — sobre o que venceu no mês.** As parcelas que venceram no mês e como
> cada uma foi paga. Exemplo: em setembro venceram R$ 100; R$ 70 foram pagos
> até o vencimento, R$ 10 entre 1 e 30 dias depois, R$ 5 mais de 30 dias
> depois e R$ 15 seguem em aberto. Resultado: 70% em dia, 5% após 30 dias.
> Mostra a pontualidade de cada mês de vencimento. O "após 30 dias" de um
> mês só fecha 30 dias depois, então os meses recentes ainda mudam.
>
> Perguntas:
>
> 1. Qual leitura o gráfico deve mostrar: A, B ou outra?
> 2. O percentual é sobre o valor em R$ ou sobre a quantidade de parcelas?
> 3. Qual valor usar: o valor pago, o valor de face da parcela ou o valor
>    presente?
> 4. Algum tipo de movimento fica de fora, como estornos, recompras ou
>    renegociações?
> 5. Pagamento antecipado (antes do vencimento) conta como "pago em dia", ou
>    "em dia" é só o pago no dia do vencimento?
>
> Se as duas leituras servirem, a A é mais simples de construir com os dados
> que temos hoje.

## Relação com a "Performance de Pagamento" (tarefa 04)

Conferido no protótipo em 27/10/2026 **[C]**: os dois gráficos tratam do mesmo
assunto (quando a parcela é paga em relação ao vencimento) e vêm do mesmo
bloco de dados (`DADOS.venc`: `escada` e `pgto`), mas respondem perguntas
diferentes.

| | Comportamento de pagamento (esta aba) | Performance de Pagamento ([tarefa 04](04-inconsistency-monitoring.md)) |
|---|---|---|
| Forma | duas linhas, mês a mês (`pgtoChart`, `:998`) | 10 faixas de dias antes e depois do vencimento, somadas no período (`aggEscada`, `:924`; `escadaChart`, `:952`) |
| Medida | % pago em dia e % pago mais de 30 dias depois | R$: valor de baixa (coluna) e VP em carteira das parcelas baixadas (linha) |
| Pergunta | a pontualidade está melhorando ou piorando? | como os pagamentos do período se distribuem e qual o resultado contra o VP? |

- Se a D21 for a leitura (a) (sobre o recebido), as duas linhas daqui saem da
  coluna da escada mês a mês: "% pago em dia" = faixas antes do vencimento e
  no dia ÷ total; "% pago após 30 dias" = faixas a partir de 31 dias depois ÷
  total. Um cálculo só alimentaria as duas abas.
- Os números do protótipo são de exemplo e não fecham entre si: na carteira
  consolidada de jul–out/2025, "após 30 dias" dá 8,5–8,8% pela escada e
  8,8–9,7% no gráfico; "em dia" dá ~59% pela escada (antes + no dia) e
  45–46% no gráfico, e a base do gráfico é fixa (R$ 1,32 bi) em todos os
  meses. Não servem para concluir a definição; daí a pergunta 5 à
  controladoria.

## Proposta

1. **Faixas mensais**
   ([monthly_band_migration.sql](../attachments/sql/monthly_band_migration.sql)):
   por fundo, produto e faixa, no último `data_ref` de cada mês. Contrato
   inteiro na faixa do seu `dias_atraso` (a parcela mais atrasada arrasta o
   contrato), como o protótipo faz (D20).
2. **Matriz de rolagem — próxima versão (D20 revista em 27/10)**, na
   visualização "Estudo de Migração" (D20)
   ([migration_matrix.sql](../attachments/sql/migration_matrix.sql)): de cada faixa
   no fechamento anterior para cada faixa no fechamento seguinte, mais
   "(saiu)" e "(novo)", em contratos e VP. Prova de conceito na Dayvale A,
   set/26 ([evidência](../evidence/rating-migration-redshift-2026-10-22.md#matriz-de-rolagem-prova-de-conceito)).
3. **Pagamento** ([monthly_payment.sql](../attachments/sql/monthly_payment.sql)):
   % do valor pago no mês que foi pago até o vencimento e mais de 30 dias
   depois, com o mapa de sinal da D5 (D21).
4. **Onde calcular** (D22, provisória): tabelas no Postgres da data-lake-api,
   preenchidas em segundo plano; cada mês fechado é calculado uma vez e a rota
   só lê. Histórico desde jan/26: ~9 pares de meses para a matriz.

### Lógica da tabela da Análise de Migração

Consulta em [monthly_band_migration.sql](../attachments/sql/monthly_band_migration.sql)
(revista em 26/10/2026):

1. **Fechamento de cada mês:** o último `data_ref` do mês com foto do fundo,
   procurado só na última semana do mês e por fundo (o último dia pode vir
   incompleto, P15).
2. **Faixa do contrato:** pelo `dias_atraso` do contrato; nulo = em dia;
   1–30, 31–60 … 151–180, 181+ (D33).
3. **Produto:** pela `dim_contrato` (D17); sem casamento, produto nulo.
4. **Soma:** contratos, VP e PDD por fechamento, fundo, produto e faixa.
   Gravado no Postgres uma vez por mês fechado (D22); ~300 linhas por mês.
5. **Na tela:** linhas = faixas, colunas = meses, valor = VP em R$ mi. Fundo
   escolhido ou soma de todos (consolidada); produtos escolhidos ou todos,
   com os sem produto incluídos quando nenhum é escolhido (D18); período como
   no Histórico; só meses fechados até a data de referência, como o protótipo
   (`dashboard_fundos.html:971-981`).

**Validada pelo Heitor em 26/10/2026** (lógica e custo).

**[C]** Prova com a Dayvale A, 31/08 e 30/09/2026, sem produto, ~1,7 s: em
dia R$ 41,45 → 39,77 mi; 181+ R$ 9,73 → 9,99 mi; soma de 30/09 igual ao
estoque do fundo (R$ 53,54 mi).

### Lógica do Estudo de Migração

> **Próxima versão** (D20 revista em 27/10). A lógica e a consulta ficam
> prontas aqui; ver [later.md](../later.md).

Consulta em [migration_matrix.sql](../attachments/sql/migration_matrix.sql)
(revista em 26/10/2026):

1. **Dois fechamentos:** o do mês anterior e o do mês atual, pela etapa 1 de
   [monthly_band_migration.sql](../attachments/sql/monthly_band_migration.sql).
2. **Faixa de cada contrato nas duas fotos**, pelo `dias_atraso` do próprio
   contrato (D33: 8 faixas).
3. **Junção completa** pelo mesmo administrador, fundo e `id_contrato_admin`:
   presente nas duas fotos = de uma faixa para outra; só na anterior =
   "saiu"; só na atual = "novo".
4. **Só fundos com foto nas duas datas**, para um fundo que sai do arquivo não
   virar uma linha inteira de "saiu".
5. **Produto** pela `dim_contrato` (D17).
6. **Soma** por fundo, produto, faixa de origem e faixa de destino: contratos,
   VP no início e VP no fim. Gravado no Postgres uma vez por par de meses
   (D22).
7. **Na tela:** linhas = faixa no mês anterior (mais "novo"), colunas = faixa
   no mês atual (mais "saiu"), célula = % da linha (D33).

**[C]** Genius E, 31/08 → 30/09/2026, ~29 s para o fundo inteiro (190 mil
contratos; produtos 713, 449, 1043 e sem produto). Produto 713, % dos
contratos de cada faixa de origem:

| De \ Para | Em dia | 1–30 | 31–60 | 61–90 | 91–120 | 121–150 | 151–180 | 181+ | Saiu | Contratos |
|---|---|---|---|---|---|---|---|---|---|---|
| Em dia | 47% | 45% | | | | | | | 8% | 40.122 |
| 1–30 | 6% | 57% | 23% | | | | | | 14% | 44.848 |
| 31–60 | 3% | 18% | 33% | 32% | | | | | 14% | 18.937 |
| 61–90 | 2% | 6% | 6% | 9% | 66% | | | | 12% | 5.483 |
| 91–120 | 1% | 2% | 2% | 1% | 2% | 86% | | | 7% | 3.548 |
| 121–150 | 1% | 1% | 0% | 0% | 0% | 1% | 91% | | 6% | 2.748 |
| 151–180 | 1% | 1% | 0% | 0% | 0% | 0% | 1% | 94% | 4% | 2.787 |
| 181+ | 0% | 0% | 0% | | 0% | 0% | 0% | 99% | 1% | 46.628 |
| Novo | 93% | 7% | | | | | | | | 19.197 |

Leitura: a partir de 61 dias, quase todo contrato continua piorando (66%,
86%, 91%, 94%), o que combina com a régua do 713 subir de 33% para 100% nessas
faixas. **[H]** Os 45% de "em dia → 1–30" parecem alto; pode ser parcela que
vence perto do fim do mês e é paga com poucos dias de atraso. Validar com a
controladoria.

**Custo:** com todos os fundos, as duas fotos somam ~17 mi de contratos.
Rodar fundo a fundo na tarefa mensal (10–30 s cada) evita uma consulta única
longa; ler a `dim_contrato` uma vez só em vez de duas economiza ~15 s.

### Matriz de migração ("Estudo de Migração", D20)

Conferido em 26/10/2026 **[C]**:

- No protótipo, "Estudo de Migração" é uma aba à parte que abre a planilha de
  roll rate do fundo, descrita como "migração entre faixas de atraso e
  validação da régua de PDD por roll rate" (`dashboard_fundos.html:680-692`).
  A matriz é esse conteúdo, agora calculado na tela.
- A aba só aparece com um fundo escolhido (`dashboard_fundos.html:514`,
  `migForFund`).
- O front atual não tem essa aba (`pdd/pdd.view.ts:20-26`): é uma aba nova,
  com o mesmo filtro de produto do Rating e da Análise de Migração.
- Faixa pelo `dias_atraso` do contrato. O arrasto por sacado (D29) é regra de
  provisão; na matriz, ele faria um contrato em dia "rolar" por causa de outro
  contrato do mesmo sacado.

Pontos de atenção:

- **D33:** faixas (as 8 da Análise de Migração ou as da régua de cada produto)
  e escopo (só por fundo e produto, ou também a consolidada).
- **"(saiu)" junta tudo o que deixou o estoque:** pago, baixado por perda,
  recomprado, transferido de fundo. Separar com a liquidação fica para depois
  ([later.md](../later.md)).
- **Dados:** QY com atraso contado desde a migração (P13), então a matriz dela
  não diz nada por enquanto; Kanastro sem atraso de 1 a 14 dias (P14); fundo
  que sai do arquivo (Genius A em set/26, P6) aparece como "(saiu)" em massa.
- **Primeiro mês:** o histórico começa em jan/26, então a primeira matriz é
  jan → fev/26.

## Validação

- Soma das faixas num fechamento = VP do estoque do fundo nesse dia.
- Na matriz, a soma de cada linha "de" = contratos da faixa no fechamento
  anterior; a soma de cada coluna "para" (sem "(saiu)") = contratos da faixa
  no fechamento seguinte.

## Pendências

- **D8 provisória (23/10), opção (b):** a `administradores_estoque_contrato`
  tem a fonte INTERNAL. No fundo que vem por um administrador, vale o
  administrador; a INTERNAL só cobre fundo sem administrador, pela mesma regra
  isolada da data-lake-api ([tarefa 01](01-stock-movement.md#d8-provisória-o-que-muda-no-código-se-mudar)).
  **D55 (27/10):** fundo com INTERNAL e administrador usa o administrador.
  **D56 (27/10):** os fundos só-INTERNAL aparecem, com os dados da INTERNAL;
  produto pela D17 (mesmo cadastro de contratos); dias de atraso e rating
  confirmados pelo Heitor em 27/10 (D56).
  (O ponto "se esta aba mostra os fundos só-INTERNAL" foi resolvido pela D56.)
- D21 (controladoria) em [decisions.md](../decisions.md); D22 provisória. D33
  foi para [later.md](../later.md) com a matriz.
- P13, P14, P15, P16 em [data-problems.md](../data-problems.md).

## Histórico

- **28/10/2026 (integração TS-5442, alterações locais sem commit):** **[C]**
  a data-lake-api já tinha `GET /valid/pdd/dates`, com `fund_legal_id`
  opcional e resposta com `first_date`/`last_date` nulas quando não há dados.
  O BFF passou a expor `GET /controllership/valid/pdd/dates`, normalizando o
  documento e conferindo o fundo no escopo da sessão. Aceita leitura de
  Rating ou Migração; para a carteira de um parceiro, combina apenas os
  intervalos dos fundos dele. O front consulta por fundo ou carteira,
  limita a referência em Rating e Migração, ajusta uma referência fora do
  intervalo e desabilita o seletor enquanto não há limites disponíveis.
  Resposta atrasada de outro fundo é cancelada. Visão Geral e Histórico
  continuam sem esses limites.
  Referências desta atualização: BFF `44d0427` + alterações locais,
  `src/modules/controllership/valid/viewer.py:160` e `business.py:237`;
  front `184df4b4` + alterações locais,
  `src/app/features/controllership/pdd/pdd.page.ts:145` e `:512`;
  data-lake-api `1d5a156` + alterações locais já existentes.
  Validação local: tipos e build de desenvolvimento do front, lint dos
  arquivos alterados, 18 testes de arquitetura do BFF, 3 testes existentes
  de business e 4 testes de PDD da data-lake-api passaram. A chamada direta
  da rota, com serviços simulados, passou em 8 cenários e 5 verificações de
  permissão. Os novos testes HTTP e os specs de navegador não puderam
  executar: o ambiente bloqueia comunicação local. A validação completa
  também encontrou lint/padrões no protótipo local não versionado e falta
  de acesso à fonte externa na compilação otimizada. Auditoria de
  dependências não executada por falta de rede. Nenhum deploy, push, job
  ou acesso a serviços reais da aplicação foi executado.
- **22/10/2026:** protótipo mapeado; viabilidade conferida no lake
  (`dias_atraso`, estabilidade do contrato, matriz de prova na Dayvale A,
  pagamento de set/26). D20, D21 e D22 abertas.
- **25/10/2026:** D18 tomada (Heitor). Heitor pediu explicação da matriz de
  migração (D20), do gráfico de pagamento (D21) e do que seria calculado (D22).
- **27/10/2026 (noite):** primeira versão da tela no front, na branch da
  TS-5438, **sem commit**, para ver com dados fictícios (`127.0.0.1:4201`):
  componente `pdd/migration/pdd-migration.component` (tabela de VP por faixa
  e fechamento, com linha de total; o card de pagamento fica "em definição"
  até a D21), `buildAgingTable` e `agingWindowStart` em `pdd.view.ts`, rota
  provisória `controllership/valid/aging` (D49) e 288 linhas fictícias em
  `.ai/scripts/smoke-data/controllership.json`. Specs escritos e não rodados
  (sem Chromium na máquina); lint dos arquivos alterados limpo.
- **27/10/2026:** Heitor adiou a matriz de migração para a próxima versão
  (D20 revista); D33 para later.md.
- **26/10/2026 (noite, 3):** consulta da Análise validada pelo Heitor. Lógica
  do Estudo de Migração registrada e testada no Genius E (29 s); D33 ampliada
  (medida do % e período).
- **26/10/2026 (noite, 2):** lógica da tabela da Análise de Migração
  registrada e provada na Dayvale A.
- **26/10/2026 (noite):** D17 e D20 tomadas (matriz no "Estudo de
  Migração", conferida contra o protótipo); D22 provisória (Postgres); D33
  aberta.
- **26/10/2026:** D18 completada (contratos sem produto entram nos totais).
  Explicação do retrato × matriz registrada (D20, ainda em aberto). D21 vai
  para a controladoria, com a pergunta acima.
- **23/10/2026:** D8 provisória, opção (b), vinda da tarefa 01. A definir se
  esta aba mostra os fundos só-INTERNAL.
- **27/10/2026 (commits, sem push):** branch `feature/TS-5438-pdd-abertura-de-rating`
  nos quatro repositórios. platform-cessao (3): repositório, régua em vigor na
  data, rota `GET /pdd/regua-vigente`. BFF (3): chamadas, business (rating,
  recálculo PLGN, faixas mensais), rotas `valid/pdd` e `valid/aging` com escopo
  do parceiro. data-lake-api (9): módulo `valid` em pacotes, configuração,
  modelos, migration 0009 (não aplicada), leitura no Redshift, poça no
  Postgres, execução diária (D58), rotas, tasks sem agendamento. Front (5):
  data-access, abertura de rating, painel PLGN, tabela de migração, mock.
  Cada commit do front compila sozinho (`ng build` por etapa); os da
  data-lake-api importam e passam nos testes do PDD um a um. Não rodados: testes
  do front (sem Chromium), do platform-cessao (Python 3.8 e índice privado) e
  os da poça contra um Postgres. Hook `test-arch` da data-lake-api pulado: falha
  para qualquer commit fora do container (ambiente isolado sem `pydantic`) e o
  teste já quebra na master (`day_cache.py`).
