# 02 — Abertura de Rating

- **Status:**
  - 22/10/2026: viabilidade conferida no lake. **Dá para construir** a
    "visão do cliente" (rating do administrador, VP, PDD e % PDD por fundo e
    produto) só com `administradores_estoque_contrato` + `dim_contrato`. O
    filtro de produto cobre ~51% do VP de 30/09; o resto fica "sem produto"
    (D18). O "Recálculo PLGN" e a faixa de dias de cada rating dependem de uma
    régua que não está nas views (D19).
  - 25/10/2026: D18 (sem grupo "Sem produto") e D19 (régua cadastrada no
    platform-cessao, lida por produto) tomadas. Em aberto: os contratos sem
    produto entram nos totais com "Todos os produtos"?
  - 26/10/2026: D18 completada (os contratos sem produto entram nos totais
    da aba). D28 aberta (como ligar a régua ao produto).
  - 26/10/2026: D28 tomada (régua da `regra`); D30 (régua em vigor na data
    de referência); D31 aberta (como achar essa régua).
  - 26/10/2026: D31 provisória (opção c, a validar com o time) e D32 (aviso
    sem régua).
  - 26/10/2026: D17 tomada; D22 provisória (Postgres).
  - 27/10/2026: D48 aberta (contrato da rota).
  - 27/10/2026: D50 (produto obrigatório; sem visão de todos os produtos nem do
    fundo) e D51 (Recálculo PLGN fora desta versão). D48 revista.
  - 27/10/2026: implementada nos quatro repositórios, com commit (ver
    Histórico). 28/10/2026: integrada na `feature/TS-5442-pdd-integracao`
    (front, BFF e data-lake-api), com o escopo `pdd-rating-opening`. Poça
    vazia até aplicar a migration `0010` e ligar a carga (desligada por
    padrão). D31 e D22 provisórias, a validar.
- **TS-5438.** Branch `feature/TS-5438-pdd-abertura-de-rating` nos quatro
  repositórios, criada em 27/10/2026 a partir do `origin/master` local, sem
  upstream e sem commit:

  | Repositório | Base |
  |---|---|
  | apl-credit-whitelabel (front) | `f7bb2d84` (`origin/master` buscado em 27/10) |
  | apl-credit-whitelabel-api (BFF) | `bb877db` (buscado em 27/10) |
  | data-lake-api | `d3708f0` (buscado em 27/10) |
  | platform-cessao | `f19ef2ce` (buscado em 20/10; atualizar com `git fetch origin` e `git merge --ff-only origin/master`) |

  O `git fetch` não rodou nesta sessão (sem acesso à chave SSH). A
  implementação da Mov. Estoque está guardada em `stash@{0}` no front, no BFF
  e na data-lake-api (27/10, 16h01).
- **Repos:** data-lake-api (consulta e rota), BFF (rota), front (a aba já
  existe e espera o contrato `PddPerProduct`), platform-cessao (rota da régua
  por produto, D19).
- **Evidência:** [rating-migration-redshift-2026-10-22.md](../evidence/rating-migration-redshift-2026-10-22.md).

## Item original

> Irei desenvolver a visualização de "Abertura de Rating" e "Análise de
> Migração", que iteram sobre as informações de PDD do fundo. Nessas
> visualizações, temos um filtro de produto, cujo ID está na view
> "dim_contrato". Verifique se é possível construir essas duas visualizações
> com o que temos estruturado hoje no banco de dados. Só posso usar as Views
> "administradores_*" e "dim_contrato" para esse dashboard.
>
> — Heitor, 22/10/2026

## O que a tela precisa

Protótipo `dashboard_fundos.html` **[C]**:

- **Visão do cliente** (`renderRatingBanda`, `:769`; `aggBandas`, `:706`):
  uma linha por rating com faixa de atraso (dias, da régua), % régua, Qtd.
  (contratos), VP, PDD e % PDD; total no rodapé.
- **Recálculo PLGN (atraso por sacado)** (`renderMinha`, `:847`;
  `minhaRows`, `:826`): o mesmo estoque reagrupado pela faixa de atraso do
  **sacado** (o maior atraso dele), com PDD = VP × % da régua. Some da tela
  quando o dado não existe (`:853`).
