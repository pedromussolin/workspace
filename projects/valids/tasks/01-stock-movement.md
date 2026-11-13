+++
card = "TS-5441"
type = "task"
epic = "TS-5690"
assignee = "dev-a0893bc9a2"
reporter = "dev-a0893bc9a2"
relates = ["TS-4366", "TS-5044", "TS-4815"]

[tracker]
status = "done"
priority = "Medium"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 01 — Mov. Estoque: aquisições, baixas e accrual de juros

- **Status:**
  - 21/10/2026: desenho de aquisições (D2), baixas (D3) e accrual (D4).
  - 22/10/2026: mapa de sinal das baixas no código (D5); qualquer par de
    datas (D6); accrual pela foto de cada dia (D9); taxas como vêm do lake
    (D12); pontas do período (D13); accrual por roll-forward por parcela, numa
    consulta só por intervalo (D15, substitui a D4).
  - 23/10/2026: intervalo de dia (D23); fonte da `get_stock` em
    `administradores_estoque_contrato` (D7).
  - 23/10/2026: INTERNAL pela opção (b), **provisória** até a controladoria
    validar (D8): Visão Geral e Histórico com todos os fundos; Mov. Estoque só
    para fundo de administrador, sem consolidado. Cálculo pela consolidação
    Celery → Postgres, task por dia (D10). Visão Geral e Histórico também
    calculados antes e guardados (D25). Rota nova `/valid/stock-movement`
    (D11).
  - 23/10/2026: aba visível com aviso na carteira consolidada e nos fundos
    só-INTERNAL (D24). **Todas as decisões da Mov. Estoque tomadas**; a D8
    segue provisória até a controladoria validar.
  - 23/10/2026: **implementado nas três branches, sem commit** (ver
    [Implementação](#implementação-2310)). Nenhuma query rodada no Redshift.
  - 26/10/2026: movimentação na "poça" do Postgres, numa consolidação
    própria, separada da do Chrisgol e no mesmo modelo, por fundo
    (D34). data-lake-api refeita sem commit (ver
    [Implementação na poça](#implementação-na-poça-2610-d34)); BFF e front
    não mudam.
- **Repos:** data-lake-api (consultas, consolidação diária e rota), BFF (rota
  e consolidação por fundo), front (waterfall e evolução mensal).
- **Conceitos financeiros** (valor presente, taxa, accrual): ver
  [concepts.md](../concepts.md).

## Item original

> Aba "Mov. Estoque": hoje só "Saldo Inicial" e "Estoque Real" vêm do lake,
> por consultas que já existem na data-lake-api. Aquisições, Baixas e Accrual
> de Juros ainda não têm consulta, porque as views só entraram agora.
> Aquisições: `administradores_aquisicao`. Baixas: `administradores_liquidacao`.
> Accrual de juros: ainda não se sabe como trazer. Só as views
> `administradores_*` podem ser usadas.
>
> — Heitor, 21/10/2026

## O que a tela precisa

Do protótipo `dashboard_fundos.html` (local, fora do git do front) **[C]**:

- **Waterfall do período** (`renderRecon`, `dashboard_fundos.html:1015-1037`;
  `waterfallChart`, `:1038`): saldo inicial, soma das aquisições, baixas e
  accrual, saldo final calculado e estoque real. O subtítulo mostra a
  diferença entre os dois saldos, em vermelho a partir de 1% e em amarelo a
  partir de 0,3%.
- **Evolução mensal** (`reconEvoChart`, `:1063`): aquisições, baixas e
  accrual mês a mês.
- **Alerta "Accrual a revisar"** na Visão Geral quando a diferença passa de
  1% (`:1199-1203`).
- O protótipo guarda por mês `[saldo inicial, aquisições, baixas (negativo),
  accrual, saldo final calculado, estoque real]`. O accrual era calculado à
  parte, não como sobra da conta, e por isso a diferença serve de conferência.
  Na tela nova o período é livre (D6).

A conta:

```
saldo final calculado = saldo inicial + aquisições − baixas + accrual
conferência           = saldo final calculado − estoque real
```

## Como está hoje

**[C]**, commits do README:

- **Front:**
  - A aba mostra só as duas âncoras. `buildWaterfallChart`
    (`src/app/features/controllership/pdd/pdd.view.ts:416`) deixa aquisições,
    baixas, accrual e saldo final como categoria sem barra.
  - `buildStockReconciliation` (`pdd.view.ts:356`) compara o primeiro
    fechamento do recorte com o da **data de referência**, não com a Data
    final do filtro. Com movimentos somados no período, isso precisa mudar
    (D13).
  - A evolução mensal é um estado vazio (`stock/pdd-stock.component.html:21-30`).
  - Os dados vêm de `getStock` (`data-access/pdd/stock.service.ts:35`).
- **BFF:** `GET controllership/valid/stock`
  (`src/modules/controllership/valid/viewer.py:57`) chama a data-lake-api e,
  na carteira consolidada, soma todas as linhas
  (`business.py:54`, `:139-145`); com um fundo escolhido, pega a primeira
  linha cujo CNPJ casa (`business.py:152`).
- **data-lake-api:** `GET /valid/stock` (`src/modules/valid/viewer.py:37`)
  busca 2 anos (`business.py:11`) com cache de 24 h no Redis, pela consulta
  `GET_STOCK_DATA` (`src/infra/redshift/queries/plgn/valid.py:3`), que lê
  `plgn.estoque_contrato` (`valid.py:22`). Essa tabela **não** é uma view
  `administradores_*` ([P1](../data-problems.md#p1--o-estoque-atual-não-vem-de-uma-view-administradores_), D7).

## Período e foto diária

Decisões D6 e D9: qualquer par de datas, e tudo calculado por dia.

- **Só há foto em dia útil.** **[C]** De 04/09/2026 (sexta) a próxima foto é
  08/09 (07/09 foi feriado), nos 5 administradores com estoque na data.
- **Um número por fundo e por dia:** aquisições e baixas do dia (`data_ref`) e
  o accrual da foto do dia (calculado sobre a foto anterior). Qualquer período
  é a soma dos dias; a evolução mensal é a soma por mês.
- **Pontas do período (D13, decidida em 22/10):**
  - saldo inicial = última foto **antes** da Data inicial;
  - movimentos da Data inicial à Data final, inclusive;
  - estoque real = última foto **até** a Data final.

  Exemplo: de 01/09 a 30/09 → saldo de 31/08, movimentos de 01/09 a 30/09,
  estoque de 30/09.
- **O estoque real passa a seguir a Data final.** Hoje ele fica preso à data
  de referência (`pdd.view.ts:356`). Se o usuário escolher Data final antes
  da referência, o waterfall somaria movimentos de um período e compararia
  com o estoque de outro.

## Aquisições

Decisão D2: soma do `vl_aquisicao` por administrador, fundo e dia, filtrando
por `data_ref`. Consulta: [attachments/sql/acquisitions_by_day.sql](../attachments/sql/acquisitions_by_day.sql).

- **[C]** A view é um arquivo diário de eventos: `data_ref` = `data_aquisicao`
  em todas as linhas vistas (13 a 20/10/2026).
- **[C]** A BGT manda parte das aquisições por contrato, sem `id_parcela`. Não
  muda a soma; só importa para cruzar por parcela.
- Lacunas a validar: Dayvale sem aquisição em set/26
  ([P5](../data-problems.md#p5--dayvale-aquisições-faltando-e-um-dia-gigante));
  QY entra em set/26 já com R$ 543 mi de "aquisições"
  ([P6](../data-problems.md#p6--fundos-que-não-fecham-no-mês)).

## Baixas

Decisão D3: soma do `vl_pago`, por administrador, fundo, dia e tipo de
movimento. Consulta: [attachments/sql/settlements_by_day.sql](../attachments/sql/settlements_by_day.sql).
O `vl_presente` da liquidação não é usado: só Dayvale e Fydd o preenchem
([P3](../data-problems.md#p3--vl_presente-da-liquidação-só-em-dois-administradores)).

### Observação: estoque a VP × baixa pelo valor pago

O estoque é medido a valor presente. Quando a parcela sai do estoque, o saldo
cai pelo **VP dela naquele dia**, não pelo valor pago. Exemplo: parcela com VP
de R$ 970 quitada antecipadamente por R$ 980. O estoque cai R$ 970, a baixa
pelo `vl_pago` é de R$ 980, e o saldo final calculado fica R$ 10 abaixo do
estoque real.

Esses R$ 10 são resultado da liquidação (desconto ou ágio na antecipação,
juros de mora, perda na renegociação), não erro. Eles aparecem como
**diferença entre o saldo final calculado e o estoque real**, e quem olhar a
conferência precisa saber disso.

**[C]** No Fydd A em set/26: `vl_pago` R$ 8,11 mi × VP baixado R$ 6,98 mi.
A diferença de R$ 1,13 mi bate com o `vl_ajuste` (−R$ 1,18 mi).

### Sinal por tipo de movimento (D5)

Decisão D5 (22/10/2026): mapa tipo → sinal no código, por administrador. Tipos
vistos em set/26 e de 13 a 20/10/2026; a tabela é o ponto de partida do mapa.
Os itens marcados "a validar" ou **[H]** ainda pedem confirmação.

| Administrador | Tipo | Proposta |
|---|---|---|
| BGT | `InstallmentPayment`, `Payment` | +1. **[C]** não se repetem no mesmo contrato e dia (15/09) |
| Dayvale | `LIQUIDACAO COBRANCA`, `BAIXA RENEGOCIACAO PRESERVA PDD`, `BAIXA DE SALDO`, `BAIXA POR DEPOSITO SACADO` | +1 |
| Fydd | `BAIXA` | +1 |
| Fydd | `HONORARIOS` | a validar: `vl_pago` de R$ 10,7 mil contra nominal de R$ 74 mil em set/26 |
| Genius | liquidação normal, antecipada e parcial; baixa parcial e automática; baixa por renegociação; troca com troco; resolução de cessão por cancelamento ou devolução; alienação para terceiros; baixa parcial zerada | +1. Renegociação e troca: confirmar se o contrato novo entra como aquisição |
| Kanastro | `total_liquidation`, `partial_liquidation`, `interest_liquidation` | +1 |
| QY | `installment_settlement`, `installment_fine_payment`, `fine_payment` | +1 |
| QY | `asset_settlement` | +1, confirmando que não repete o `installment_settlement` |
| QY | `installment_payment_reversal`, `installment_partial_refund` | −1 **[H]**: vêm com `vl_pago` positivo ([P4](../data-problems.md#p4--estornos-com-vl_pago-positivo-na-qy)) |
| QY | `gloss` | +1: o `vl_pago` já vem negativo **[H]** |
| QY | `installment_reactivation` | 0: `vl_pago` = 0 |

Os tipos com acento apareceram com `?` no cliente usado. Conferir o valor
exato antes de escrever o mapa.

## Accrual de juros

**Decisão atual (D15, 22/10):** roll-forward por parcela, encadeado em
intervalos curtos, numa consulta só por intervalo (seção abaixo). As seções
seguintes sobre taxa × prazo (D4, D9, D12, D14) ficam como histórico do
caminho até aqui. Explicação para quem não é da área:
[concepts.md](../concepts.md).

### Consulta única por intervalo (D15)

Consulta: [attachments/sql/movement_by_interval.sql](../attachments/sql/movement_by_interval.sql).
Para um intervalo entre duas fotos, `(:foto_anterior, :foto]`, devolve por
fundo:

| Coluna | O que é | De onde vem |
|---|---|---|
| `opening_balance` | saldo inicial | VP da foto anterior |
| `acquisitions` | aquisições | `vl_aquisicao` do intervalo (D2) |
| `liquidations` | baixas | `vl_pago` do intervalo, com o sinal da D5 |
| `interest_accrual` | accrual | variação de VP das parcelas presentes nas duas fotos + pagamentos delas no intervalo |
| `closing_balance` | estoque real | VP da foto atual |
| `paid_on_remaining` | pagamentos das parcelas que ficaram | já somado no accrual; sai à parte para conferir |
| `pv_entered` | VP das parcelas que entraram | foto atual, parcelas que não estavam na anterior |
| `pv_exited` | VP das parcelas que saíram | foto anterior, parcelas que não estão na atual |

**Por que uma consulta só:**
- A parte pesada é ler as duas fotos da view por parcela e juntá-las. Saldo
  inicial, estoque real e accrual saem dessa mesma leitura.
- Aquisição e liquidação do intervalo são leves (sortkey `data_ref`) e entram
  como CTEs.
- O saldo e o estoque passam a ter a mesma base do accrual (D7 revista).

**Por que um intervalo por consulta, e não o período inteiro de uma vez:**
- O período é o encadeamento dos intervalos: o estoque real de um é o saldo
  inicial do seguinte, e os componentes somam.
- Juntar 2 anos numa consulta só (com `LAG` por parcela) leria todas as fotos
  de uma vez: centenas de milhões de linhas numa execução, alto risco de o
  Redshift abortar.
- Um intervalo por execução da consolidação (D10) é incremental, pode ser
  retentado e só calcula o que é novo.
- Intervalo de dia (D23): cada execução usa a foto do dia e a foto anterior a
  ela (o dia útil anterior com foto).

**A conferência se explica pela própria consulta.** Por construção:

```
estoque real − saldo calculado
  = (pv_entered − acquisitions) + (liquidations − paid_on_remaining − pv_exited)
```

- O primeiro termo é a diferença entre o VP das parcelas novas e o preço pago
  (rendimento desde a compra, salto na entrada, aquisição sem registro).
- O segundo é a diferença entre o pago pelas parcelas que saíram e o VP delas
  (rendimento até a saída, resultado na liquidação, baixa sem registro).

**[C] Teste no Fydd A, 31/08 → 30/09/2026** (consulta filtrada só nesse fundo):

| Coluna | R$ mi |
|---|---|
| Saldo inicial | 150,13 |
| Aquisições | 8,60 |
| Baixas | 8,11 |
| Accrual | 1,28 (nenhum pagamento em parcela que ficou) |
| Estoque real | 155,51 |
| Entradas a VP / saídas a VP | 10,20 / 6,10 |

Saldo calculado = 151,90. Conferência = 155,51 − 151,90 = 3,61 =
(10,20 − 8,60) + (8,11 − 0 − 6,10). Reproduz os números da reconciliação de
21/10.

**Falta testar:**
- **Custo com todos os fundos** num par de fotos, fora do horário comercial e
  combinado com o time de dados, para dimensionar a execução diária e o
  backfill (D23).
- **Pagamentos casando com as parcelas:** conferir se o `id_parcela` da
  liquidação casa com o do estoque em todos os administradores. Se não casar,
  o pagamento parcial vira accrual negativo. No Fydd A, `paid_on_remaining`
  veio zero.

### Por que por parcela e não por contrato (23/10)

Pergunta do Heitor: fazer o roll-forward com `administradores_estoque_contrato`.
Dá, e é mais leve: ~7,5 mi de contratos por foto contra ~40 mi de parcelas,
fora a INTERNAL. Mas o accrual deixa de ser só rendimento. Quando uma parcela
é paga, ou quando o fundo compra mais parcelas de um contrato que já tem, o
contrato continua no estoque e o VP dele muda por isso. Na comparação por
contrato, essas mudanças caem dentro do "VP de quem ficou".

**[C]** Kanastro A, 31/08 → 30/09/2026, R$ mi (consultas filtradas no fundo):

| | Por contrato | Por parcela |
|---|---|---|
| Variação do VP de quem ficou | −33,01 | +48,73 |
| + pagamentos de quem ficou | +91,80 | +6,07 |
| **= accrual** | **58,78** | **54,80** |
| VP das entradas (aquisições: 73,49) | 62,58 | 78,90 |
| VP das saídas | 18,86 | 116,93 |
| Conferência | −6,07 (−0,36%) | −2,09 (−0,12%) |

A diferença de 3,98 no accrual é a soma de duas coisas que não são juros:

- **+16,32:** parcelas novas compradas dentro de contratos que o fundo já
  tinha (78,90 − 62,58). É aquisição.
- **−12,34:** diferença entre o pago (85,73) e o VP (98,06) das parcelas que
  saíram de dentro de contratos que continuaram. É resultado da baixa.

Neste mês as duas se compensaram em parte; em outro mês, podem não se
compensar. Por contrato, o accrual mistura aquisição e resultado de baixa, e a
conferência perde a separação. Por parcela, cada coisa fica no seu lugar.

Em fundo com uma parcela por contrato (o Fydd tem ~1), os dois níveis dão o
mesmo resultado. **Alternativa se o teste de custo falhar (D23):** roll-forward
diário por contrato, aceitando o accrual menos puro, antes de passar para o
encadeamento mensal.

## Caminho até a D15 (histórico)

Primeiro desenho (D4, D9 e D12), substituído pela D15: **taxa × prazo**, sobre a view
por parcela (`plgn.administradores_estoque`), **foto a foto**, com as taxas
como vêm do lake. Consulta de um dia: [attachments/sql/accrual_by_day.sql](../attachments/sql/accrual_by_day.sql).

### Como funciona

O administrador calcula o VP de cada parcela como
`nominal ÷ (1+i)^(prazo/base)`. Com o tempo, o prazo encurta e o VP sobe em
direção ao nominal; essa subida é o accrual. Para cada foto, sobre as parcelas
a vencer da foto anterior:

```
accrual do dia = VP na foto anterior × ((1 + i)^(n / base) − 1)
n              = dias desde a foto anterior, limitado aos dias até o vencimento
```

| `metodo_taxa_*` | Base | Dias (n) |
|---|---|---|
| `expb252_aa` | 252 | úteis: 1 entre dois dias úteis seguidos |
| `exp360_aa` | 360 | corridos: 3 de sexta para segunda |
| `exp365_aa` | 365 | corridos |

- **Taxa:** ver [Qual taxa e por quê](#qual-taxa-e-por-quê) logo abaixo.
- **Unidade:** a BGT manda em percentual (75,32 = 75,32% a.a.), então divide
  por 100 (parâmetro `:fontes_taxa_percentual`). Os demais mandam em fração
  (0,2388 = 23,88% a.a.).
- **Problemas nas colunas de taxa** (P7, P8, P10) ficam com o time de dados;
  o código não os contorna (D12). Enquanto não forem corrigidos, parcela sem
  taxa sai sem accrual e o efeito aparece na conferência.
- **Dias entre fotos:** calendário B3 que já existe na data-lake-api
  (`src/shared/utils/business_days.py:12`, `is_business_day`).

### Qual taxa e por quê

**Regra de hoje:** por parcela, `taxa_recebivel` com `metodo_taxa_recebivel`;
se vier vazia, `taxa_cessao` com `metodo_taxa_cessao`. O que cada taxa
significa: [concepts.md](../concepts.md#3-que-taxa-é-essa).

**Por quê:** o accrual tem que reproduzir a subida do VP, então precisa da
mesma taxa que o administrador usou para calcular o VP. Nenhuma coluna diz
qual foi; a regra saiu dos dados. **[C]**:

1. **Amostra de 4 parcelas por administrador (30/09):** a taxa implícita no VP
   bate com a `taxa_recebivel` em Fydd e Genius. No Kanastro as duas taxas são
   praticamente iguais; na Dayvale a implícita fica entre as duas; na BGT
   nenhuma bate (P8).
2. **Agregado das parcelas a vencer do Fydd A em set/26:** variação real
   1,092; com `taxa_recebivel` 1,088 (−0,3%); com `taxa_cessao` 1,073 (−1,7%).
   A do recebível chega mais perto, mas a de cessão também não fica longe.
3. **BGT:** a `taxa_recebivel` vem vazia, então só sobra a `taxa_cessao`.

**É 100% válido? Não.** É a melhor regra que os dados mostraram, não uma regra
confirmada:

- O significado das colunas não foi confirmado com quem gera o dado.
- O teste cobre uma amostra pequena e 5 fundos num mês. Genius C (+16%) e
  BGT (+24%) desviam por motivos ainda não provados (pagamento parcial, P8).
- A regra é por parcela, não por administrador: se um administrador preencher
  as duas e calcular o VP pela de cessão, ela erra sem avisar.
- A `taxa_recebivel` vem arredondada em 2 casas em alguns administradores
  (Fydd 0,50 contra 0,5058 implícita; Dayvale 0,23 ou 0,24 contra ~0,2395).
  **[H]** Isso deve explicar desvios pequenos como o −2,1% da Dayvale.

**Como fica válido (D14):** o time de dados ou a controladoria confirma, por
administrador, qual coluna de taxa e de método reproduz o VP. A regra vira um
mapa explícito (fonte → coluna), com os valores de hoje como ponto de partida.
A conferência por fundo continua mostrando quando algo sair do lugar.

### Roll-forward diário: custo e efeito

Pergunta do Heitor (22/10): se a fórmula já lê a foto de cada dia, o
roll-forward por parcela não sairia quase pelo mesmo custo? Decisão em aberto:
D15.

**Como seria:** para cada par de fotos seguidas (d−1 e d), juntar as parcelas
pelo `id_parcela` e separar em três grupos:
- **ficaram:** a variação de VP delas é o accrual;
- **entraram:** VP na foto d, a comparar com as aquisições do dia;
- **saíram:** VP na foto d−1, a comparar com as baixas do dia.

**Custo, comparado com a fórmula.** **[C]** Pelo plano do Redshift (`EXPLAIN`
de um dia, todos os fundos, 22/10):
- **Fórmula:** lê uma foto e soma por fundo.
- **Roll-forward:** lê duas fotos e junta. A tabela não é distribuída por
  parcela (`AUTO(EVEN)`), então o plano mostra `DS_DIST_BOTH`: as duas fotos
  (~70 mi de linhas) são redistribuídas entre os nós antes da junção, e uma
  delas vira tabela de hash de ~35 mi de linhas.

O planejador estima 1 linha para a tabela, então o `EXPLAIN` não dá números
para comparar. **[H]** Algumas vezes o custo da fórmula por dia: minutos, o que
cabe numa consolidação em segundo plano, mas precisa de um teste real.

**Sinal de risco (corrigido em 23/10):** as junções "abortadas" em 22/10
(Genius C e Dayvale A) pararam em ~59,9 s, o limite de 60 s que o cliente
`attachments/rsq.py` impõe (`statement_timeout`). Nenhuma regra do Redshift agiu
nelas (`stl_wlm_rule_action` vazio). Ver a
[estimativa de custo](../evidence/stock-movement-redshift-2026-10-21.md#estimativa-de-custo-pelo-histórico-do-redshift-23102026).

**O que o roll-forward ganha:**
- **Não depende das colunas de taxa:** P7, P8, P10 e a D14 deixam de afetar o
  accrual, e os fundos BGT sem taxa passam a ter accrual.
- **O accrual é o que o administrador de fato apropriou** no VP.
- **A conferência se separa em grupos:** entrada com e sem aquisição
  registrada, saída com e sem baixa registrada. Isso aponta direto falhas
  como a falta de aquisições da Dayvale (P5).

**Cuidados:**
1. **Pagamento parcial:** a parcela que recebeu parte do valor continua no
   estoque com VP menor. O roll-forward contaria essa queda como accrual
   negativo, e a baixa (`vl_pago`) a subtrairia de novo. É preciso somar de
   volta os pagamentos do dia das parcelas que ficaram (junção pequena com a
   liquidação pelo `id_parcela`).
2. **Toda mudança de VP das parcelas que ficaram vira "accrual":** além dos
   juros, recálculo do administrador, troca de taxa, renegociação sem baixa e
   o VP de vencidas que sobe na Genius (P9). Com a fórmula, esses casos
   aparecem na conferência; com o roll-forward, ficam dentro do accrual.
3. **`id_parcela` estável entre fotos:** **[C]** confirmado nos fundos testados
   (Fydd A, Kanastro A, Dayvale A, Genius C, BGT B+H+L e G); conferir nos
   demais.

**Antes de decidir:** rodar um dia inteiro (todos os fundos) fora do horário
comercial, combinado com o time de dados, e medir tempo e se o Redshift
aborta.

#### Por que não basta comparar a Data inicial com a final

Pergunta do Heitor (22/10): pegar as parcelas da Data inicial e subtrair o VP
delas na Data inicial do VP na Data final. É o mesmo roll-forward, feito uma
vez só. A conta enxerga só as parcelas presentes nas duas pontas e perde o
rendimento de:

1. **quem saiu no meio** (paga ou baixada): rendeu até sair, mas não tem VP no
   fim;
2. **quem entrou no meio** (comprada): rendeu desde a compra, mas não tem VP no
   início.

Exemplo de um ano ([concepts.md](../concepts.md#7-a-foto-de-cada-dia)):

| | Accrual | Saldo calculado | Conferência |
|---|---|---|---|
| Real (A rendeu 200, B rendeu 94,43) | 294,43 | 894,43 | 0 |
| Só as duas pontas | 0 | 600,00 | −33% |
| Encadeado por mês | 260,99 | 860,99 | −3,7% |
| Encadeado por dia | 294,43 | 894,43 | 0 |

**[C]** Mesmo num mês: no Fydd A em set/26, as parcelas presentes nas duas
pontas explicam R$ 1,28 mi dos R$ 3,76 mi de variação de VP; o resto está nas
que entraram (R$ 1,60 mi) e nas que saíram (R$ 0,88 mi).

Completar a conta das pontas com aquisições e baixas por parcela também não
resolve: o resultado das baixas entraria no accrual e a conta fecharia sempre,
o mesmo problema do residual.

#### Proposta do Heitor: pontas no waterfall, meses na tabela (22/10)

- **Waterfall:** VP na Data final − VP na Data inicial.
- **Tabela:** VP no fim de cada mês − VP no início do mês.

Análise:

1. **"VP" tem que ser das parcelas que estavam no estoque na Data inicial.**
   Com o VP do estoque inteiro, a diferença já inclui aquisições e baixas, que
   o waterfall soma de novo. No exemplo do ano: accrual de 94,43 e saldo
   calculado de 694,43 contra 894,43 reais.
2. **Gráfico e tabela divergem** em período com mais de um mês: no exemplo
   do ano, accrual 0 no waterfall e 260,99 somando a tabela.

**Ajuste sugerido:** a lógica da tabela vira a base única, e o accrual do
waterfall é a soma dos meses do período (opção (d) da D15). Exige meses
fechados na tela (reabre a D6). O custo cai para uma junção de duas fotos por
mês, e cada parcela perde o rendimento do mês em que entrou ou saiu, o que vai
para a conferência. O cuidado com pagamento parcial continua valendo. Escolha
entre (d) e (b) em aberto.

**Complemento do Heitor:** na tabela, todos os meses só com as parcelas que
estavam na Data inicial (coorte fixa). Análise:

1. **As parcelas compradas no período nunca entram.** No exemplo do ano, B
   (comprada em julho) não aparece; em agosto, A rende 17,10 e B 15,30. **[C]**
   O Kanastro baixou R$ 115,50 mi sobre R$ 1.669,67 mi em set/26 (~7% no mês).
   **[H]** Nesse ritmo, depois de 12 meses restam ~42% das parcelas iniciais, e
   o accrual da tabela cairia mês a mês sem o do fundo cair.
2. **A conferência cresce com o período** e o alerta de 1% dispara em quase
   todo período maior que um mês.
3. **Gráfico e tabela ainda divergem:** a parcela da coorte que sai no meio
   entra na tabela nos meses completos e fica fora das pontas.

| Exemplo do ano | Accrual |
|---|---|
| Waterfall (coorte, pontas) | 0 |
| Tabela (coorte, mês a mês) | 181,58 |
| (d): cada mês com as parcelas do início daquele mês | 260,99 |
| Real | 294,43 |

**Sugerido:** (d) na tabela e no waterfall (soma dos meses). A coorte pode ser
uma visão à parte ("rendimento da carteira na Data inicial"), se a
controladoria quiser. Confirmar de onde veio a regra da coorte.

#### Dá para usar o VP diário da `get_stock`? (22/10)

Não para o accrual. **[C]** A rota traz o VP **somado por fundo e dia**
(`GROUP BY` fundo e `data_ref` em `src/infra/redshift/queries/plgn/valid.py`,
repassado pelo BFF em `business.py:122`). O roll-forward precisa do VP **por
parcela**, para saber quais ficaram, entraram e saíram. Com a soma, só dá para
fazer a conta pela sobra (opção A, descartada na D4): (VP de hoje − VP de
ontem) − aquisições + baixas. Fazer isso por dia não muda nada, porque os VPs
intermediários se cancelam na soma e o resultado é o mesmo da conta feita no
período inteiro. A série da `get_stock` continua servindo para o saldo inicial
e o estoque real (D7).

### Comportamento por situação da parcela

1. **A vencer:** rende pela taxa. **[C]** Bate com a variação real do VP em
   Fydd (−0,3%), Kanastro (−0,1%) e Dayvale (−2,1%) num mês inteiro.
2. **Vence no meio do período:** rende só até o vencimento (o limite de n).
   **[C]** Bate em Fydd e Dayvale.
3. **Já vencida:** não rende. **[C]** Em Fydd e Dayvale o VP das vencidas
   ficou exatamente igual. Na Genius C subiu R$ 0,36 mi
   ([P9](../data-problems.md#p9--genius-vp-de-parcela-vencida-sobe)).
4. **Pagamento parcial:** o VP real cai pelo valor pago, mas isso já entra
   como baixa pelo `vl_pago`; o taxa × prazo mede só o rendimento. **[H]**
   Explica a diferença na Genius C (+16%; R$ 17 mi de "baixa parcial" em set/26
   no administrador) e na BGT (+24%).
5. **Entrou ou saiu no meio do período:** com a foto diária, a parcela rende
   enquanto está no estoque. Sobra só o dia da entrada e o da saída.
6. **PDD:** não entra; o VP é bruto.

Resultado de set/26 (31/08 → 30/09, numa foto só), parcelas que ficaram no
estoque, R$ mi ([evidência](../evidence/stock-movement-redshift-2026-10-21.md#taxa--prazo--variação-real-do-vp)):

| Fundo | Grupo | Variação real do VP | Taxa × prazo | Desvio |
|---|---|---|---|---|
| Fydd A | a vencer | 1,09 | 1,09 | −0,3% |
| Kanastro A | a vencer | 49,57 | 49,53 | −0,1% |
| Dayvale A | a vencer | 0,58 | 0,57 | −2,1% |
| Genius C | a vencer | 10,84 | 12,62 | +16% |
| BGT B+H+L | a vencer | 4,46 | 5,53 | +24% |

### Custo

- **Um dia:** uma leitura da foto por parcela (~35 mi de linhas; a sortkey corta
  o resto). **[C]** Em 21/10, a consulta de um dia para todos os fundos coube
  no limite de 60 s do cliente.
- **2 anos:** ~500 fotos. Não cabe numa chamada da tela, então cada dia é
  calculado uma vez e gravado por fundo, na consolidação Celery → Postgres que
  a data-lake-api já tem (D10). A rota só soma.
- **[H]** Se um administrador reprocessar a foto de um dia, o dia precisa ser
  recalculado; prever isso na consolidação.

## Conferência esperada em set/26

Calculada em 21/10, ainda **numa foto só** (31/08 com 21 dias úteis e 30
corridos), D2, D3 sem o mapa da D5, e D4. Com a foto diária, o accrual deve
subir um pouco nos fundos que compraram no mês, porque as parcelas novas
passam a render a partir da entrada. R$ mi
([evidência](../evidence/stock-movement-redshift-2026-10-21.md#conferência-com-o-accrual-mensal)):

| Fundo | Saldo inicial | Aquisições | Baixas | Accrual | Saldo calculado | Estoque real | Conferência |
|---|---|---|---|---|---|---|---|
| Kanastro A | 1.669,67 | 73,49 | 115,50 | 55,35 | 1.683,02 | 1.680,38 | +0,2% |
| BGT C | 148,58 | 0,00 | 9,11 | 5,75 | 145,22 | 145,12 | +0,1% |
| Genius E | 121,27 | 11,90 | 11,80 | 3,26 | 124,62 | 125,17 | −0,4% |
| Genius B | 386,38 | 57,39 | 46,35 | 43,69 | 441,12 | 444,16 | −0,7% |
| Fydd A | 150,13 | 8,60 | 8,11 | 1,34 | 151,96 | 155,51 | −2,3% |
| Dayvale A | 55,26 | 0,00 | 8,31 | 0,69 | 47,64 | 53,54 | −11,0% |

BGT B, D, E e H e Genius C e G também ficam dentro de ±1,5%. Os desvios
grandes coincidem com problemas de dado: BGT A (+13,6%) e BGT F (−31,1%) se
compensam em boa parte ([P6](../data-problems.md#p6--fundos-que-não-fecham-no-mês)),
Dayvale sem aquisições (P5), Genius D (+9,7%) e F (−10,0%) a investigar, e
BGT G, J, K e L sem taxa (P7).

O que cai na conferência:

1. **Resultado nas baixas:** `vl_pago` − VP da parcela na saída (D3).
2. **Salto na entrada [H]:** quando o estoque é avaliado a uma taxa menor que
   a da aquisição, o VP da parcela nova já nasce acima do `vl_aquisicao`
   ([concepts.md](../concepts.md#8-o-que-sobra-na-conferência)). No Fydd A,
   o VP em 30/09 das parcelas novas foi de R$ 10,20 mi contra R$ 8,60 mi de
   aquisição. A causa ficou mais incerta em 22/10: no agregado do Fydd, a taxa
   de cessão não é sistematicamente maior que a do recebível (P10).
3. **Dia da entrada e da saída** de cada parcela (foto diária).
4. **Falha de dado** (P5, P6, P7, P9).

## D10 em detalhe: consolidação diária

> **Revisto pela D26 (23/10):** sem tabelas novas. O resultado de cada dia
> fica no Redis, não no Postgres; o resto (task por dia, backfill, rota que
> só soma) vale igual. Ver [Implementação](#implementação-2310).
>
> **D26 desfeita em 26/10 (Heitor):** a Mov. Estoque vai usar tabelas novas
> no Postgres. A implementação abaixo, com o Redis, precisa ser revista.

### O problema

Com a foto diária (D9), o accrual de um dia exige ler a foto inteira daquele
dia na view por parcela (~35 mi de linhas). Um período de 2 anos tem ~500
fotos.

- **Opção (a), calcular na hora com cache no Redis** (como a `/valid/stock`):
  a primeira tela de 2 anos pediria ~500 leituras de foto. Mesmo a menos de
  1 minuto cada, são horas, e nenhuma chamada HTTP espera isso. Com datas
  livres (D6), quase toda combinação de datas seria nova, então o cache
  ajudaria pouco. **Não serve.**
- **Opção (b), consolidação:** um processo em segundo plano calcula cada dia
  **uma vez**, grava o resultado numa tabela pequena no Postgres, e a rota só
  soma linhas. A tela fica rápida porque não toca o Redshift.

### O que já existe na data-lake-api

**[C]** A consolidação do `portfolio` (TS-5244, `arquitetura.md`) já faz
isso para outro dado:

- **Agendador (Celery beat):** a task `dispatch_due` roda a cada minuto e
  decide quem está na hora (`src/infra/celery/tasks.py:33-39`,
  `src/modules/consolidation/business/schedule.py`). Cada fundo tem um horário
  (`start_time` em `consolidation_task_fund`) e é retentado a cada 30 min até
  ter dado novo.
- **Worker:** a task `consolidate_fund` recebe o trabalho pela fila (SQS), lê
  o Redshift e grava no Postgres.
- **Controle:** `consolidation_task` (quais tasks existem),
  `consolidation_task_fund` (quais fundos cada task cobre) e
  `consolidation_run` (cada execução, com status `queued`, `running`,
  `success`, `failed` ou `skipped`, e erro).
- **Publicação sem meio-termo:** o dado novo só passa a valer num commit único
  no fim; se falhar no meio, a rota continua lendo o anterior.
- **Disparo manual e acompanhamento** pelas rotas `/consolidation/*`; limpeza
  diária às 03:00.

### A proposta para a Mov. Estoque

1. **Uma task nova** (ex.: `valid_stock_movement`), registrada em
   `consolidation_task`.
2. **A unidade é o dia, não o fundo.** A view por parcela só é ordenada por
   `data_ref`: ler a foto para um fundo custa o mesmo que para todos. Então
   cada execução lê a foto de um dia uma vez e calcula todos os fundos juntos
   (`GROUP BY` fundo). As tasks atuais são por fundo; esta foge do padrão de
   propósito.
3. **O que grava:** uma linha por fundo e por dia numa tabela nova (ex.:
   `valid_stock_movement_daily`): VP do dia (saldo, D7), aquisições, baixas já
   com o sinal da D5 (e o detalhe por tipo numa tabela filha, se a tela quiser
   abrir), accrual e quantas parcelas ficaram sem taxa. A troca das linhas do
   dia é feita numa transação só.
4. **Quando roda:**
   - todo dia, depois que o lake recebe a foto nova (mesmo agendador, com
     retentativa);
   - **reprocesso:** as views têm `loaded_at`. Se o maior `loaded_at` de um
     dia mudar (administrador reenviou o arquivo), o dia é recalculado;
   - **histórico (backfill):** os ~500 dias de 2 anos, em lotes, fora do
     horário comercial.
5. **A rota:**
   - saldo inicial = VP da última linha antes da Data inicial;
   - soma dos componentes da Data inicial à Data final;
   - estoque real = VP da última linha até a Data final (D13);
   - evolução mensal = soma por mês.

   Só Postgres, sem Redshift.

### Custos e cuidados

- **Tamanho:** ~30 fundos × ~500 dias ≈ 15 mil linhas em 2 anos. Pequeno.
- **Tempo:** **[C]** um dia, todos os fundos, coube em menos de 1 minuto em
  21/10. **[H]** O backfill de 2 anos deve levar poucas horas de worker.
- **Redshift:** as consultas que pararam em 21 e 22/10 bateram no limite de
  60 s do cliente de teste, não em regra do Redshift (corrigido em 23/10). O
  backfill continua indo para fora do horário comercial, combinado com o time
  de dados.
- **Frescor:** a tela mostra até o último dia consolidado. A rota devolve
  essa data, e o front pode exibi-la.
- **Mais peças:** migration, task, monitoramento das runs. Em troca, a tela
  fica rápida e o Redshift é lido uma vez por dia.

## Implementação na poça (26/10, D34)

A movimentação tem uma **consolidação própria** na data-lake-api, dentro do
módulo `src/modules/valid` (o mesmo do dashboard inteiro: um módulo só, pedido
de 26/10), separada da do Chrisgol (TS-5244): nada
do módulo `consolidation` é reaproveitado (código, tabelas, tasks, rotas). Ela
só segue o mesmo modelo: fundo cadastrado com horário, beat a cada minuto, uma
run por fundo na fila, meta D-2, publicação atômica, monitoramento e limpeza.
O que é compartilhado é a infraestrutura da aplicação: conexão do Postgres,
migrations do Alembic, Celery/SQS, sessão do Redshift e calendário de dias
úteis. Substitui o Redis da D26 e a task por dia da D10. O contrato da
`/valid/stock-movement` é o mesmo, então BFF e front ficam como estão.

**O que a run faz** (`src/modules/valid/business/runner.py:207`):
1. Acha a última foto de cada fonte do fundo até a meta (D-2 dias úteis). A
   foto de D-1 fica de fora: a da BGT chega incompleta (P18), e um dia gravado
   só é refeito à mão.
2. Sem foto depois do último dia gravado, a run fica `skipped`; depois das
   12h, se o fundo está atrás da meta, `failed` (é o alerta).
3. Continua da última foto gravada da fonte (ou da primeira foto a partir de
   2 anos atrás, num fundo novo) em **blocos de 31 dias corridos**. Cada bloco
   é uma consulta no Redshift e uma transação no Postgres, que troca os dias
   do bloco e grava o progresso da run.
4. Para em **3 blocos por run** (~3 meses), para o histórico de um fundo novo
   não prender a fila. Enquanto o fundo estiver atrás da meta, o beat volta a
   cada 30 min.
5. A run **manual** refaz os últimos 2 dias gravados de cada fonte (arquivo
   reenviado pelo administrador) e segue em frente.

**Peças (data-lake-api, sem commit):**
- **Tabelas** (`src/infra/postgres/models/valid.py`, migration `0009`):
  `valid_movement_fund` (fundos e horário, soft delete),
  `valid_movement_run` (execuções, com status, progresso e sinal de vida) e
  `valid_stock_movement` (um dia por fundo e fonte; guarda o histórico
  inteiro, e quando a run antiga sai na limpeza o `run_id` fica nulo).
- **Regras** (`business/rules.py`): horário do fundo e retentativas
  (`rules.py:69`), meta D-2 (`rules.py:22`), "tem dia novo".
- **Tasks Celery** (`viewer/tasks.py`): `dispatch_valid_movement` (tick a
  cada minuto), `consolidate_valid_movement` (uma run) e
  `clean_valid_movement` (03:30), com liga/desliga próprio
  (`CFG_VALID_SCHEDULE_ENABLED`; sem valor, liga em produção e local). Mesma
  fila SQS da aplicação.
- **Rotas de controle** em `/valid/movement`: fundos (listar, cadastrar com
  horário, mudar horário, remover), disparo manual (`POST /run`), execuções
  (listar, detalhe, liberar run parada) e `GET /status` (última run e último
  dia gravado de cada fundo).
- **Consulta por fundo** (`src/infra/redshift/queries/plgn/valid.py:214`): a
  de período (P1) com uma linha por dia, a lista de fotos pronta e o fundo
  filtrado. O VP da parcela é somado: parcela repetida na foto entra inteira
  no saldo. Fotos do fundo: `valid.py:43` (última) e `valid.py:54` (lista do
  bloco).
- **Rota da tela** `/valid/stock-movement` lê o Postgres
  (`src/modules/valid/repository.py:91`); o "consolidado até" passou a ser o
  último dia **do fundo**.
- **Configuração** `CFG_VALID_*` (`src/shared/config/__init__.py:191`).
- Saiu: o Redis e a task por dia.

**Validação:**
- **[C]** A consulta por dia, na semana de 16 a 22/10 do Kanastro A, bate
  com a de período nos 5 dias: saldo inicial, aquisições, baixas, accrual e
  estoque real iguais até o centavo, e cada dia abre onde o anterior fecha.
  No Redshift, com fila nesse horário: 14,0 s de execução, contra 11,7 s da
  de período na mesma hora (que levava 5,9 s em 23/10, com o cluster livre).
- **[C]** Testes: 180 passam nos arquivos que não precisam de banco (regras,
  blocos, consulta, rota, liga/desliga do beat e os da master), com a falha
  de arquitetura que já existe na master (`day_cache`). Os 6 testes contra o
  Postgres (blocos até a meta, run manual, run sem dia novo, tick do beat,
  leitura da rota e rotas de controle) foram escritos e ficam pulados aqui:
  não há Postgres neste ambiente. A migration gera o SQL esperado
  (`alembic upgrade 0008:0009 --sql`).

- **[C] Simulação com dados reais, sem gravar nada:**
  [simulate_fund_movement.py](../attachments/simulate_fund_movement.py) roda as
  mesmas consultas e blocos da run, só leitura no Redshift, e monta a
  resposta da `/valid/stock-movement` em memória (sem Postgres). Na semana de
  16 a 22/10 do Kanastro A deu os mesmos números da consulta de período, em
  ~17 s.

**Ajustes de 26/10 (D35, D36 e filtros):**
- **data-lake-api:** um módulo só, `valid`, em pastas (`business/`,
  `repository/`, `viewer/`): a Visão Geral, a rota da tela e a consolidação
  da movimentação. Rotas de controle em `/valid/movement/*`, tasks
  `src.modules.valid.viewer.tasks.*`. Rota nova `GET /valid/stock-movement/dates`
  (primeiro e último dia consolidados do fundo).
- **BFF:** `GET /controllership/valid/stock-movement/dates`, com a mesma
  checagem de fundo do parceiro.
- **Front:**
  - fundo num campo que filtra conforme se digita (`app-combobox`, como em Lotes
    de Liquidação), com "x" que volta à Carteira Consolidada;
  - período num campo só (`app-date-picker range`, como em Formalização), que
    só deixa escolher os dias consolidados; o "x" do período volta ao padrão;
  - barras do waterfall mais largas: entrada nova `barMaxWidth` no `app-chart`
    (padrão continua 28 px; no waterfall, 64 px, nunca mais que 62% do espaço
    da categoria);
  - fundo INTERNAL: Saldo inicial e Estoque real do VP, com o ícone de aviso e
    o tooltip, no waterfall e na evolução mensal (D35).
- **Waterfall como o do protótipo** (`dashboard_fundos.html`): os saldos saem
  do zero; aquisições, baixas e accrual flutuam, cada um começando onde o
  anterior parou (verde soma, vermelho subtrai), e o saldo final calculado
  termina onde o accrual parou; estoque real em dourado; o valor escrito em
  cima de cada barra. Para isso o `app-chart` ganhou `base` (barra flutuante:
  tooltip e exportação mostram o passo) e `labels` por série, com spec e
  exemplo na vitrine. A evolução mensal ficou como estava.
- **Carteira Consolidada (D37):** a mesma visão do fundo INTERNAL, com o aviso
  próprio.
- **Mock:** um quinto fundo fictício, administradora INTERNAL, com estoque
  próprio (o mock passou a responder o estoque por fundo quando tem); os
  dias fictícios da poça nos dados fixos.
- **[C] Testes:** data-lake-api, 272 nos arquivos sem banco (mais a falha do
  `day_cache` da master); BFF, 1795 unitários; front, 487 do mock, do gráfico,
  da vitrine e da controllership, lint e check-patterns limpos. Conferido na
  tela (modo mock): fundo com movimentação, fundo INTERNAL com o tooltip e a
  carteira consolidada.

- **Ver o front com a poça simulada, sem BFF, Azure nem tabela:** o mock do
  portal calcula a Mov. Estoque a partir de uma lista de dias
  (`core/http/mock-api/mock-api.pdd.ts`, sem dado real no repositório);
  [pool_to_mock.py](../attachments/pool_to_mock.py) transforma o CSV num script
  que grava essa lista só no `localStorage` do navegador. Conferido em 26/10
  com a semana de 16 a 22/10: Kanastro A com o período preso aos dias
  consolidados e os mesmos números da simulação.
- **Poça fictícia (o caminho preferido, sem dado real):**
  [generate_fake_pool.py](../attachments/generate_fake_pool.py) gera o mesmo CSV
  com os quatro fundos fictícios do mock, de 01/07 a 22/10/2026, fechando a
  conta da conferência dia a dia; carregar com `pool_to_mock.py
  --manter-fundos`. Conferido em 26/10 na tela (último mês e evolução
  mensal).
- **Mock do front já com a poça fictícia:** os dias fictícios de 03/08 a
  22/10/2026 entraram em `.ai/scripts/smoke-data/controllership.json`
  (`controllership/valid/stock-movement/days`): o `start:mock` abre a Mov.
  Estoque calculada, sem colar nada no console. O smoke segue com as respostas
  fixas. Os arquivos com dados reais da simulação foram apagados em 26/10.

**Para colocar em produção (ordem):**
1. Rodar os testes no devcontainer, com o Postgres na `0009`
   (`alembic upgrade head`).
2. Teste de custo com o time de dados: um bloco de um mês do maior fundo (QY
   A, 15,6 mi de parcelas) e um dia novo de todos os fundos.
3. Deploy com a migration.
4. Cadastrar os fundos de administrador com horário
   (`POST /valid/movement/funds`).
5. Acompanhar `GET /valid/movement/status`. **[H]** O histórico de 2 anos
   são ~24 blocos por fundo: ~8 runs, ~12 min de Redshift num fundo do
   tamanho do Kanastro A, ~5 h somando os fundos, espalhadas pelas janelas do
   beat em 1 ou 2 dias. Depois, cada dia novo leva ~6 s por fundo, ~2 a 3 min
   para todos.

**Pendente / cuidados:**
- A fila SQS e o worker (concorrência 1) são os mesmos da consolidação do
  portfolio: as runs das duas esperam umas pelas outras. Uma fila própria
  pede infraestrutura nova (fila e worker).
- Numeração da migration: a Rating/Migração (D22) também vai criar tabelas;
  quem entrar depois troca o `down_revision`.

## Implementação (23/10)

> **Armazenamento e agendamento revistos pela D34 (26/10):** ver
> [Implementação na poça](#implementação-na-poça-2610-d34). O resto (rota, BFF,
> front) vale como está.

Branches criadas a partir da `master` (último `origin/master` conhecido: o
`fetch` falhou por falta de acesso ao remoto neste ambiente), sem upstream e
**sem commit**:

| Repositório | Branch |
|---|---|
| data-lake-api | `feature/TS-5441-pdd-mov-estoque` (era `feature/TS-4815-pdd-mov-estoque` até 28/10) |
| apl-credit-whitelabel-api (BFF) | `feature/TS-5441-pdd-mov-estoque` (era `feature/TS-5044-pdd-mov-estoque` até 28/10) |
| apl-credit-whitelabel (front) | `feature/TS-5441-pdd-mov-estoque` (era `feature/TS-4366-pdd-mov-estoque` até 28/10), aberta na cópia `~/projects/.worktrees/apl-credit-whitelabel-mov-estoque` |

**data-lake-api** (revisto pela D26 em 23/10: sem tabelas novas; **a D26 foi
desfeita em 26/10**, tabelas novas no Postgres liberadas):
- **Consolidação diária da movimentação**, em
  `src/modules/consolidation/business/valid_movement.py`:
  - tasks `dispatch_valid_movement` (beat a cada 30 min) e
    `consolidate_valid_movement_day` (um dia, todos os fundos);
  - consulta em `src/infra/redshift/queries/plgn/valid.py`, que é a
    [consulta por intervalo](../attachments/sql/movement_by_interval.sql).
- **Resultado no Redis** (`src/modules/consolidation/repository/valid_movement_store.py`),
  sem TTL:
  - `valid:movement:v1:day:<data>`: as linhas do dia;
  - `valid:movement:v1:days`: hash com o estado de cada dia;
  - `valid:movement:v1:lock:<data>`: trava de fila, que expira sozinha se o
    worker morrer;
  - `valid:movement:v1:funds`: os fundos com movimentação.
- **Leitura em `src/modules/valid`:**
  - rota nova `/valid/stock-movement`, que soma os dias do Redis;
  - `/valid/stock` com o mesmo formato, lendo o Redshift na hora com cache
    (prefixo `v2`), agora pela `administradores_estoque_contrato` (D7) e com a
    regra da D8 em `select_stock_sources`.
- **Escolhas da implementação, a confirmar:**
  - **Reprocesso por janela:** os 2 últimos dias úteis são refeitos uma vez por
    dia, em vez de olhar o `loaded_at` (detalhe da D10).
  - **`CFG_VALID_SCHEDULE_ENABLED` desligada por padrão:** o beat só agenda
    depois do teste de custo com o time de dados.
  - **Ritmo do backfill:** histórico das 20h às 6h, até 3 dias na fila, nova
    tentativa de dia falho depois de 60 min, foto anterior procurada até 10
    dias úteis para trás. Tudo configurável (`CFG_VALID_*`).
  - **Fundo duplicado sob outro administrador** (o Fydd sob a Dayvale, P5):
    vale a fonte com mais dias.
  - **Sinal das baixas (D5):** `installment_payment_reversal` e
    `installment_partial_refund` −1; `installment_reactivation` ignorado.
- **Testes:**
  - 72 passam, entre eles o armazenamento no Redis com um Redis em memória e o
    runner com dublês.
  - O pre-commit do repositório usa black 24.8.0 e ruff 0.6.9 (não o black 26
    do `requirements.txt`): os arquivos estão limpos nessas versões.
  - `test_arch::test_shared_utils_boundaries` já falhava na `master`
    (`day_cache.py`).

**BFF:**
- Rota `GET /controllership/valid/stock-movement`, com o contrato da D11 e 422
  para Data inicial depois da final.
- **Acréscimo:** checagem do escopo do parceiro, exigida pelo
  `test_arch_partner_scope`. A organização interna vê qualquer fundo; o
  parceiro, só os seus, e recebe 403 fora deles.
- 1.808 testes passam. Um teste de outro módulo (`cerc_reconciliation`) é
  instável e falha às vezes também sem a mudança.

**Front:**
- `getStockMovement` no serviço.
- **Aba Mov. Estoque:**
  - Período padrão: o último mês até a data de referência (D27; Data final
    na referência pela D13). A movimentação sai junto com o estoque.
  - Aviso da D24 na carteira consolidada e para `available: false`.
  - Waterfall com os valores reais e a pílula da diferença: vermelha a partir
    de 1%, amarela a partir de 0,3%.
  - Nota explicando o resultado nas baixas (D3), evolução mensal e "dados
    consolidados até".
- **Waterfall com barras a partir do zero:** o `app-chart` não tem barra
  flutuante, e criar uma é mudança em componente comum, que pede um pedido
  explícito.
- Mock do `start:mock` e spec do `pdd-stock`, que saiu da lista de legado sem
  spec.
- 306 testes da controllership passam. A suíte inteira não rodou aqui por
  falta de memória; o lint dos arquivos alterados está limpo.

**Para colocar em produção (ordem):**
1. Fazer o teste de custo da consulta por intervalo, com todos os fundos num
   par de dias, fora do horário comercial e com o time de dados.
2. Ligar `CFG_VALID_SCHEDULE_ENABLED` e acompanhar o hash
   `valid:movement:v1:days` até o backfill terminar.
3. Confirmar com a infraestrutura a política de memória do Redis: com
   `allkeys-*`, as chaves sem TTL também podem ser removidas. Com
   `volatile-*` ou `noeviction`, não.

Até o passo 2 terminar, a Mov. Estoque responde `available: false` nos dias
ainda não consolidados. A Visão Geral e o Histórico mudam no deploy (D7 e D8),
sem depender da consolidação.

**Não feito / pendente:**
- **Testes que dependem de ambiente:** rodar a suíte inteira do front (`.ai/scripts/validate.sh`) e o smoke
  da tela, em claro e escuro.
- **Disparo manual:** a data-lake-api não tem rota para reprocessar um dia da
  Mov. Estoque; hoje isso é só pelo Celery ou apagando o estado do dia no
  Redis.
- **Dias faltando:** um dia que falta no consolidado quebra a corrente, e a
  diferença dele aparece em `difference` sem estar em nenhuma das duas partes.

## Otimização da consulta (23/10)

O perfil da execução de todos os fundos numa semana (166 s) mostrou o custo em
agregações gravando em disco (193 GB), redistribuição entre nós (66 GB), uma
CTE lida duas vezes e gravada em área temporária (33 GB) e uma junção em laço
(o `data_ref > anterior AND data_ref <= foto`).

**[C]** Medido com fundos filtrados, cache de resultado desligado, mesmos
resultados até o centavo:

| Consulta | Escopo | Antes | Depois | O que mudou |
|---|---|---|---|---|
| Intervalo de um dia (worker) | QY A, 15,6 mi de parcelas | 14,9 s | **7,7 s** | parcela como número de 64 bits (`FNV_HASH`) e marcadores de presença |
| Intervalo de um dia | Kanastro A, 5,9 mi | 6,9 s | 5,9 s | idem |
| Período (semana) | Kanastro A | 24,3 s | **5,9 s** | P1: uma leitura por foto com os dois papéis por junção pequena, chave numérica, fluxos mapeados por junção pequena |
| Período (mês) | Kanastro A | — | 33,7 s | P1 com a lista de fotos pronta |

- A consulta do worker (`GET_STOCK_MOVEMENT`) passou a ser a versão do
  intervalo otimizada.
- A versão de período fica no gerador `attachments/generate_period_movement.py`,
  que recebe a lista de fotos pronta (calendário B3). Descobrir as datas dentro
  da consulta a deixa ~2× mais lenta, porque o Redshift refaz a leitura a cada
  uso da CTE.
- **Testadas e descartadas:**
  - função de janela (`LAG`/`LEAD` por parcela): 17,3 s na semana, ordenação
    cara;
  - agrupar por fonte, CNPJ e parcela em texto: 13,9 s na QY;
  - traduzir a chave do fundo por uma tabela à parte: sem disco, mas no mesmo
    tempo, por causa da leitura extra.
  - **[H]** levar as fotos para o Python e parear lá (avaliado em 23/10, sem
    medir): um mês do Kanastro A são ~130 mi de linhas (22 fotos × 5,9 mi)
    saindo por uma conexão só, pelo nó líder; só a transferência levaria
    minutos, contra ~34 s da consulta inteira, e a memória iria a vários GB. No
    worker, cada dia seriam ~74 mi de linhas (duas fotos de todos os fundos). O
    pareamento fica no Redshift, que o faz em paralelo junto dos dados; o
    Python só soma o que já vem pequeno (os dias consolidados).
- **[H] 2 anos de um fundo na hora:** ≥ 12 a 15 min no Kanastro (~1,5 s por
  intervalo). Calcular sob demanda continua inviável para a tela; a
  consolidação diária segue necessária.
- **Na tela, trocar o fundo leva ~0,5 a 1 s** com a consolidação: a
  movimentação sai do Redis (32 ms de CPU para 2 anos) e o estoque, do cache
  (203 ms). Só o cache frio do estoque, uma vez por dia, vai ao Redshift (não
  medido). Ver a [evidência](../evidence/stock-movement-redshift-2026-10-21.md#tempo-da-tela-ao-trocar-o-fundo-23102026).
- **[C] Nulo e colisão:** `FNV_HASH` de nulo é nulo (testado no lake em
  23/10), então parcela sem id não casa entre as fotos, como antes. Duas
  parcelas com o mesmo número são improváveis (~1 em 20 mil numa foto de 40 mi
  de parcelas, pela conta do paradoxo do aniversário) e o erro ficaria no VP
  das duas.
- **Falta medir com todos os fundos** (o caso do worker); a v2 deve ganhar mais
  lá, onde a tabela da junção é maior.
- **O que mais ajudaria, e depende do time de dados:**
  - ordenar a tabela física por trás da `administradores_estoque` também por
    fonte e fundo (sortkey composta `data_ref, source, cnpj_classe`): a
    leitura de um fundo ficaria bem mais barata;
  - distribuir por `id_parcela`: as duas fotos não precisariam cruzar a rede
    na junção.

## Contrato proposto (D11)

Rota nova decidida em 23/10 (D11); este contrato é a base, com detalhes
ajustáveis na implementação. Rota na data-lake-api, repassada
pelo BFF em `controllership/valid` (o router já exige `pdd:read`):

```
GET /valid/stock-movement?fund_legal_id=...&start_date=AAAA-MM-DD&end_date=AAAA-MM-DD
```

Resposta (números do Fydd A em set/26):

```json
{
  "fund_legal_id": "…",
  "admin": "…",
  "available": true,
  "opening_date": "2026-08-31",
  "closing_date": "2026-09-30",
  "last_consolidated_date": "2026-10-21",
  "opening_balance": 150125544.92,
  "acquisitions": 8601131.06,
  "liquidations": 8111578.04,
  "interest_accrual": 1282827.48,
  "closing_balance": 155507736.92,
  "calculated_closing_balance": 151897925.42,
  "difference": 3609811.50,
  "difference_on_entries": 1600754.30,
  "difference_on_exits": 2009057.20,
  "months": [
    { "month": "2026-09", "opening_balance": 0, "acquisitions": 0, "liquidations": 0,
      "interest_accrual": 0, "closing_balance": 0 }
  ]
}
```

- **`opening_date` e `closing_date`:** as fotos usadas de fato (D13). Podem
  diferir das datas pedidas por fim de semana, feriado ou dia ainda não
  consolidado.
- **Conta da conferência pronta na API** (`calculated_closing_balance`,
  `difference` e as duas parcelas), para a regra ficar num lugar só.
- **Fundo sem movimentação** (só-INTERNAL): `200` com `"available": false` e
  um motivo, não 404. O 404 da `/valid/stock` significa "fundo não
  encontrado", e a tela mostraria erro em vez do aviso da D24.
- **Carteira consolidada:** o front não chama a rota; mostra o aviso da D24.
- **Meses cortados pelo período** somam só os dias dentro dele.

## Plano de implementação (proposta)

Decisões tomadas; a D8 ainda vai ser validada com a controladoria. Contrato novo muda nas três pontas no mesmo
ciclo.

1. **data-lake-api**
   - Consolidação (D10), como em [D10 em detalhe](#d10-em-detalhe-consolidação-diária):
     uma execução por dia (D23) roda a
     [consulta única](../attachments/sql/movement_by_interval.sql) e grava uma
     linha por fundo e intervalo; reprocesso pelo `loaded_at`.
   - Backfill dos 2 anos em lotes; depois, só o intervalo novo e os
     reprocessados.
   - Mapa de sinal (D5) no código, passado à consulta como listas de tipos.
   - Rota (D11) que soma os dias do período, com testes.
   - **Visão Geral e Histórico (D7, D25):** task diária própria que lê a
     `plgn.administradores_estoque_contrato` (no lugar da `plgn.estoque_contrato`
     de `src/infra/redshift/queries/plgn/valid.py:22`) e grava por fonte, fundo
     e dia. A rota `/valid/stock` passa a ler o Postgres, aplica a regra da D8
     e devolve o mesmo formato de hoje: BFF e front não mudam. Backfill de 2
     anos em poucas consultas.
2. **BFF:** rota em `controllership/valid` (o router já exige `pdd:read`),
   consolidando por fundo e por carteira como a `get_stock`; schemas.
3. **Front:**
   - `data-access/pdd`: interface e serviço novos.
   - Estoque real pela Data final (D13).
   - `buildWaterfallChart` com os valores reais, o saldo final calculado e a
     conferência no subtítulo; a evolução mensal com três séries.
   - O texto da conferência explica que a diferença inclui o resultado nas
     baixas (D3).
   - Specs de comportamento, regras do `.ai/` do front.

### D8 provisória: o que muda no código se mudar

A D8 está provisoriamente na opção **(b)** (23/10; passou por (a) no mesmo
dia). Ainda vai ser validada com a controladoria.

**Como fica cada aba:**

| Escopo | Visão Geral e Histórico | Mov. Estoque |
|---|---|---|
| Fundo de administrador | sim | sim |
| Fundo que vem pela INTERNAL e por um administrador (4) | sim, com o número do administrador | sim |
| Fundo só-INTERNAL (10) | sim, com o número da INTERNAL | **não**: não tem aquisição nem liquidação |
| Carteira Consolidada | sim, com todos os fundos | **não, por enquanto** |

**Para que uma mudança custe pouco:**

- **A regra fica num ponto só:** uma função na data-lake-api que escolhe, por
  fundo e data, de qual fonte vem o estoque da `get_stock` (administrador
  primeiro, INTERNAL só se não houver outro). Com a D25, a consolidação grava
  todas as fontes e a função age na leitura do Postgres: mudar a D8 não exige
  recalcular nada. BFF e front não repetem essa lógica.
- **O front não testa "INTERNAL".** A aba Mov. Estoque decide pela resposta da
  rota dela: carteira consolidada ou fundo sem movimentação mostram o aviso da
  D24. Se a regra mudar, o front não muda.
- **A rota da Mov. Estoque é por fundo** (D11): por enquanto não há total
  consolidado. A consulta por intervalo continua calculando todos os fundos de
  administrador; a view por parcela não tem INTERNAL.
- **O que mudaria em cada opção:**

  | Opção | data-lake-api (`get_stock`) | Mov. Estoque |
  |---|---|---|
  | **(b) atual** | descarta a linha INTERNAL quando o CNPJ também vem por um administrador | só fundo de administrador; consolidado escondido |
  | (a) excluir | descarta toda linha INTERNAL | consolidado pode voltar: bateria com a Visão Geral (exceto ~0,5% da BGT) |
  | (c) como hoje | não descarta nada | contagem dupla nos 4 fundos repetidos |

- **Lista de fundos do filtro:** **[C]** vem da platform-cessao
  (`src/shared/repository/funds.py:26`, BFF), não do lake. Com a (b), os fundos
  só-INTERNAL têm estoque, então a `get_stock` responde normalmente para eles.

**Se um dia o consolidado da Mov. Estoque voltar com a (b)**, ele não bateria
com a Visão Geral: em 30/09, ~R$ 4,88 bi de movimentação contra ~R$ 15,88 bi de
VP (~31%). Formas de apresentar nesse caso: aviso com a ponte entre os números,
ou barra "variação sem detalhe" para os fundos só-INTERNAL.

## Validação

- Fydd A em set/26, num intervalo só (31/08 → 30/09): 150,13 / 8,60 / 8,11 /
  1,28 / 155,51, conferência 3,61 = (10,20 − 8,60) + (8,11 − 6,10).
  **[C]** já reproduzido em 22/10.
- Encadeado por dia, o accrual de setembro do Fydd A deve ficar acima de 1,28,
  porque as parcelas novas e as que saíram passam a contar enquanto estão no
  estoque **[H]**.
- Encadeamento: o estoque real de um intervalo é igual ao saldo inicial do
  seguinte, e a soma dos intervalos de 01/09 a 30/09 é igual à soma de 01/09 a
  15/09 com 16/09 a 30/09.
- Fundo com conferência acima de 1%: rodar a
  [conferência por parcela](../attachments/sql/reconciliation_by_installment.sql) no mês.

## Pendências

- **Integração TS-5442 (`feature/TS-5442-pdd-integracao`, 28/10), em andamento:**
  - BFF pronto: merge da Rating (`b031ae6`), merge da Mov. Estoque (`fde9bc3`; rotas da
    movimentação com o escopo `pdd-stock-movement`) e escopos novos `pdd-rating-opening` e
    `pdd-migration-analysis` (`44d0427`). 2493 testes passam.
  - Front: merges da Rating (`71b049dd`) e da Mov. Estoque (`184df4b4`). Build ok, lint e
    check-patterns limpos, 645 de 646 specs; o `chart-export.spec` falha às vezes (instável, falha
    também na TS-5441 pura). **Falta:** escopos novos nas abas Rating e Migração (`pdd.permissions`
    e `PDD_TABS`); filtros de produto das duas abas como combobox; data de referência delas só
    com os dias que têm dados, como na Mov. Estoque.
  - data-lake-api pronta: merge da Rating (`8ba37a2`, migration `0010`), merge da Mov. Estoque
    (`28cbdd7`, migration `0011`; nomes repetidos das regras ficam com a Rating no pacote
    `business`) e a Rating passou a achar buracos pelos dias lidos, com a regra da movimentação
    (`1d5a156`). 358 testes passam; só o `test_arch` do `day_cache` falha, como na master.
- **Carga da poça pela D58: implementada em 28/10** (data-lake-api, branch
  `feature/TS-5441-pdd-mov-estoque`, 8 commits de `36542c8` a `9a6a158`).
  Como ficou:
  - **Agendamento:** uma execução por dia para todos os fundos, no horário de
    `CFG_VALID_MOVEMENT_RUN_AT` (Brasília). O beat só agenda com
    `CFG_VALID_MOVEMENT_SCHEDULE_ENABLED=true`, desligado por padrão em todo
    ambiente. Antes, o agendamento da D34 ligava sozinho em produção e em
    LOCAL.
  - **Dias de cada execução:** como na Rating. A primeira lê do mesmo dia do
    mês anterior até hoje. As seguintes leem o mês anterior ao dia mais antigo
    lido, os dias novos e os 5 mais recentes, até 01/01/2026. Um registro dos
    dias lidos (`valid_movement_day`) inclui fim de semana e feriado. Diferente
    da Rating, os dias que faltam entre o mais antigo e hoje também entram, que
    é o buraco deixado por uma execução interrompida.
  - **Leitura:** as fotos de todos os fundos são listadas uma vez por trecho de
    dias seguidos, mais 10 dias antes, para achar a foto que abre o primeiro
    intervalo. Os blocos têm 7 dias corridos e vão do mais novo para o mais
    antigo. Em cada bloco, uma consulta por fundo e fonte, com a fonte escolhida
    no próprio bloco (P5, P6). O bloco troca os dias de todos os fundos numa
    transação. Bloco que falha derruba a execução, que é tentada de novo em
    30 min.
  - **Reprocesso à mão:** task `reprocess_valid_movement(início, fim)`, só
    dentro dos dias já lidos (foto atrasada além de 5 dias, recarga
    retroativa como a do P23).
  - **O que saiu:** o cadastro de fundos (`valid_movement_fund`), as rotas
    `/valid/movement/*`, a meta D-2, os blocos de 31 dias até 3 por execução e
    a limpeza diária.
  - **Testes:** 48 passam (regras, runner com dublês, rota). Os 3 contra o
    Postgres ficam para o devcontainer.
- **Antes de ligar a carga:**
  - Teste de custo com o time de dados: um mês de todos os fundos deve levar
    uns 10 a 15 min por execução.
  - Na branch que junta com a Rating: as duas migrations são `0009` sobre a
    `0008`, então uma vira `0010`. O horário da Mov. Estoque fica depois do
    da Rating.
  - Fundo sem foto por mais de 10 dias recomeça a sequência: o intervalo que
    atravessa a falta não é gravado.
- **Validar a D8 com a controladoria** (como apresentar os fundos da INTERNAL).
  Pode mudar a regra e o que está em
  [D8 provisória](#d8-provisória-o-que-muda-no-código-se-mudar).
- Teste de custo da consulta única com todos os fundos num par de fotos (fora
  do horário comercial, com o time de dados), para dimensionar a execução
  diária e o backfill. Se o Redshift abortar, revisitar a D23.
- Conferir se o `id_parcela` da liquidação casa com o do estoque em todos os
  administradores.
- Conferir que nenhuma parcela se repete dentro da mesma foto (a junção
  multiplicaria as linhas); rodar junto com o teste de custo.
- Problemas de dado em [data-problems.md](../data-problems.md). Os
  de taxa (P7, P8, P10) não afetam mais o accrual (D15).

## Histórico

- **21/10/2026:**
  - Mapeamento do código nas três pontas e perfil das views
    `administradores_*` no lake.
  - Reconciliação de set/26 por fundo; testes de roll-forward por parcela e de
    taxa × prazo.
  - D1 a D4 tomadas (Heitor).
- **22/10/2026:**
  - Pasta de acompanhamento criada; conferência esperada de set/26 registrada.
  - D5 (mapa de sinal no código), D6 (qualquer par de datas), D9 (foto
    diária) e D12 (taxas como vêm, correção com o time de dados) tomadas
    (Heitor). D10 revista para a consolidação; D13 aberta (pontas do período).
  - [concepts.md](../concepts.md) criado.
  - D13 tomada pela opção (a). Medido no Fydd A: accrual com a taxa do
    recebível −0,3%, com a de cessão −1,7%. D14 aberta (regra da taxa por
    administrador, a confirmar). D10 detalhada (task por dia). Consultas de
    Genius e Dayvale paradas no limite de 60 s do cliente de teste (visto em
    23/10); não repetidas.
  - Pergunta sobre o custo do roll-forward diário: `EXPLAIN` mostra duas
    fotos redistribuídas (`DS_DIST_BOTH`) contra uma leitura simples da
    fórmula. D15 aberta, com teste de custo antes.
  - Pergunta sobre comparar só a Data inicial com a final: serve para período
    curto, falha em período longo (exemplo de um ano: −33%). Entrou na D15
    como opção (c), com o encadeamento mensal como (d).
  - Proposta do Heitor (pontas no waterfall, meses na tabela): ajuste sugerido
    para o waterfall somar os meses, ou seja, (d) com meses fechados. Escolha
    entre (d) e (b) em aberto.
  - Complemento (coorte fixa na Data inicial para todos os meses): deixa de
    fora as parcelas compradas no período; sugerida a (d) com cada mês pelas
    parcelas do início do mês, e a coorte como visão à parte. Aguardando
    confirmação.
  - Pergunta sobre usar o VP diário da `get_stock`: não serve para o accrual
    (é soma por fundo; vira a conta pela sobra); serve para saldo e estoque.
  - **D15 tomada (Heitor):** accrual por roll-forward. Pedido de trazer estoque
    e accrual numa consulta só: criada a
    [consulta por intervalo](../attachments/sql/movement_by_interval.sql),
    testada no Fydd A (reproduz set/26). D14 dispensada; D7 revista (saldo e
    estoque da Mov. Estoque pela mesma consulta); D23 aberta (dia × mês).
- **23/10/2026:** D23 tomada (Heitor): intervalo de dia. O teste de custo
  segue como pré-requisito para dimensionar a execução diária e o backfill.
- **23/10/2026:** pergunta sobre fazer o roll-forward por contrato. Medido no
  Kanastro A (set/26): por contrato o accrual vira 58,78 contra 54,80 por
  parcela, misturando aquisição em contrato existente (+16,32) e resultado de
  baixa (−12,34). Heitor confirmou: fica por parcela (D15). Por contrato fica
  como alternativa se o teste de custo falhar.
- **23/10/2026:** D7 tomada (Heitor): a `get_stock` passa a ler
  `administradores_estoque_contrato`. Mov. Estoque segue com saldo e estoque
  da consulta por intervalo.
- **23/10/2026:** D8 tomada como **provisória** (Heitor): opção (b), a validar
  com a controladoria; a regra fica isolada num ponto da data-lake-api para
  mudar barato.
- **23/10/2026:** com a D8 (b), o consolidado da Mov. Estoque (~R$ 4,88 bi em
  30/09) não bate com o da Visão Geral (~R$ 15,88 bi). Duas formas de
  apresentar registradas, a levar à controladoria junto com a D8.
- **23/10/2026:** D8 provisória revista (Heitor): de (b) para (a), descartar a
  INTERNAL do dashboard. Consolidado da Mov. Estoque passa a bater com a Visão
  Geral; carteira consolidada cai para ~R$ 4,88 bi (30/09). Ponto aberto: fundos
  só-INTERNAL na lista do filtro.
- **23/10/2026:** D8 provisória de volta à (b) (Heitor). Visão Geral e
  Histórico para todos os fundos; Mov. Estoque só para fundo de administrador,
  sem carteira consolidada por enquanto. D24 aberta (aviso ou aba escondida).
- **23/10/2026:** D10 tomada (Heitor): consolidação Celery → Postgres, task
  por dia, backfill combinado com o time de dados.
- **23/10/2026:** D25 tomada (Heitor): Visão Geral e Histórico também
  calculados antes e guardados, em task própria; gravados por fonte para a D8
  ser aplicada na leitura; rota `/valid/stock` com o mesmo formato.
- **23/10/2026:** contrato da rota nova proposto (D11), aguardando confirmação.
- **23/10/2026:** D11 tomada (Heitor): rota nova `/valid/stock-movement`, com
  o contrato proposto como base.
- **23/10/2026:** D24 tomada (Heitor): aba visível com aviso. Todas as
  decisões da Mov. Estoque tomadas; implementação aguarda liberação do Heitor.
- **23/10/2026:** implementação nas três branches (sem commit, sem query no
  Redshift). Chaves de agendamento e de leitura pelo Postgres desligadas por
  padrão; reprocesso por janela no lugar do `loaded_at` (a confirmar).
- **23/10/2026:** D26 tomada (Heitor): sem tabelas novas. Movimentação no
  Redis; Visão Geral e Histórico de volta ao Redshift com cache (D25 desfeita).
  Código refeito: tabelas, migration e modelos removidos.
- **23/10/2026:** consulta otimizada. Intervalo do worker 2× mais rápido num
  fundo grande e período 4× mais rápido, com os mesmos resultados. Anexos
  atualizados; um anexo de simulação com nome real de administrador e CNPJ foi
  removido (sigilo).
- **23/10/2026:** D27 (Heitor): período padrão da Mov. Estoque passa a ser o
  último mês até a data de referência. Front ajustado; 44 testes da tela de
  PDD passam, lint e check-patterns limpos.
- **26/10/2026:** D26 desfeita (Heitor): tabelas novas no Postgres liberadas;
  a Mov. Estoque vai usar tabelas novas. Volta a valer a D10 (resultado por
  fundo e dia no Postgres); a parte da implementação que grava no Redis
  precisa ser revista.
- **26/10/2026:** D34 (Heitor): movimentação na "poça" do Postgres, por fundo,
  no modelo de consolidação do Chrisgol. data-lake-api refeita sem commit:
  task `valid_stock_movement`, tabela e migration `0009`, consulta por fundo
  em blocos, rota lendo o Postgres; Redis removido. Consulta por dia validada
  contra a de período na semana de 16 a 22/10 do Kanastro A.
- **26/10/2026:** D34 revista (Heitor): consolidação separada da do
  Chrisgol, só no mesmo modelo. Módulo próprio com tabelas, tasks,
  regras e rotas próprios; o módulo `consolidation` voltou ao estado da
  master.
- **26/10/2026:** D35 e D36 (Heitor). Um módulo só (`valid`) na data-lake-api;
  rota das datas consolidadas nas três pontas; filtros do front (fundo com
  busca e "x", período único limitado aos dias consolidados), barras mais
  largas e a visão do fundo INTERNAL. Simulação da semana de 16 a 22/10 de
  todos os fundos (ver a evidência).
- **26/10/2026:** D37 (Heitor): carteira consolidada com a visão do fundo
  INTERNAL. Waterfall flutuante como o do protótipo; fundo INTERNAL fictício
  no mock do front.
- **28/10/2026:**
  - Carga da poça da Mov. Estoque refeita pela D58, no mesmo desenho da
    Abertura de Rating: execução diária com horário e liga/desliga por
    variável de ambiente, registro dos dias lidos, blocos do mais novo para o
    mais antigo e reprocesso à mão. Saem o cadastro de fundos e as rotas de
    controle da D34.
  - Data-lake-api: branch renomeada para `feature/TS-5441-pdd-mov-estoque`
    (tarefa nova da Mov. Estoque) e 8 commits, de `36542c8` a `9a6a158`. Os
    hooks do repositório rodaram; o `test-arch` foi pulado porque já falha na
    master (`day_cache` importa o Redis). Front e BFF seguem sem commit.
  - Front e BFF: branches renomeadas para `feature/TS-5441-pdd-mov-estoque`.
    Front com 4 commits, de `5ac64d7e` a `31d831ea`, na cópia
    `.worktrees/apl-credit-whitelabel-mov-estoque`; cada commit compila sozinho.
    BFF com 2 commits, `a84d26c` e `c8efd9c`, com todos os hooks.
  - Front: às 23:39 de 27/10, o stash da Mov. Estoque tinha sido aplicado por
    engano no checkout principal, em cima da branch da Rating (6 arquivos em
    conflito). A mistura foi guardada num stash marcado "DESCARTÁVEL" e a
    branch da Rating voltou limpa. Os stashes antigos da Mov. Estoque (um em
    cada repositório) e o descartável podem ser apagados quando quiser.
- **29/10/2026:** validação da `feature/TS-5442-pdd-integracao` para produção. Passam:
  data-lake-api 368 (só o `test_arch` do `day_cache`, que já falha na master), BFF 2521, front
  com build, 5017 specs e audit sem vulnerabilidade. Os lints acusam só erros antigos ou o
  protótipo local. Rotas e nomes de campo (ECL) batem nas três pontas, e as migrations ficam
  `0009 → 0010 → 0011`. Para produção: enviar os commits locais (front 3, BFF 2); aplicar as
  migrations (`RUN_MIGRATIONS=1`); ligar as cargas diárias (`CFG_VALID_PDD_*` e
  `CFG_VALID_MOVEMENT_*`); atribuir os escopos `pdd-rating-opening` e
  `pdd-migration-analysis` aos grupos. Os testes contra Postgres não rodaram aqui.

- **30/10/2026:** conferência no Datadog do deploy de produção de 29/10 (versão
  `prod-219c8f3`, às 16:04 de Brasília). **[C]** O job de migration aplicou
  `0009 → 0010` e `0010 → 0011` às 16:04; o worker registrou as seis tasks do
  módulo `valid`. **[C]** As cargas diárias **não rodaram** às 19h: o beat de
  produção subiu às 16:05, não reiniciou depois e, até 09:10 de 30/10, só
  enviou `consolidation.dispatch_due` (a cada minuto), `clean_consolidation`
  e `celery.backend_cleanup`; nenhum `dispatch_valid_pdd` ou
  `dispatch_valid_movement` foi enviado ou recebido em nenhum ambiente. O
  beat só agenda essas tasks com `CFG_VALID_PDD_SCHEDULE_ENABLED=true` e
  `CFG_VALID_MOVEMENT_SCHEDULE_ENABLED=true` no ambiente do próprio beat
  (`src/infra/celery/tasks.py:19-20`); o horário (`CFG_VALID_*_RUN_AT`) é
  lido pelo worker (`pdd_runner.py:73`, `movement_runner.py:83`). **[H]** As
  variáveis não chegaram ao container do beat (ou o beat não foi reiniciado
  depois de definidas); validar nas variáveis do deploy. Os timeouts de
  Postgres vistos de 19:01 de 29/10 a 08:04 de 30/10 são só do staging; a
  produção não teve erro de `dispatch_due`.
- **30/10/2026 (2):** ligação das cargas diárias preparada no repositório do
  ArgoCD da data-lake-api, branch `feature/TS-5442-pdd-cargas-diarias`, sem
  commit: `CFG_VALID_PDD_*` e `CFG_VALID_MOVEMENT_*` (`SCHEDULE_ENABLED=true`,
  `RUN_AT=19:00`) no `env` do worker e do beat de `asgard-production`. **[C]**
  O `entrypoint.sh` exporta as variáveis do Guardian depois das do container:
  se o Guardian também as definir, vale a dele. O horário é `HH:MM` com dois
  dígitos e sem fuso (com fuso, a comparação com a hora de Brasília quebra o
  dispatch); valor vazio impede a configuração de carregar.
- **30/10/2026 (3):** rotas para disparar à mão a execução diária, na
  data-lake-api, sem commit (pedido do Heitor): `POST /valid/pdd/run` e
  `POST /valid/stock-movement/run`, 202 com `run_id` e os dias da run, 409 com
  uma run na fila ou rodando. A run à mão (`trigger = manual`) lê os mesmos
  dias que a do horário leria naquele momento, não depende de `RUN_AT` nem de
  `SCHEDULE_ENABLED` e não conta como a do dia: a do horário ainda roda e lê
  mais um mês, então cada disparo adianta um mês da carga do histórico. Sem
  migration (o `manual` já era aceito). Escolhas a confirmar [H]: rota sem
  trava de config (como a `/consolidation/tasks/{task}/run`) e run à mão fora
  da conta do dia. Testes com dublês: 21 dos runners e das rotas passam.
- **30/10/2026 (4): erro na carga da Mov. Estoque achado rodando a
  data-lake-api localmente** (Postgres 18 local, Redshift e SQS com dados
  fictícios). **[C]** `consolidate_valid_movement` falha em todo bloco no
  `DELETE … WHERE ref_date BETWEEN` de `replace_days`
  (`src/modules/valid/repository/movement.py:153`, commit `83fac45`): o
  SQLAlchemy 1.4.41 do `requirements.txt` não avalia o `BETWEEN` em Python
  (`InvalidRequestError: Could not evaluate current criteria`). O teste de
  repositório que já existia
  (`test_replace_days_swaps_the_block_for_every_fund_and_marks_the_days`)
  pega o erro, mas só roda com Postgres e por isso era pulado aqui. Correção
  no checkout, sem commit: `.execution_options(synchronize_session=False)`,
  como a consolidação já faz; com ela, os 6 testes de repositório do PDD e da
  Mov. Estoque passam contra o Postgres local e a carga grava os 31 dias.
  **[H]** A imagem de produção (`prod-219c8f3`) tem o mesmo código: ligar
  `CFG_VALID_MOVEMENT_SCHEDULE_ENABLED` antes do deploy da correção faz a run
  falhar e ser repetida a cada 30 min até a meia-noite, lendo o Redshift à
  toa. A carga da Rating e da Migração funcionou localmente de ponta a ponta.
- **30/10/2026 (5):** fila, worker e beat próprios para as cargas do PDD (D77),
  sem commit. data-lake-api (`feature/TS-5442-pdd-integracao`): config
  `CFG_AWS_SQS_TASKS_VALID_QUEUE_NAME`/`_URL`, as 6 tasks do `valid` roteadas para
  a fila do `valid` quando ela existe (`src/infra/celery/tasks.py`), as duas filas
  no `predefined_queues` do kombu (`src/infra/celery/__init__.py`) e
  `CELERY_WORKER_QUEUE=valid` no `entrypoint.sh`; 5 testes novos
  (`tests/test_celery_valid_queue.py`), 47 passam com os do PDD e da agenda; o
  app Celery montado com as duas filas confirma rotas, filas e agenda dos dois
  beats. ArgoCD (`feature/TS-5442-pdd-cargas-diarias`): fila no
  `resources.yaml`; worker `valid` e beat `valid-beat` no `values.yaml` de
  `asgard-production`; as `CFG_VALID_*` saíram do worker e do beat da
  consolidação. Ordem: fila e Guardian → deploy da imagem nova (com a correção
  do `replace_days`) → `values.yaml`. O `CFG_VALID_PDD_RUN_AT` que estava como
  `1:00` no worker (formato que derruba a carga da config) foi para `01:00` no
  worker `valid`, a confirmar com o Heitor (01:00 ou 19:00).
- **30/10/2026 (6):** na carga da Abertura de Rating e da Migração, "pdd" virou
  "ecl" (pedido do Heitor; escopo escolhido: só config, tasks e rota de disparo).
  `CFG_VALID_PDD_*` → `CFG_VALID_ECL_*` (prefixo da `ValidPddSettings`, com
  docstring "ECL = PDD"; também no `values.yaml` do ArgoCD), tasks
  `*_valid_pdd` → `*_valid_ecl` (com `CONSOLIDATE_ECL_TASK_NAME`) e
  `POST /valid/pdd/run` → `POST /valid/ecl/run`. Ficam: arquivos, classes,
  atributo `settings.valid_pdd`, `GET /valid/pdd`, `/valid/pdd/dates` e as
  tabelas `valid_pdd_*` (sem migration, sem mudança no BFF e no front). Nada
  em produção usava os nomes antigos (nenhuma task do módulo rodou lá). 99
  testes passam; na API local, a rota antiga dá 404 e a nova roda a carga pela
  `consolidate_valid_ecl`.
- **30/10/2026 (7):** as rotas de disparo à mão aceitam período (pedido do
  Heitor), sem commit. `POST /valid/ecl/run` e `POST /valid/stock-movement/run`
  com corpo opcional `{"start_date", "end_date"}` (as duas pontas inclusive);
  sem corpo, os dias da execução do horário, como antes. Regras na
  `manual_days` (`movement_rules.py`, usada pelas duas cargas), escolhidas para
  a poça seguir sem buracos, a confirmar [H]: o período encosta nos dias já
  lidos ou cobre parte deles (a execução diária lê de uma vez tudo o que falta
  entre o dia mais antigo e hoje); com nada lido, termina hoje; não passa de
  hoje nem começa antes do `backfill_start`; até `manual_max_days` dias (93 por
  padrão, `CFG_VALID_ECL_MANUAL_MAX_DAYS` / `CFG_VALID_MOVEMENT_MANUAL_MAX_DAYS`),
  para a run não passar do `stale_run_minutes`. Fora disso, 422 com o motivo;
  run ativa, 409. As tasks `reprocess_*` seguem com a regra antiga (só dentro
  dos dias lidos). 120 testes passam; na API local, julho e depois abril a
  junho estenderam a poça do ECL até 01/04, março (solto) deu 422 e setembro
  estendeu a da Mov. Estoque.
- **30/10/2026 (8):** D78 implementada na data-lake-api, sem commit. Tabela
  `valid_pdd_stock_day` (migration `0014`, encadeada na `0011`: ao juntar com
  a `0012` da Residual e a `0013` da Performance, acertar o `down_revision`
  antes do deploy); `ValidPddSourceRepository.get_stock_days` (o
  `GET_STOCK_DATA` limitado aos dias do bloco); `replace_stock_days` na mesma
  transação dos dias; `ValidRepository.get_stock_from_pool`; `get_stock` lê a
  poça com `stock_from_pool` (`CFG_VALID_ECL_STOCK_FROM_POOL`, desligada) e
  segue no Redshift sem ela; `backfill_start` do ECL em 01/10/2025. Testes: 150
  passam, inclusive os de repositório contra o Postgres local; a `0014` sobe e
  desce. Na API local, a rota leu a poça em 0,06 s, com a mesma escolha de
  fonte. Para produção: deploy (a migration roda no job), deixar a carga do ECL
  encher de 01/10/2025 até hoje (diária ou rota com período, até 93 dias por
  chamada) e só então `CFG_VALID_ECL_STOCK_FROM_POOL=true` no container da API.
  Dias carregados antes deste deploy não têm o estoque: reprocessar.
- **30/10/2026 (9):** D79 implementada na data-lake-api, sem commit. Modelo
  `src/infra/postgres/models/valid_run.py` (`ValidLoad`, `ValidRunTrigger`,
  `ValidRunStatus`, `ValidRunORM`, `ValidDayORM`); base
  `src/modules/valid/repository/run.py` (`ValidRunRepository`, tudo filtrado
  pela carga; `start_run` não inicia run de outra carga, já que os ids são
  comuns); `ValidPddRepository` e `ValidMovementRepository` herdam dela e
  ficam só com os dados. Migration `0015` (sobre a `0014`): no Postgres local,
  com 6 runs e 213 dias do ECL e 5 runs e 91 dias da Mov. Estoque, a ida
  preservou contagens, intervalos, dias publicados e as 195 linhas da
  movimentação apontando para runs da própria carga; a volta devolveu as
  tabelas antigas iguais. 151 testes passam (1 novo de isolamento entre as
  cargas, contra o Postgres). Na API local, as duas cargas rodaram ao mesmo
  tempo, cada uma com o seu 409. Pendências: as branches da Residual (`0012`)
  e da Performance (`0013`) ainda criam tabelas de controle próprias; ao
  juntá-las, passar a usar `valid_run`/`valid_day` (cargas `residual` e
  `payment`, com o `ck_valid_run_load` ampliado) e reencadear as migrations.
- **30/10/2026 (10):** tudo o que estava sem commit na data-lake-api foi
  commitado na `feature/TS-5442-pdd-integracao`, commit `eb5c066` (sem push):
  fila, worker e beat do `valid`, nomes ECL, rotas de disparo com período,
  poça da Visão Geral e do Histórico (`0014`), controle comum das cargas
  (`0015`) e a correção do `replace_days` da Mov. Estoque. Ficaram fora as
  alterações locais do Heitor (`.devcontainer`, `.vscode`, `README.md`,
  `docker-compose.local.yml` e a porta 8001 do `entrypoint.sh`). Hooks
  passaram; `test-arch` pulado (falha do `day_cache`, igual na master). O
  ArgoCD (`feature/TS-5442-pdd-cargas-diarias`) segue sem commit.
- **30/10/2026 (11):** quanto histórico cada execução lê virou configurável
  (pedido do Heitor), sem commit: `backfill_months` nas duas cargas
  (`CFG_VALID_ECL_BACKFILL_MONTHS`, `CFG_VALID_MOVEMENT_BACKFILL_MONTHS`;
  padrão 1, de 1 a 12). A primeira execução lê de `backfill_months` meses atrás
  até hoje; as seguintes, os `backfill_months` meses anteriores ao dia mais
  antigo lido, até o `backfill_start`. Regra em `months_before`
  (`movement_rules.py`); com 1 mês, o resultado é o mesmo de antes (conferido
  dia a dia em 5 anos). A variável é lida onde o `run_days` roda: no worker
  `valid` (execução do horário) e na API (rota de disparo sem período); por
  isso precisa estar nos dois containers. 158 testes passam; na API local, com
  2 meses, a run leu de 01/01 a 28/02 mais os dias recentes.
- **30/10/2026 (12):** o tamanho do histórico de cada execução passou de meses
  para **dias** (pedido do Heitor), sem commit: `backfill_days`
  (`CFG_VALID_ECL_BACKFILL_DAYS`, `CFG_VALID_MOVEMENT_BACKFILL_DAYS`; padrão
  31, de 1 a 366), no lugar do `backfill_months` da entrada anterior. A
  primeira execução lê os últimos N dias até hoje; as seguintes, os N dias
  anteriores ao dia mais antigo lido, até o `backfill_start`. Com 31, nenhuma
  execução lê menos que o "um mês" de antes (que tinha de 28 a 31 dias); dois
  testes de nova tentativa mudaram um dia por isso (a partir de 21/10, a run
  volta até 20/09 e não mais 21/09). `months_before` e o `one_month_before` do
  `movement_rules.py` saíram (sem uso). 149 testes passam; na API local, com 45
  dias, a run leu de 17/11 a 31/12/2025 mais os 5 dias recentes.
- **30/10/2026 (13):** o `backfill_days` foi commitado na
  `feature/TS-5442-pdd-integracao` da data-lake-api, commit `14d595b`, sobre o
  `eb5c066` (sem push). Hooks passaram; `test-arch` pulado, como antes.
- **30/10/2026 (14):** correção no ArgoCD (`feature/TS-5442-pdd-cargas-diarias`,
  sem commit), apontada pelo Heitor: o `valid-beat` tinha sido criado como item
  de `workers` com `USE_CELERY_BEAT=1`, o que está errado. O chart tem um bloco
  `beat:` só; o agendamento do `valid` passa a ficar nele
  (`CFG_VALID_ECL_SCHEDULE_ENABLED` e `CFG_VALID_MOVEMENT_SCHEDULE_ENABLED`), e
  o `valid-beat` saiu. Conferido com o app Celery: o beat agenda os 4 avisos, os
  da consolidação na fila dela e os do `valid` na `data-lake-api-valid`. O
  isolamento continua na fila e no worker `valid`. Sobra no código commitado
  (`eb5c066`): o comentário de `src/infra/celery/tasks.py` ainda fala em "worker
  e beat próprios".
- **30/10/2026 (15):** pedidos do Heitor, na `feature/TS-5442-pdd-integracao`
  (por uma cópia temporária da branch, porque o checkout principal está na
  `release/20261030`), sem commit: a tabela nova da poça virou
  `valid_ecl_stock_day` (coluna `ecl`, ORM `ValidEclStockDayORM`, migration
  `0014_valid_ecl_stock_day.py`); a `0015` não tem mais `legacy_id` nem cópia de
  dados (nenhuma run rodou) e para com erro se uma tabela de controle tiver
  linhas; o comentário de `tasks.py` passou a dizer "worker próprio (o beat é o
  da aplicação)". Validação, tudo local (nada em produção): suíte inteira com
  491 passando (a falha é a do `day_cache`, igual na release); migrations num
  banco novo a partir da `0011`, com a parada de segurança testada; beat e
  worker reais do Celery em processos separados (fila em arquivo), com uma run
  de cada carga até `success`; o `values.yaml` do ArgoCD conferido contra a
  configuração e o `entrypoint.sh`. O banco local foi recriado do zero.
- **30/10/2026 (16):** D80 implementada, sem commit, em cópias temporárias das
  branches `feature/TS-5442-pdd-integracao` (data-lake-api e BFF), porque os
  checkouts principais estão nas releases. data-lake-api: arquivos, classes,
  schemas, configuração, tasks, rotas e SQL do módulo `valid` em ECL; migration
  `0016` (renomeia `valid_pdd_*` para `valid_ecl_*`, coluna `pdd` → `ecl`,
  chaves, índices, checagem e sequências; para se houver linhas). Também tirei
  as conversões `int()`/`float()` redundantes ao montar `StockSourceRow` (o
  Pydantic converte; ficou só o `or 0` dos dois campos que podem vir nulos).
  BFF: `src/services/data_lake_api/__init__.py` chama `/valid/ecl` e
  `/valid/ecl/dates`, e os dublês dos testes também. Validação, tudo local:
  491 testes na data-lake-api (só a falha do `day_cache`), `alembic check` sem
  diferença, `0016` com parada de segurança, ida e volta; 94 testes do módulo
  no BFF; o código do BFF chamando a data-lake-api local em `/valid/ecl`;
  registro das tasks e agenda do beat conferidos.
- **30/10/2026 (17):** commitado nas duas `feature/TS-5442-pdd-integracao`
  (sem push): data-lake-api `5d284f6` (nomes ECL no módulo `valid`, rotas
  `/valid/ecl`, `0015` sem cópia, `0016`, `StockSourceRow` sem conversões) e
  BFF `ee9d113` (chama `/valid/ecl` e `/valid/ecl/dates`). Hooks passaram; na
  data-lake-api o `test-arch` foi pulado (falha do `day_cache`), no BFF passou.
  Os dois sobem juntos.
- **30/10/2026 (18):** ArgoCD, staging (branch `feature/TS-5442-pdd-cargas-diarias`,
  sem commit): worker `valid` igual ao de produção (com `ENVIRONMENT=staging`)
  e as variáveis de agendamento no beat; o comentário do beat do staging foi
  corrigido (ele passa a agendar as cargas do valid). Horários iguais aos de
  produção, por escolha do Heitor, apesar de o Postgres do staging ficar
  desligado das 19h às 08h e nos fins de semana (Datadog, 7 dias). Com isso, o
  ECL das 01:00 deve acabar rodando nas novas tentativas depois das 08:00, e a
  Mov. Estoque das 19:00 tende a não completar; durante o dia, a rota de
  disparo funciona. Sandbox sem mudança (só tem a API, com imagem antiga).
  Conferido com o código: no staging o beat agenda só `dispatch_valid_ecl` e
  `dispatch_valid_movement`.
