# 12 — Lotes reais: buscar os lotes antes dos valores

- **Status:** **prioridade máxima** (passa na frente das outras, 14/10/2026);
  mapeada, aguardando ID da tarefa.
- **Repos:** platform-cessao. BFF e front não mudam.
- **Contrato:** a rota `GET /liquidacao/lotes/reais` continua recebendo os
  mesmos parâmetros e devolvendo o mesmo payload, inclusive
  `lotes_da_remessa`. Só muda como a cessão monta a resposta.
- Linhas de código contra `origin/master` `d72e01c` (13/10/2026).

## Conclusão

Separar "primeiro os lotes, depois os valores" **já é o que a listagem faz
para os valores** desde a TS-5184, e essa parte é barata: 0,48 s no trace
abaixo **[C]**. Fazer a soma em consultas separadas não ganha nada.

O ganho está em levar a mesma ideia para as duas partes que ainda não a
seguem, ambas por causa do **fundo** (o lote não tem fundo próprio, quem tem
é a parcela de cada pagamento):

1. **Lotes irmãos (`lotes_das_remessas`):** parte de todos os pagamentos das
   remessas da página e faz oito acessos por pagamento. É 74% do tempo de
   banco da listagem e a causa da maioria dos 500. **[C]**
2. **Filtro de fundo da página:** para saber se um lote é do fundo, procura
   entre **todos** os pagamentos de **cada** lote da janela (não só dos 20
   da página, por causa da contagem total). Sem filtro de produto, p50 de
   4,4 s e p95 de 94 s. **[C]**

## PR alternativo

O PR `feature/ajuste-rota-liquidacao-lote-real` mexe só na página (19% dos
500) e não nos irmãos (81%). Análise e recomendação em
[12-analise-pr-lotes-reais.md](12-analise-pr-lotes-reais.md).

## Evidência

Detalhe e consultas para repetir em
[evidencias/lotes-reais-datadog-2026-10-14.md](../evidencias/lotes-reais-datadog-2026-10-14.md).
Seis dias até 14/10, depois da réplica e do limite de 120 s:

- `GET /liquidacao/lotes/reais`: 749 chamadas, **146 com 500 (19,5%)**, todas
  por `statement_timeout` (o banco cancela a consulta em 120 s). Antes da
  réplica, eram 18% de 504 no BFF: o erro mudou de lugar, não diminuiu. **[C]**
- `lotes_das_remessas`: 342 execuções, **126 canceladas (37%)**, 4,3 h de
  banco. **[C]**
- Página sem produto: 85 execuções, 15 canceladas, 1,0 h. Com produto: 293
  execuções, p50 0,39 s, 3 canceladas, 0,5 h. **[C]**
- Trace `6acfda6000000000951f20fe386b54eb`: página 0,48 s, irmãos 120 s
  cancelados. **[C]**

## Como a listagem funciona hoje

`ServiceLiquidacao.get_lotes_reais_paginated`
(`cessao/api/liquidacao/service.py:1300`) faz duas consultas:

| Passo | Onde | O que faz |
|---|---|---|
| Página | `repository.py:632-784` | CTE `pagina` (consulta nomeada dentro do SQL) com os lotes da janela, ordenados e com `LIMIT`; `LATERAL` (subconsulta que roda uma vez por linha da página) soma `valor_pago` e junta os `proc_ids` só desses lotes |
| Irmãos | `repository.py:829-858`, chamado em `service.py:1347` | para cada `proc_id` da página, todos os lotes que essa remessa alimentou no fundo, para montar `lotes_da_remessa` |

Onde está o custo:

- **Fundo da página:** `_lote_tem_pagamento_do_fundo` (`repository.py:786`)
  é um `EXISTS` (teste "existe ao menos uma linha") sobre pagamento + parcela.
  Para um lote de outro fundo, o `EXISTS` não acha e percorre **todos** os
  pagamentos do lote. Como `count(*) OVER ()` (`repository.py:674`) conta o
  total da listagem, o teste roda para todos os lotes da janela, não só os
  da página. **[C]**
- **Soft delete:** o filtro global (`cessao/database/listeners.py:731`)
  injeta um `NOT EXISTS` por pagamento (parcela → contrato → processo
  deletado). Em `lotes_das_remessas` entra **duas vezes**, porque a query tem
  `Parcela` e `LiquidacaoPagamento`. **[C]**
- **Irmãos:** uma remessa grande (Mercato Libero) tem dezenas de milhares de
  pagamentos; a consulta lê cada um, a parcela e as duas checagens antes do
  `DISTINCT`. **[H]** O número de pagamentos por remessa nas execuções
  canceladas sai do `EXPLAIN` do passo 4a do SQL anexo.