- **Indicadores:** VP total, PDD total, % PDD, número de ratings e contratos;
  taxa média ponderada, vencimento do dia e ticket médio (`metricasFor`,
  `:367`).
- **Rosca PDD/VP** e **VP por rating** (os 6 maiores).
- **Filtros:** fundo (ou consolidado), produto, data.

Front atual (commit `f7bb2d84`) **[C]**:

- A aba já existe (`pdd/rating/pdd-rating.component.html`) e mostra "ainda
  não disponível" enquanto `pddPerProduct` está vazio
  (`pdd/pdd.page.ts:86-90`).
- Contrato esperado: `PddPerProduct { product {id, name}, pdd_rate[] }`, com
  `rating`, `aging_from`, `aging_to`, `contract_count`, `pv`, `pdd`,
  `pdd_pv_ratio` (`data-access/pdd/pdd.interface.ts:3-17`).
- O filtro "Produtos" aparece nas abas Rating e Migração
  (`pdd/pdd.page.html:55`) e lista os produtos que vierem no próprio
  `pddPerProduct` (`pdd/pdd.page.ts:121-123`).

## O que o lake tem

| Elemento | Situação | De onde |
|---|---|---|
| Rating por contrato | **[C]** disponível | `faixa_pdd` de `administradores_estoque_contrato` |
| VP, PDD, contratos | **[C]** disponível | `vl_presente`, `vl_pdd` (vem negativo: usar o módulo), `COUNT(*)` |
| Produto | **[C]** parcial: ~51% do VP | `dim_contrato.produto_id`, ver "Produto" abaixo |
| Nome do produto | **[H]** fora das views | `controllership/valid/funds` do BFF (`produtos` de cada fundo) |
| Faixa de dias e % da régua | **[C]** não está nas views | régua do platform-cessao por produto (D19), rota a criar |
| Recálculo PLGN | **[C]** dados existem; régua a caminho | `cpf_cnpj_sacado` e `dias_atraso` preenchidos; régua pela rota da D19 |
| Taxa média, vencimento do dia, ticket | **[C]** disponível | ticket = VP ÷ contratos; taxa e vencimento como na tarefa 01 |

### Rating

- O rating da tela é o `faixa_pdd` do administrador: é ele que tem a PDD
  calculada. O `rating` de `dim_contrato` é outro (rating da originação, com
  `score`) e não coincide com o `faixa_pdd` **[C]**.
- Cada administrador tem a sua escala (BGT AA–H, `GLOSA`, `PJ`; Genius A–M,
  `WOP`; Kanastro A–D; QY AA, A). A ordem de exibição precisa conhecer essas
  letras extras (`pdd.view.ts:120` só conhece AA–G).
- Fundos sem PDD: Fydd manda PDD zero (P12); QY mandou zero em 30/09 (P13).

### Produto

Regra que funcionou em 30/09/2026 (D17) **[C]**:

1. mesmo fundo: `dim_contrato.cnpj_classe = cnpj_classe`;
2. `dim_contrato.num_controle = id_contrato_admin`;
3. se não casar, `dim_contrato.identificador = id_contrato_admin`.

Sem o passo 1, os números colidem entre fundos. Com ele, nenhum contrato
casou com duas linhas, e as duas chaves nunca deram produtos diferentes. Por
administrador: BGT e Genius usam `num_controle`; QY usa `identificador`;
Fydd casa pelas duas.

**Sem produto [C]:** Kanastro A, Dayvale A e BGT B, C, F, G, J, K, L não
estão em `dim_contrato`; Genius C (~21% do VP) e Genius E (~4%) casam só em
parte. Juntos, ~49% do VP de 30/09 (Kanastro sozinho ~34%). Ver P16.

D18 (25 e 26/10): esses contratos não ganham opção no filtro de produto,
mas **entram nos totais da aba**. Sem produto escolhido, a aba mostra o fundo
inteiro, e o total bate com a Visão Geral. Escolhido um produto, saem. O
contrato atual do front (`PddPerProduct`, uma entrada por produto) não tem
onde pôr essas linhas: a rota precisa devolver também o total do fundo por
rating, à parte das entradas por produto.

