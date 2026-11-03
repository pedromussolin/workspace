Status: em andamento
Data: 03/11/2026
Tags: valids, pdd, ecl, controladoria, lake

# VALIDs: dashboard de PDD — Planejamento

Pasta de trabalho do dashboard de PDD da controladoria (tela "Conciliação de
Estoques e VALIDs", `features/controllership/pdd` do portal). Um arquivo por
tarefa, com o problema, as evidências, a proposta e como vamos provar que
funcionou.

> **Chat novo?** Comece por [CONTINUE.md](CONTINUE.md): onde parei, as
> branches de cada repositório e o próximo passo.

- Migrada em 03/11/2026 da pasta local `~/projects/pdd-workspace`, que não era
  versionada; o conteúdo é o mesmo, com os nomes de pasta e de arquivo em
  inglês.

- Referência visual e de cálculo: o protótipo
  `apl-credit-whitelabel/src/app/features/controllership/pdd/dashboard_fundos.html`
  (arquivo local, fora do git do front).
- Dados: Redshift do lake, lido pela data-lake-api e repassado pelo BFF.
  Só as views `plgn.administradores_*` alimentam o dashboard (D1), mais a
  `plgn.dim_contrato` para o produto do contrato (D16).
- Os dados das views ainda não foram validados (21/10/2026). O que parecer
  errado vai para [data-problems.md](data-problems.md).

## Como ler esta pasta

> Os nomes reais por trás dos análogos e o CNPJ de cada fundo citado por letra
> ficam fora do repo, em `~/.config/workspace/private/valids.md`.
> Ver o `CLAUDE.md`.

| Arquivo | Para que serve |
|---|---|
| [CONTINUE.md](CONTINUE.md) | Onde parei, branches e próximo passo |
| [concepts.md](concepts.md) | Valor presente, taxa, accrual de juros e PDD (régua, efeito vagão), para quem não é da área |
| [decisions.md](decisions.md) | Decisões tomadas e pendentes, com quem decide |
| [data-problems.md](data-problems.md) | Inconsistências achadas nas views do lake |
| [evidence/stock-movement-redshift-2026-10-21.md](evidence/stock-movement-redshift-2026-10-21.md) | Perfil das views e reconciliação de set/26 por fundo, com as consultas |
| [evidence/rating-migration-redshift-2026-10-22.md](evidence/rating-migration-redshift-2026-10-22.md) | `dim_contrato`, chave do produto, rating, atraso e rolagem, com as consultas |
| [evidence/inconsistency-monitoring-redshift-2026-10-27.md](evidence/inconsistency-monitoring-redshift-2026-10-27.md) | Escada de vencimentário, lacunas de parcelas e nominal × aquisição, com as consultas |
| [later.md](later.md) | Melhorias adiadas, com o que falta para retomar |
| `tasks/` | Uma tarefa por arquivo (lista abaixo) |
| `attachments/` | SQL e o cliente somente leitura do Redshift |

Todas as referências de código (`arquivo:linha`) apontam para estes commits:

| Repositório | Commit (21/10/2026) |
|---|---|
| apl-credit-whitelabel (front) | `f7bb2d84` (master) |
| apl-credit-whitelabel-api (BFF) | `bb877db` (master) |
| data-lake-api | `d3708f0` (master; mudanças locais só em `.devcontainer`, `.vscode`, `README.md` e `entrypoint.sh`) |
| platform-cessao | `f19ef2ce` (master, consultado em 25/10/2026) |

## Abas do dashboard

| Aba | Situação |
|---|---|
| Visão Geral | completa; 30/10: passa a ler a poça do Postgres pela carga do ECL (D78), sem commit, atrás de `CFG_VALID_ECL_STOCK_FROM_POOL` |
| Histórico VP e PDD | completa; 30/10: idem (D78), 12 meses de histórico |
| Mov. Estoque | em andamento: [tarefa 01](tasks/01-stock-movement.md) |
| Abertura de Rating | implementada na TS-5438 e integrada na TS-5442 (27–28/10), com o Recálculo PLGN; poça vazia até ligar a carga: [tarefa 02](tasks/02-rating-breakdown.md) |
| Análise de Migração | faixas mensais integradas na TS-5442; limites de datas ligados no BFF e no front (28/10, alterações locais); pagamento pendente: [tarefa 03](tasks/03-migration-analysis.md) |
| Monitoramento de Inconsistências (Performance de Pagamento, Lacunas de Parcelas, Análise Residual) | Análise Residual commitada (29/10, TS-5466, sem push); Performance de Pagamento e Lacunas só com o título: [tarefa 04](tasks/04-inconsistency-monitoring.md) |

## Tarefas

| # | Tarefa | Repos | Depende de | Status | TS |
|---|---|---|---|---|---|
| 01 | [Mov. Estoque: aquisições, baixas e accrual de juros](tasks/01-stock-movement.md) | data-lake-api, BFF, front | D8 provisória (controladoria) | desenho definido (21–22/10): aquisições e baixas por dia, accrual por roll-forward diário numa consulta por intervalo (D15, D23), período livre; implementado nas branches, sem commit (23/10); 26/10: movimentação na "poça" do Postgres, numa consolidação própria por fundo, no mesmo modelo da do Chrisgol, dentro do módulo `valid` (D34), data-lake-api refeita; filtro de período só com os dias consolidados (D36) e visão do fundo INTERNAL (D35); falta teste de custo e testes no devcontainer; 28/10: carga da poça refeita pela D58 (execução diária com horário e liga/desliga por env var, desligada); 28/10: commitada na TS-5441 nas três pontas | TS-5441 nas três pontas (front era TS-4366, BFF TS-5044, data-lake-api TS-4815) |
| 02 | [Abertura de Rating](tasks/02-rating-breakdown.md) | data-lake-api, BFF, front, platform-cessao (régua) | D22 e D31 provisórias | viabilidade conferida (22/10): rating, VP e PDD por produto saem das views; produto em ~51% do VP; régua virá do platform-cessao por produto (D19); 27/10: implementada nos quatro repositórios (TS-5438, com a rota `GET /pdd/regua-vigente` no platform-cessao); 28/10: integrada na TS-5442 com os escopos da aba | TS-5438, TS-5442 (integração) |
| 03 | [Análise de Migração](tasks/03-migration-analysis.md) | data-lake-api, BFF, front | D21; D22 provisória (matriz na próxima versão) | faixas mensais integradas; 28/10: rota de datas integrada no BFF e no calendário do front, em alterações locais; build de desenvolvimento e verificações locais passaram, testes HTTP/navegador impedidos pelo ambiente; pagamento pendente da D21 | TS-5442 (integração) |
| 04 | [Monitoramento de Inconsistências: Performance de Pagamento, Lacunas de Parcelas e Análise Residual](tasks/04-inconsistency-monitoring.md) | data-lake-api, BFF, front | Residual: D59 a D66 tomadas; Performance: commitada (TS-5467), sem push, D76; Lacunas: D41, D72 | viabilidade conferida (27/10): as três saem das views `administradores_*`; taxa média fora por enquanto (D44); Lacunas sem o Fydd, pesadas (57 s num fundo) e com a liquidação para achar a parcela posterior paga (D41); 29/10: Análise Residual commitada nas três pontas (TS-5466), sem push; migration e carga desligadas; 29/10: Performance em espera (time de dados); Lacunas: D40, D42, D71, D73 e D74 tomadas; view por contrato testada | TS-5466 (Residual), TS-5467 (Performance) |

## Glossário

- **ECL (Expected Credit Loss):** nome em inglês usado nos campos financeiros
  do código para o PDD (Provisão para Devedores Duvidosos). Padronização pedida
  em 28/10/2026: `ecl`, `ecl_total`, `ecl_pv_ratio` e `ecl_rate` nos contratos
  da data-lake-api, do BFF e do front. Na tela, o rótulo continua **PDD**.
  Os adaptadores mantêm os nomes das colunas de origem e de persistência;
  a troca não exige alteração física de banco. Rotas, permissões e nomes
  existentes da funcionalidade permanecem com PDD. Desde 30/10/2026 (D80),
  todo o código do módulo `valid` da data-lake-api usa ECL, inclusive rotas
  (`/valid/ecl`), tabelas (`valid_ecl_*`) e variáveis (`CFG_VALID_ECL_*`); o BFF
  chama `/valid/ecl`. Seguem PDD: colunas do Redshift, `funds`, `portfolio`, as
  rotas do BFF para o front e o rótulo na tela.
- **VP (valor presente):** valor da parcela hoje, descontado pela taxa até o
  vencimento. O estoque do dashboard é a soma do VP.
- **PDD:** provisão para devedores duvidosos; não entra no VP, é coluna à
  parte.
- **Administrador (fonte):** quem manda os arquivos do fundo ao lake; coluna
  `source` das views.
- **Fechamento:** um dia com estoque no lake (`data_ref`). Na Mov. Estoque, o
  fechamento do mês é o último `data_ref` dele.
- **Baixa:** saída da parcela da carteira do fundo (liquidação pelo sacado,
  antecipação, recompra, glosa...). O valor de baixa é o que sai da carteira
  (valor no vencimento ou VP em carteira); ainda não é usado (D75).
- **Valor de liquidação:** o `vl_pago` da liquidação, o que o sacado pagou
  (D75, que substituiu a D46). É o que a Mov. Estoque soma como "Baixas" (D3)
  e o que a Performance de Pagamento mostra por faixa.
- **Valor no vencimento:** o `vl_vencimento` da liquidação, o que o sacado
  devia na data de vencimento da parcela (igual ao nominal). Pelo time de
  dados, `vl_pago = vl_vencimento + vl_juros − vl_ajuste`: o valor de baixa
  é o valor no vencimento mais juros de atraso menos desconto (P25).
- **Saldo inicial / estoque real:** VP no fechamento anterior / no fechamento
  do período.
- **Waterfall (cascata):** gráfico que parte do saldo inicial, soma aquisições
  e accrual, subtrai baixas e chega ao saldo final calculado.
- **Accrual de juros:** quanto o VP cresce com a passagem do tempo, porque a
  parcela fica mais perto do vencimento.
- **Taxa × prazo:** cálculo do accrual pela fórmula do próprio VP: VP ×
  ((1+taxa)^(dias/base) − 1).
- **Conferência:** diferença entre o saldo final calculado e o estoque real.
- **du / dc:** dias úteis / dias corridos. Base 252 usa du; bases 360 e 365
  usam dc.
- **Sortkey:** coluna pela qual o Redshift ordena a tabela no disco. Filtrar
  por ela (`data_ref`) faz a consulta ler só os blocos do período.
- **Roll-forward por parcela:** reconciliação que compara parcela a parcela
  dois fechamentos (quem ficou, quem entrou, quem saiu).
- **Rating do administrador (`faixa_pdd`):** classe de risco que o
  administrador dá ao contrato, com um % de PDD por classe. É a "visão do
  cliente" da Abertura de Rating.
- **Régua:** tabela do fundo que liga a faixa de dias de atraso ao rating e
  ao % de PDD. Não está nas views.
- **Faixa de atraso:** grupo de dias de atraso do contrato (em dia, 1–30,
  31–60 …). O atraso do contrato é o da parcela vencida mais antiga.
- **Matriz de rolagem (roll rate):** quantos contratos (e quanto VP) de cada
  faixa num fechamento foram para cada faixa no fechamento seguinte, ou
  saíram do estoque.
- **Efeito vagão (arrasto):** o % de PDD da parcela mais atrasada vale para o
  contrato inteiro e, quando a régua é por devedor, para todos os contratos
  do mesmo sacado. Ver [concepts.md](concepts.md#9-pdd-faixa-régua-e-efeito-vagão).