## Proposta

SQL de cada passo, com `EXPLAIN` e checagem de equivalência, em
[anexos/sql/lotes_reais_lotes_antes_dos_valores.sql](../anexos/sql/lotes_reais_lotes_antes_dos_valores.sql).

### Visão em etapas (20/10)

O que deixa a listagem rápida não é quebrar em várias consultas: é cada
etapa custar pelo número de **lotes**, não de **pagamentos**. Um lote pode
ter dezenas de milhares de pagamentos; a janela tem bem menos lotes
**[H]** (passo 7 do SQL mede).

| Etapa | O que lê | Custo cresce com | Hoje |
|---|---|---|---|
| 1. Lotes da janela (data, produto, status) | só o lote | lotes da janela | já é assim |
| 2. Fundo de cada lote | um pagamento e a parcela dele | lotes da janela | todos os pagamentos dos lotes de outros fundos |
| 3. Filtro do fundo, ordem, total, `LIMIT` | resultado de 1 e 2 | lotes da janela | o total obriga a etapa 2 na janela inteira |
| 4. Valores e `proc_ids` da página | pagamentos dos 20 lotes | pagamentos da página | já é assim (0,48 s) |
| 5. Lotes de cada remessa (irmãos) | índice (remessa, lote), saltando de lote em lote | lotes da remessa | todos os pagamentos da remessa, com parcela e soft delete duas vezes |
| 6. Fundo dos irmãos | como a etapa 2 | lotes irmãos | junto com a 5 |

São três consultas: 1 a 3 numa só (o total e a ordem ficam no banco), 4 e
5-6. Depende de três coisas:

- **D11** para a etapa 2. Sem ela, a etapa 2 só fica barata com o fundo
  gravado no lote (opção (b) abaixo).
- ~~Índice composto `(liquidacao_processo_uuid, liquidacao_lote_id)` para
  saltar de lote em lote~~ **descartado em 20/10**: na réplica,
  `liquidacao_processo` tem uma linha por pagamento (802 milhões), então não
  há o que saltar. A etapa 5 lê os pagamentos da remessa, sem parcela e sem
  soft delete. **[C]**
- **Soft delete** só na etapa 4 (valores); fora das etapas que apenas
  identificam lotes (ver "Efeito do soft delete").

### Premissa: o lote tem um fundo só (D11)

Os dois atalhos abaixo valem se cada lote real tiver pagamentos de um único
fundo. É o desenho do fechamento por chave (produto, originador, fundo,
origem) e do lote vigente, mas o modo por proc_id ainda pode juntar fundos
num lote (a D3 só entra na tarefa que mudar as linhas `proc:`). **[H]** O
passo 1 do SQL responde: lista os lotes dos últimos 90 dias com mais de um
fundo.

### 1. Lotes irmãos em duas etapas

Mesma ideia da sua consulta 1: achar os lotes primeiro, olhar o fundo depois,
e só nos poucos lotes encontrados.

- **Etapa A:** `liquidacao_processo` por `proc_id` → `liquidacao_pagamento`
  por `liquidacao_processo_uuid` → `DISTINCT (proc_id, lote_id)`. Sem
  parcela e sem soft delete (opção `incluir_processos_deletados` do
  listener, `listeners.py:570`): dois acessos por índice por pagamento, em
  vez de oito.
- **Etapa B:** dos lotes da etapa A (dezenas), ficam os do fundo, olhando
  **um** pagamento de cada (`LIMIT 1`).

Medido na réplica em 20/10 (fundo 209): **> 120 s** na consulta atual contra
**0,17 s** (5,3 s frio) nas duas etapas. **[C]** O índice composto pensado
antes foi descartado (ver "Visão em etapas").

### 2. Fundo da página olhando um pagamento

Trocar o `EXISTS` por "o fundo do primeiro pagamento do lote é o da
listagem": um acesso por índice em `liquidacao_lote_id` e um pela chave da
parcela, por lote da janela, em vez de varrer os pagamentos dos lotes de
outros fundos. A página volta a ser a sua consulta 1 mais esse teste. O
`LATERAL` dos valores (sua consulta 2) fica como está.

### Efeito do soft delete nas respostas

Tirar o soft delete das duas checagens muda a resposta só num caso: lote
cujos pagamentos daquela remessa (ou do fundo) são **todos** de contratos
deletados. Hoje ele some; depois aparece (com `valor_pago` e
`qtd_registros` zerados pelo `LATERAL`, que mantém o soft delete). **[H]**
raro; o passo 5 do SQL compara as duas versões numa chamada real e precisa
sair vazio. Se não sair, a etapa B ganha a checagem de soft delete, que
custa pouco por rodar só nos lotes já encontrados.