Quase todo fundo tem um produto só. Têm mais de um: BGT A (3), Genius C (2) e
Genius E (3, um com 94% do VP).

### Faixa de dias e % régua

**D19 (25/10):** a régua vem do platform-cessao. Como ela é hoje **[C]**
(`platform-cessao`, commit `f19ef2ce`):

- Cadastro: `POST /pdd/regua` (`cessao/api/pdd/viewer.py:23-33`, namespace
  em `cessao/app_factory.py:137`), com `nome`, `faixas` (`faixa_pdd` inteiro e
  `rate_perc`), `prazo_pdd` e `meses_matriz` (`cessao/api/pdd/schema.py:7-24`).
  Só existe o cadastro: não há rota para ler, listar, alterar ou apagar régua.
  A resposta é um texto ("Régua: X criada com sucesso! ID: N"), não um JSON.
- Fluxo (`cessao/api/pdd/service.py:7-18`): recusa nome repetido e régua com
  as mesmas faixas, `prazo_pdd` e `meses_matriz` de outra
  (`cessao/api/pdd/validator.py:39-65`); grava a régua e uma linha por faixa,
  com `ordem` dada pelo `rate_perc` crescente.
- `prazo_pdd` = `contrato` ou `devedor` (padrão `devedor`,
  `cessao/database/enum.py:777-781`): conta o atraso por contrato ou pelo
  devedor (sacado). É o que o "Recálculo PLGN" precisa.
- `meses_matriz`: inteiro, padrão 0; nenhum código o usa. **[H]** Meses de
  matriz de rolagem para uma PDD calculada pela migração.
- Formato das faixas, pela fixture de teste (`test/api/pdd/fixtures.py:7-22`)
  **[C]**: `faixa_pdd` em dias **negativos** depois do vencimento (0, −15,
  −30, −60, −90, −120, −150, −180, −9999) e `rate_perc` em fração (0; 0,005;
  0,025 … 1,0). Cada valor é o **fim** da faixa: em dia → 0%, 1–15 dias →
  0,5%, 16–30 → 2,5% … acima de 180 → 100%. Confirmado em 26/10 pelo
  conciliador, que lê o mesmo formato (`cessao/conciliacao/conciliador.py:187-207`)
  **[C]**.
- Tabelas `regua_pdd` e `regua_pdd_faixa` (`cessao/database/models.py:1665-1691`,
  migração `cessao/migrations/versions/2022-01-04T16:01:01_788d1945fa15_.py`),
  sem chave para produto ou fundo, e nenhum código lê a régua (a regra
  `cessao/framework/regras/pdd/pdd_default.py` não está implementada). A
  rota nova precisa dessa ligação (D28).
- Pontos frágeis do validador, lidos no código e não testados **[C]**: sem
  `prazo_pdd` no corpo, o padrão vira o enum e a comparação com as réguas
  existentes (`validator.py:33-35`) nunca acusa duplicada; se a nova régua
  repete as faixas de uma existente e tem faixas a mais,
  `validator.py:25` dá `IndexError` (erro 500); se tem faixas a menos, é
  recusada como duplicada.

A régua do platform-cessao é a da PLGN, não a do administrador: ela alimenta
o "Recálculo PLGN". A "visão do cliente" continua com o rating que o
administrador manda, sem coluna de dias.

### Tabelas de PDD no platform-cessao

Lidas em 26/10/2026 no código (`platform-cessao`, commit `f19ef2ce`) e no
espelho das tabelas no lake (`captalys_trusted.platform_cessao_master_*`)
**[C]**:

| Tabela | O que guarda | Quem usa | Linhas |
|---|---|---|---|
| `regra` (tipo `pdd`) | régua por **produto e fundo**: `kwargs` com `faixa_pdd`, `pdd_rate`, `prazo_pdd`, `meses_matriz` (`cessao/database/models.py:1555-1565`) | conciliador da cessão, na compra de contratos vencidos (`conciliador.py:225-238`); leitura e cadastro em `GET`/`POST /produto/{id}/regras` (`cessao/api/produto/viewer.py:116-157`) | 255 regras de PDD, 131 ativas, 98 produtos |
| `regua_pdd` + `regua_pdd_faixa` | régua solta, sem produto (`models.py:1665-1691`) | só o `POST /pdd/regua`; nada lê | 0 |
| `regra_pdd_prazo_devedor` | maior atraso por sacado e por cedente, por fundo (`models.py:1655-1663`) | nenhum código nos repositórios locais | 14,6 mi, carga única de 24/10/2023, 2 fundos |
| `regra_pdd_faixa` | valor de aquisição por faixa, fundo, produto e data (`models.py:1640-1653`) | nenhum código | não espelhada no lake |
| `estoque` | foto por parcela vinda do arquivo do administrador, com `valor_pdd` e `faixa_pdd` em texto (`models.py:5040-5070`) | nenhum código | legado, de 2019 |

- **Linha do tempo [C]:** as tabelas `regra_pdd_faixa` e
  `regra_pdd_prazo_devedor` entraram no código em 15/05/2020 (commit
  `c6ed0986`), e a primeira regra de PDD na `regra` é de 16/05/2020. A
  `regua_pdd`, a `regua_pdd_faixa` e a rota `POST /pdd/regua` vieram em
  04/01/2022 (VEGA-1855, commits `fdfc3d80` e `f16c45d4`) e nunca receberam
  linha. Regras de PDD na `regra` por ano de criação: 8 (2020), 48 (2021), 36
  (2022), 18 (2023), 20 (2024), 70 (2025), 55 (2026). Ou seja, o cadastro
  continuou na `regra` depois de 2022.
- **A régua que vale é a da `regra`.** No produto 713 (94% do Genius E), a
  regra ativa tem 1% (em dia), 1,9% (1–15 dias), 6% (16–30), 15% (31–60), 33%
  (61–90), 47% (91–120), 66% (121–150), 86% (151–180), 100% (181–360) e 100%
  (acima de 360). É o % de PDD medido no lake para os ratings A, B, C … `WOP`
  desse produto em 30/09 ([evidência](../evidence/rating-migration-redshift-2026-10-22.md)).
- `prazo_pdd` nas regras de PDD: 125 ativas `devedor` e 6 ativas `contrato`
  (mais 123 e 1 inativas). Os 12 produtos do estoque com régua ativa são
  todos `devedor`.
- A troca de régua é feita desativando a regra antiga e criando outra: no
  Genius E, as regras de 449, 713 e 1043 foram desativadas e recriadas em
  05/02/2026. Não há campo de vigência, mas as datas dão uma aproximação
  **[H]**: a regra vale de `data_criacao` até o `data_atualizacao` em que foi
  desativada (o `data_atualizacao` também muda em qualquer outra edição).
- O par produto 72 + fundo 37 tem duas regras de PDD ativas, com as mesmas
  taxas (criadas em 2021 e 2023). O conciliador busca uma só
  (`conciliador.py:232-238`, `one_or_none`) e daria erro nesse par.
- Dos 21 produtos achados no estoque em 30/09, 12 têm regra de PDD ativa (36,
  69, 449, 713, 746, 1043, 1340, 1538, 1637, 1703, 1802, 1835). Sem regra ativa:
  1 (77% do BGT A), 812, 1143, 1145, 1472, 1505, 1571 (só inativa), 1769 e 1868
  (QY).
- A regra é por produto **e** fundo: a leitura precisa dos dois (o fundo da
  plataforma, não o CNPJ).
- Na compra de contratos com parcela vencida, o conciliador aplica a régua com
  **efeito vagão** fixo (`conciliador.py:41`): o % da parcela mais antiga
  (`conciliador.py:286-298`) desconta o VP de todas as parcelas do contrato
  (`conciliador.py:300-318`).

**D28 (26/10, Heitor):** a régua vem da `regra` (tipo `pdd`, produto + fundo),
as tabelas que já existem e estão em uso. `regua_pdd` não entra.

### Régua vigente na data de referência