### Se a D11 disser que há lote com mais de um fundo

O atalho de "um pagamento" fica errado. Opções, em ordem de custo:

- **(a)** manter o `EXISTS` do fundo, mas sem soft delete: ganha menos;
- **(b)** coluna `fundo_id` em `liquidacao_lote_processo` (migration nova,
  backfill e gravação em todos os pontos que criam lote, inclusive o atlas):
  a página fica toda no índice `(fundo_id, data_criacao)`. Soma ~16 h e
  conflita com a D3, que define o fundo do lote no modo por proc_id.

### Onde fica o código

O `refact.py` ainda não está na `master` (só na branch da TS-5377). Como esta
tarefa passa na frente, a mudança vai direto em
`RepositoryLiquidacao.get_lotes` e `lotes_das_remessas`. A rota só é usada
pelo BFF (2.198 chamadas em 30 dias, todas `python-httpx`) **[C]**, então
não há fluxo legado a preservar. O merge com a TS-5377 não conflita: ela não
mexe na listagem de lotes reais.

## Proposta da DBA (20/10)

A DBA mandou duas consultas:
- **Query 1:** página e total de lotes, com o fundo descoberto por um
  pagamento (`LATERAL ... LIMIT 1`) e o soft delete num `EXISTS` com
  `OFFSET 0`. Leva ~90 ms com cache quente e ~6 s frio.
- **Query 2:** totais de um lote (valor, quantidade, `proc_ids`). Custa ~0,014
  ms por pagamento quente e ~1,2 ms frio, e propõe 16 fatias paralelas para
  lotes grandes.

**Atende em parte a tela.** Comparação com o que a tela usa (front
`d23eaef6`, `manual-reconciliation.ts` e `batches.service.ts`; cessão
`get_lotes`, `repository.py:632`):

| A tela usa | Proposta | Situação |
|---|---|---|
| Fundo obrigatório | sim | ok, mas a D11 foi revista em 20/10: há lote multifundo (D21) |
| Vários produtos | um produto, comentado | trocar por `IN` |
| Vários status | não tem | falta |
| Período | sim | ok |
| Filtro "lotes desta remessa" (`proc_id`, ignora a data) | não tem | falta |
| Ordenação por 6 campos | fixa (data desc) | falta |
| Página de 5 (`per_page`) | `LIMIT 20` fixo | parametrizar |
| Total de lotes | `count(*) OVER ()` | ok |
| Valor, quantidade, `proc_ids` | query 2 por lote | mesma conta do `LATERAL` atual; virar rota por lote muda o contrato |
| Chip de lotes da remessa (`remittance_batch_ids`) | não tem | falta; é a origem de 100 dos 124 erros 500 |

- **A query 1 confirma o caminho da proposta 2 desta tarefa** (fundo por um
  pagamento). Resolve os 500 da página sem produto (23 de 124), depois dos
  ajustes da tabela.
- **A query 2 não ganha nada** sobre o `LATERAL`. Com cache frio, um lote de
  162 mil pagamentos leva 199 s, acima dos 120 s da réplica, e derruba a
  página. As 16 fatias paralelas abririam 16 conexões por requisição, o que
  não serve numa rota de tela.
- **Falta levar à DBA:** a consulta dos lotes irmãos (proposta 1). O índice
  composto saiu da lista (ver "Medição na réplica").
- **Em aberto (pergunta ao Pietro em 20/10):** valor de lote gigante:
  1. somar na hora (como hoje);
  2. carregar por linha (muda BFF e front);
  3. gravar o total no lote.

  Recomendação: 1 agora, 3 depois.

## Medição na réplica (20/10)

Detalhe em [evidencias/lotes-reais-replica-2026-10-20.md](../evidencias/lotes-reais-replica-2026-10-20.md).
Chamada que falhou hoje: fundo 209, dia 20/10, sem produto.

| Parte | Atual | PR | Proposta |
|---|---|---|---|
| Página (fundo pelo 1º pagamento) | > 60 s | > 60 s | **0,1 s** |
| Irmãos (duas etapas) | > 120 s | não mexe | **0,17 s** (5,3 s frio) |

- **Contraexemplo da D11:** o lote 1836143 (produto 1637, por proc_id,
  15/10) tem 78 pagamentos do fundo 836 e 1 do fundo 869. É o único entre
  os 215 lotes por proc_id de 30 dias. Com o atalho, ele some da listagem
  do fundo 869. **D11 revista em 20/10** (lote pode ter mais de um fundo);
  o tratamento na listagem está na **D21**. **[C]**