**D30 (26/10, Heitor):** a visão usa a régua que estava em vigor na data de
referência. A `regra` não tem campo de vigência; o que existe **[C]**:

- **Troca por linha nova:** no Genius E, em 05/02/2026 por volta das 16h50,
  as regras de 449, 713 e 1043 foram desativadas e outras criadas no mesmo
  minuto. Nesse caso, `data_criacao` e o `data_atualizacao` da desativação
  marcam a troca.
- **Edição no lugar:** a rota de cadastro (`POST /produto/{id}/regras`,
  `cessao/api/produto/viewer.py:133-161`) acha a regra por produto, nome, tipo
  e fundo (`get_or_create` → `one_or_none`, `cessao/database/__init__.py:161-189`)
  e grava o `kwargs` novo **na mesma linha**: a régua anterior se perde. Desde
  15/08/2026 isso aconteceu 3 vezes (regra do produto 1670 em 01/09; do 1901 em
  12/09 e 15/09).
- **Erro na rota:** onde já existem duas regras com o mesmo nome no mesmo
  produto e fundo (713, 449 e 1043 no Genius E), o `one_or_none` levanta erro e
  a rota não consegue mais editar a régua. A troca de 05/02 foi feita por
  outro caminho.
- **Histórico no lake:** `captalys_trusted.platform_cessao_master_regra_history`
  (gravada pela ingestão do lake, com operação e horário do commit) tem cada
  alteração, mas só a partir de 15/08/2026, e não está entre as views
  permitidas (D1, D16).

**D31 (26/10, provisória, Heitor vai validar com o time), opção (c):** para o
produto e o fundo do contrato, a regra de PDD com `data_criacao` até o fim do
dia de referência e que estava ativa no fim desse dia (ativa hoje, ou
desativada depois dele). A foto do estoque é de fim de dia, então em
05/02/2026 vale a régua nova. Junto, a rota de cadastro passa a criar uma linha
nova e desativar a anterior nas regras de PDD, em vez de editar a mesma linha.

**D32 (26/10, Heitor):** sem régua em vigor na data (data anterior à primeira
regra do produto, ou produto sem régua), o painel "Recálculo PLGN" mostra
"Sem régua de PDD cadastrada para a data de referência selecionada". Proposta
para a seleção com vários produtos: o painel recalcula os que têm régua e
mostra o aviso para os que não têm.

### Campos das tabelas de PDD

Colunas reais pelo catálogo do espelho no lake (26/10/2026), sem as colunas
técnicas de replicação; `regra_pdd_faixa` e `estoque` não são espelhadas e
saem do modelo (`cessao/database/models.py`). Toda tabela tem `id`,
`data_criacao` e `data_atualizacao` (`cessao/database/__init__.py:217-235`).

| Tabela | Campos que importam aqui | Chaves |
|---|---|---|
| `fundo` | `nome`, `cnpj` (único), `adm`, `adm_cnpj`, `codigo_fundo` (+ cadastro do fundo: gestor, categoria, datas) | `cnpj` = `cnpj_classe` do lake (só dígitos) |
| `produto` | `nome`, `natureza`, `amortizacao`, `indexador`, `coobrigacao`, `recompra`, multa e mora | `id` = `dim_contrato.produto_id` |
| `produto_fundo` | `produto_id`, `fundo_id`, `default` (fundo padrão), `data_inicio`, `data_fim`, `config_extra`, desembolso | liga produto a fundo (N:N) |
| `regra` | `nome` (`Pdd`), `tipo_regra` (`pdd`), `ativada`, `kwargs` (JSON em texto), `produto_id`, `fundo_id` | uma régua por produto + fundo ativa |
| `regua_pdd` | `nome`, `prazo_pdd`, `meses_matriz` | sem ligação; vazia |
| `regua_pdd_faixa` | `id_regua`, `ordem`, `faixa_pdd`, `rate_perc` | `id_regua` → `regua_pdd`; vazia |
| `regra_pdd_prazo_devedor` | `fundo_id`, `devedor_id`, `tipo_devedor` (sacado/cedente), `prazo_devedor` | `devedor_id` sem chave estrangeira; carga única de 2023 |
| `regra_pdd_faixa` | `fundo_id`, `produto_id`, `faixa`, `faixa_descricao`, `valor_aquisicao`, `data_referencia` | sem uso |
| `estoque` | foto por parcela do arquivo do administrador: `nome_fundo`, `doc_fundo`, `doc_sacado`, valores, `valor_pdd`, `faixa_pdd` (texto), `data_referencia` | sem chave para fundo ou produto; sem uso |