- **Dois mundos de remessa:** em 7 dos 14 fundos do dia (~296 mil dos ~345
  mil pagamentos), cada pagamento tem a sua remessa. Ali os irmãos são o
  próprio lote, e a página carrega um `proc_id` por pagamento (211 mil no
  fundo 36). **[C]**
- **Lote gigante continua estourando** com a proposta: no fundo 36 (11
  lotes, 211 mil pagamentos), página 0,04 s, soma e contagem 0,12 s, mas o
  `proc_id` de cada pagamento leva 11,8 s, e o soft delete leva os valores
  e os irmãos a mais de 120 s. O custo é por pagamento, não por lote: é a
  pergunta em aberto acima (somar na hora × gravar no lote). **[C]**

## Próximos passos (20/10)

1. ~~**D21 (Pietro)**~~ decidida em 20/10: opção (a).
2. ~~**Conferir a premissa da D21 (a)**~~ feito em 20/10: 85 lotes por chave, nenhum multifundo. Era: lote por chave não mistura
   fundos (fundos distintos lendo todos os pagamentos de um dia, por fundo,
   para caber no limite de tempo).
3. **TS-5383** (branch `refact/TS-5383-melhora-consulta-lotes-reais`), **publicada em 20/10** (commits `61576d3` e `66318bc`; a `-sdbx` leva os dois por cherry-pick, porque o merge arrastava 18 commits da `master` que a `sandbox` não tem, com conflito no `entrypoint.sh`). Só código: sem migration, índice, variável ou mudança no BFF e no front; a rota já usa a réplica (números na evidência):
   página com o fundo pelo 1º pagamento e a checagem da D21; irmãos em duas
   etapas, sem parcela e sem soft delete. Mesmo contrato. Testes de
   repositório, validação local e depois `EXPLAIN` na réplica com os fundos
   209 (remessa por pagamento) e 26 (remessa de arquivo).
4. **De onde vêm os 500 dos irmãos:** fundo de cada chamada que falhou (log
   "Buscando lotes reais..." pelo trace). Diz quanto a TS-5383 resolve
   sozinha.
5. **Lotes gigantes (fundos 36 e 3), tarefa nova:** o custo é por
   pagamento. Decidir (i) buscar os pagamentos do lote pelo `lote_id` e
   parar de mandar um `proc_id` por pagamento (muda BFF e front); (ii) valor
   e quantidade somados na hora sem soft delete, ou gravados no lote.
6. **Responder ao autor do PR** com os números: não resolve a chamada de
   hoje; o diagnóstico do semi-join estava certo.

## Fora do escopo

- Carregar os lotes irmãos sob demanda (proposta 1 da
  [tarefa 04](04-performance-listagens.md)): muda o contrato com o front.
- Lotes fake, `pagamentos/query` e métricas: continuam na tarefa 04.

## Riscos

- **D11:** se houver lote multi-fundo, o atalho erra a contagem e a lista de
  irmãos. Por isso o passo 1 do SQL vem antes de qualquer código.
- **Plano do Postgres:** o subselect com `LIMIT 1` depende do índice em
  `liquidacao_pagamento.liquidacao_lote_id` (declarado no model; conferir no
  banco com o passo 2 do SQL).
- **Réplica:** os testes de `EXPLAIN` na réplica refletem produção, mas o
  `EXPLAIN ANALYZE` executa a consulta; rodar com `statement_timeout`.

## Validação

1. Passos 1 e 2 do SQL antes de abrir branch.
2. `EXPLAIN (ANALYZE, BUFFERS)` antes e depois (passos 3, 4a e 4b) com os
   parâmetros de uma chamada cancelada, anexados aqui e revisados com a DBA.
3. Passo 5 vazio para três remessas grandes (uma do Mercato Libero).
4. Testes de repositório: lote de outro fundo fora da página e dos irmãos;
   remessa partida em dois lotes; remessa partida entre dois fundos; lote com
   processo deletado; contagem total igual à de antes.
5. Em produção, dois dias úteis depois do deploy, repetir as consultas da
   evidência. Meta: zero 500 por `statement_timeout` e p95 da rota abaixo de
   10 s.

## Estimativa

| Parte | Dev | Validação |
|---|---|---|
| SQL de premissa e `EXPLAIN` com a DBA | 2 | 4 |
| Irmãos em duas etapas | 5 | — |
| Fundo da página | 3 | — |
| Testes de repositório e serviço | 5 | — |
| Merge na `-sdbx`, deploy e medição | 1 | 4 |
| **Total** | **16** | **8** |

**24 h.** Se a D11 levar à opção (b), ~40 h.