`kwargs` de uma regra de PDD (produto 713, fundo 209, ativa) **[C]**:

```json
{
  "faixa_pdd": {"0": 0, "1": -15, "2": -30, "3": -60, "4": -90, "5": -120,
                "6": -150, "7": -180, "8": -360, "9": -99999},
  "pdd_rate":  {"0": 0.01, "1": 0.019, "2": 0.06, "3": 0.15, "4": 0.33,
                "5": 0.47, "6": 0.66, "7": 0.86, "8": 1, "9": 1},
  "prazo_pdd": "devedor",
  "meses_matriz": 0
}
```

As chaves "0" a "9" ligam cada limite de dias ao seu %; o limite é o fim da
faixa, em dias negativos depois do vencimento.

### Como as tabelas se ligam

Versão desenhada (tabelas, busca do contrato ao %, régua do 713, troca de régua e
opções da D28): [Mapa da régua de PDD](https://claude.ai/artifact/8NFBusNPsXJXRbvUdd4SFU)
(artefato privado, 26/10/2026).

```
LAKE                                      PLATFORM-CESSAO
administradores_estoque (parcela)
  │ cnpj_classe + id_contrato_admin
administradores_estoque_contrato
  │ cnpj_classe + id_contrato_admin
  │   = cnpj_classe + num_controle (ou identificador)   (D17)
dim_contrato ── produto_id ───────────────► produto ─┐
  │                                                  ├─ produto_fundo (vigência, fundo padrão)
  └──── cnpj_classe = cnpj ───────────────► fundo ───┘
                                             regra (produto_id + fundo_id, tipo pdd, ativada)
                                               └─ kwargs: faixa_pdd, pdd_rate, prazo_pdd
regua_pdd ─< regua_pdd_faixa       (sem ligação, vazias)
regra_pdd_prazo_devedor, regra_pdd_faixa, estoque   (legado, sem uso)
```

Exemplo real no Genius E em 30/09/2026 (fundo 209 da plataforma, produto 713)
na [evidência](../evidence/rating-migration-redshift-2026-10-22.md#cadeia-estoque--produto--régua-26102026).

O que se observa nos dados, para comparar com a régua cadastrada:

As views não trazem a régua (faixa de dias → % de PDD de cada rating) **[C]**.
Dá para observar:

- **% PDD por rating:** estável dentro do produto (Genius E, produto 713: A
  1,2%, B 2,1%, C 6,2%, D 15,2%, E 33,1% … `WOP` 100%).
- **Faixa de dias:** o mínimo e o máximo de `dias_atraso` por rating saem
  largos, porque o rating não segue só o atraso do contrato (P17): BGT H vai
  de em dia a 380 dias; Genius A tem contratos com mais de 3 mil dias.
  Mostrar isso como "faixa de atraso" seria enganoso.

## Proposta

1. **Consulta** ([rating_by_product.sql](../attachments/sql/rating_by_product.sql)):
   por fundo, produto e `faixa_pdd`, numa data: contratos, VP, PDD (módulo),
   atraso mínimo e máximo. Um fundo leva ~11 s; todos os fundos de um dia,
   uma leitura da foto (~8,5 mi de contratos) e uma varredura de
   `dim_contrato` (D22).
2. **Rota** nova na data-lake-api e no BFF, devolvendo o contrato que o front
   já espera (`PddPerProduct[]`), com o nome do produto vindo de
   `controllership/valid/funds`. Sem grupo "Sem produto" (D18).
3. **Front:** preencher `pddPerProduct` em `fetchDashboard`; ordem dos
   ratings por administrador; "visão do cliente" sem coluna de dias.
4. **Recálculo PLGN:** com a rota da régua por produto (D19), aplicando o
   efeito vagão conforme o `prazo_pdd` da régua (D29, provisória): `devedor`
   arrasta pelo pior atraso do sacado no fundo; `contrato` só dentro do
   contrato. A data-lake-api
   agrupa o VP por produto e atraso (do contrato ou do sacado, conforme
   `prazo_pdd`); a régua dá a faixa e o %. Onde aplicar a régua (data-lake-api
   ou BFF, que já fala com o platform-cessao) ainda está em aberto. Com a D22
   em Postgres, a sugestão é gravar o VP por produto e dia de atraso (do
   contrato e do sacado) e aplicar a régua em vigor (D30, D31) na leitura:
   assim uma régua corrigida depois vale sem recalcular os dias gravados.

## Validação

- Soma do VP da aba = VP do estoque do fundo na mesma data (Visão Geral). No
  Genius E, 30/09: 125,17 nas duas **[C]**.
- Por produto: a soma dos produtos ≤ total do fundo; a diferença é o VP sem
  produto (P16).
- Recálculo PLGN: o total de VP é o mesmo da visão do cliente; só a PDD muda.

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
- D22 e D31 provisórias, a validar com o time.
- **Buraco nos dias novos (achado em 28/10, na Mov. Estoque):** o `run_days`
  da Rating parte do dia mais novo lido. Depois de um agendamento parado por
  mais de 5 dias, os dias novos vão em vários blocos, do mais novo para o mais
  antigo. Se a execução parar no meio, os dias entre o antigo mais novo e o
  bloco gravado nunca mais são lidos: a próxima execução só relê os 5 dias
  recentes. A Mov. Estoque acha os buracos pelo registro dos dias lidos
  (`movement_rules.run_days`). Levar a mesma regra para a Rating na branch
  que junta as duas.
- Mudança na rota de cadastro de regras de PDD: **não será feita** (D57).
- ~~Rota de leitura da régua~~ feita no platform-cessao em 27/10 (sem commit):
  `GET /pdd/regua-vigente`.
- Régua de PDD ativa para os 9 produtos sem regra (D28).
- Texto para fundo sem produto nesta aba: hoje "Este fundo não tem produto
  cadastrado" (provisório, Heitor não respondeu em 27/10).
- Confirmar que o `id` de produto da rota `valid/funds` é o `produto_id` de
  `dim_contrato` (BGT A deve listar 1, 36 e 69).
- P12, P13, P15, P16, P17 em [data-problems.md](../data-problems.md).

## Histórico

- **22/10/2026:**
  - Protótipo e front mapeados; viabilidade conferida no lake (chave de
    produto, cobertura, rating, PDD, régua observada).
  - D16 tomada (Heitor): `dim_contrato` liberada para o produto. D17, D18,
    D19 e D22 abertas.
- **27/10/2026 (noite, 5):** D48 e D49 aprovadas; D57 (no platform-cessao, só
  a rota de leitura). **platform-cessao, sem commit:** `GET /pdd/regua-vigente`
  com `cnpj_fundo`, `data_referencia` e `produto_id` opcional
  (`cessao/api/pdd/viewer.py`, `service.py`, `repository.py`, `schema.py`):
  devolve uma régua por produto do fundo, a da `regra` (tipo PDD) criada até o
  fim do dia e ativa nele, com `vigente_desde`, `vigente_ate`, `prazo_pdd` e as
  faixas em dias de atraso (`dias_de`, `dias_ate`, `percentual`). 404 para
  fundo inexistente. Testes em `test/api/pdd` escritos e não rodados (Python
  3.8 com índice privado); a lógica do service foi exercitada com as
  dependências imitadas (todos os cenários ok, inclusive as réguas reais dos
  produtos 1637 e 1703).
- **27/10/2026 (noite, 4):** Recálculo PLGN implementado no front, sem
  commit: componente `pdd/plgn/pdd-plgn.component` (comparação PDD do
  administrador × recalculada, tabela por faixa da régua, aviso sem régua da
  D32), `buildPlgnView` em `pdd.view.ts`, bloco `plgn` opcional em cada
  produto do contrato (D48) e recálculo fictício no mock (Consignado e Cartão
  com régua; Crédito pessoal sem). D55 tomada. Lake inacessível às 22h15
  (conexão recusada).
- **27/10/2026 (noite, 3):** D54 (Recálculo PLGN volta, desfaz a D51); saiu
  do later.md. D48 revista com o bloco `plgn` por produto.
- **27/10/2026 (noite, 2):** D52 (fundo obrigatório) e D53 (abre sem produto)
  tomadas. Front ajustado na branch da TS-5438, sem commit: seletor de fundo
  sem a carteira consolidada nesta aba; seletor de produto único e
  obrigatório; avisos "Selecione um fundo", "Selecione um produto" e "Este
  fundo não tem produto cadastrado" (texto provisório, a confirmar); a tabela
  e a provisão mostram só o produto escolhido; sai a coluna de dias de atraso
  (D19). ESLint e checagem de tipos limpos; specs atualizados e não rodados.
- **27/10/2026 (noite):** D50 e D51 tomadas (Heitor); D48 simplificada; D18
  passa a valer só na Análise de Migração; Recálculo PLGN para later.md.
- **27/10/2026 (tarde):** front rodando localmente em modo mock
  (`127.0.0.1:4200`, Node 22.23.3 em `~/.local/opt`). Para a aba mostrar dados,
  o front passou a pedir `controllership/valid/pdd` (`getPddPerProduct` no
  `PddService`, chamado no `fetchDashboard`; sem a rota, a lista fica vazia e a
  aba mostra o aviso), na branch da TS-5438, **sem commit**. A rota é
  provisória: o contrato com o BFF ainda será definido.
- **27/10/2026:** TS-5438; branch `feature/TS-5438-pdd-abertura-de-rating`
  criada nos quatro repositórios (sem upstream, sem commit). Mov. Estoque em
  stash.
- **26/10/2026 (noite, 4):** D31 tomada como provisória, opção (c) (Heitor vai
  validar com o time). D32: aviso no Recálculo PLGN quando não há régua na data.
- **26/10/2026 (noite, 3):** D28 tomada e D30 (Heitor). Mapeado como a
  régua muda: troca por linha nova, edição no lugar pela rota de cadastro e
  histórico do lake só desde 15/08/2026. D31 aberta.
- **26/10/2026 (noite, 2):** diagramas da régua publicados como artefato
  ("Mapa da régua de PDD"). Achados: 6 réguas ativas `contrato` na plataforma;
  troca de régua por desativação e recriação; par 72 + 37 com duas ativas.
- **26/10/2026 (noite):** D29 tomada, provisória (Heitor): vagão no contrato
  em 100% dos casos no Recálculo PLGN; revista em seguida para seguir o
  `prazo_pdd` da régua (sacado se `devedor`, contrato se não). Cadeia estoque → `dim_contrato` →
  `fundo`/`produto` → `regra` confirmada no Genius E, com contratos reais.
- **26/10/2026 (tarde):** tabelas de PDD do platform-cessao mapeadas; a régua
  por produto já existe na `regra` (tipo `pdd`) e bate com o lake no produto
  713. Efeito vagão medido no lake. A "D23" de hoje virou D28 (o número já era
  da Mov. Estoque). A D22 chegou a ser alinhada à D26 (Redis), mas a D26 foi
  desfeita no mesmo dia: volta o Postgres.
- **26/10/2026:** D18 completada (contratos sem produto entram nos totais,
  Heitor). Rota de cadastro da régua lida em detalhe; D28 aberta (ligação
  régua × produto).
- **25/10/2026:** D18 e D19 tomadas (Heitor). Mapeada a régua do
  platform-cessao; Recálculo PLGN volta ao escopo, dependendo da rota da
  régua por produto.
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
- **30/10/2026:** deploy de produção de 29/10 conferido no Datadog: migrations
  0010 e 0011 aplicadas; a carga diária das 19h não foi disparada (o beat não
  agendou `dispatch_valid_pdd`). Detalhes no histórico da
  [tarefa 01](01-stock-movement.md).
