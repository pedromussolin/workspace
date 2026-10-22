# GMUD — TS-5383 e hotfix da TS-5377: lotes reais, listagem mais rápida e detalhe do lote pelo `lote_id`

> **Status (22/10/2026, ~18:00 UTC):** já executada em produção. Registrar
> como retroativa. A TS-5383 subiu em 20/10 às 23:05 UTC; o hotfix da TS-5377,
> em 21/10 às 00:33 UTC (20/10 às 21:33 em Brasília).
>
> **Falta:**
> - a medição de 23/10, que fecha os dois dias úteis previstos (22 e 23/10);
>   o que está aqui vai até 22/10 ~18:00 UTC;
> - os testes (preenchidos pelo orquestrador);
> - prioridade e links do Jira;
> - decidir o que fazer com a cauda lenta que a medição mostrou (seção Risco).
>
> A fase 1 da TS-5377 foi no mesmo deploy da TS-5383 e tem GMUD própria
> ([gmud-ts-5377-fase1.md](gmud-ts-5377-fase1.md)); não é repetida aqui.

Tipo: Mudança não programada (já executada em 20/10/2026)

## Summary

platform-cessao, BFF e front: lotes reais — consulta mais rápida da listagem
e pagamentos/rejeitados do lote buscados pelo `lote_id`

## Descrição

**Contexto**

*TS-5383, listagem de lotes reais*
- **Antes** (13/10 23:05 a 20/10 23:06 UTC, 7 dias, Datadog): a rota
  `GET /liquidacao/lotes/reais` da cessão teve 837 chamadas e **180 erros 500
  (21,5%)**, todos por `statement_timeout` (limite de 120 s por consulta, que
  o banco aplica cancelando-a). Já era com a réplica de leitura (cópia do
  banco que só aceita leitura, TS-5279): o erro não saiu do lugar.
- **Causa** (o lote não tem fundo próprio; o fundo está na parcela de cada
  pagamento):
  - lotes irmãos (`lotes_das_remessas`, os outros lotes que a mesma remessa
    gerou): partia de todos os pagamentos das remessas da página, com parcela
    e checagem de soft delete (contrato apagado, marcado com `data_delete`)
    duas vezes. Eram 100 dos 124 erros (81%) medidos até 20/10 18:50 UTC;
  - fundo da página: o `EXISTS` virava um semi-join (junção que só testa
    existência) que lia todas as parcelas do fundo. Eram 23 dos 124 (19%), na
    página sem filtro de produto.
- **Réplica, 20/10** (parâmetros de uma chamada que tinha falhado): página
  de mais de 60 s para 0,4 s; irmãos de mais de 120 s para 0,1 s.

*Hotfix da TS-5377, detalhe do lote real*
- Com a TS-5383, a listagem do fundo 209 voltou a abrir, e o detalhe do lote
  1837116 quebrou. É um produto com uma remessa por pagamento: o lote tem
  1.744 `proc_id` (identificador da remessa).
  - a tela mandava a lista inteira na URL, que estourava (erro 414, URL longa
    demais), e mostrava um botão de CNAB por remessa;
  - passar a lista para dentro da cessão não bastava: com os 1.744 `proc_id`
    num `IN`, o Postgres estimou ~13 mil processos por `proc_id` e varreu as
    três tabelas (mais de 60 s na réplica).

**O que muda**

- **platform-cessao, TS-5383** (PR #2678, commits `61576d3d9` e `66318bc7f`,
  pela `release/20261020`; arquivo `cessao/api/liquidacao/repository.py`):
  - **fundo da página:** o lote é do fundo se a parcela do 1º pagamento é do
    fundo (dois acessos por índice por lote). Só nos produtos que fecham por
    `proc_id` (`fechar_lote_por_proc_id`), que podem misturar fundos num lote
    (D21), confere todos os pagamentos. O soft delete sai dessa escolha de
    lotes; os valores da página continuam com ele;
  - **lotes irmãos em duas etapas:** primeiro, um `LATERAL` (subconsulta que
    roda uma vez por linha) por remessa, só em `liquidacao_processo` e
    `liquidacao_pagamento`, sem parcela e sem soft delete; depois, numa
    consulta separada, o fundo de cada lote achado;
  - mesmo contrato (parâmetros e payload). Sem migration, índice ou variável.
- **platform-cessao, hotfix** (PR #2684, commit `03f6683e0`, pela mesma
  release; `repository.py`, `service.py` e `viewer.py`):
  - `GET /liquidacao/pagamentos/query` e `GET /liquidacao/pagamentos/rejeitados`
    aceitam só o `lote_id` (antes exigiam `proc_id` ou `chave`). A cessão
    descobre as remessas do lote (`remessas_do_lote`): são as mesmas que a
    listagem devolve em `proc_ids`;
  - filtro das remessas: até 20 mantém o `proc_id IN`; acima disso resolve os
    `uuid` dos processos por `LATERAL`, uma remessa por vez, e filtra pelo
    `uuid` (`MAX_REMESSAS_NO_IN = 20`). Vale para rejeitados, métricas do lote
    e a consulta da planilha de rejeitados;
  - quem ainda manda a lista de `proc_id` continua funcionando.
- **BFF** (PR #214, commit `07276dc`, pela `release/20261020` do BFF): a rota
  de exportação de rejeitados aceita `lote_id` (`proc_id` passa a opcional) e
  repassa à cessão. A rota de pagamentos já repassava `lote_id`; só a
  descrição mudou.
- **Front** (PR #226, commits `68ae8528` e `54e75747`, pela
  `release/20261020` do front):
  - tabela de pagamentos (ativos e rejeitados) e exportação vão só com o
    `lote_id`;
  - acima de 3 CNABs, um botão abre um modal com busca por `proc_id` e "ver
    mais" (`cnabInlineLimit = 3`).
- **Para master:** cessão pela #2682 (`2eb8faacd`, com a fase 1) e pela #2686
  (`bcf84478d`); BFF pela #216 (`ccb8306`); front pela #228 (`71f34a58`). As
  cópias para a sandbox (#2685, #215, #227) não entram nesta GMUD.

**O que não muda**

- **Contrato da listagem:** parâmetros, payload e `lotes_da_remessa`. A rota
  segue só na réplica (`@consulta_replica`, vale também para as duas rotas do
  detalhe) e com o limite de 120 s por consulta (constante no código).
- **O custo por pagamento continua:**
  - valores do lote (soma, contagem e `proc_ids`, com soft delete por
    pagamento): é o que ainda leva 62 s no pior caso medido (fundo 26);
  - a contagem da paginação dos pagamentos do lote (39 s num lote grande,
    trace de 21/10 17:42 UTC), sem alteração;
  - a lista `proc_ids` que a listagem devolve em cada lote.
- **Fundos 36 e 3 (lotes gigantes, 211 mil pagamentos):** seguem fora. Não
  houve nenhuma chamada desses fundos nos 7 dias antes nem desde o deploy
  (log "Buscando lotes reais...").
- **Rejeitados de remessa sem pagamento ativo no lote:** a lista de remessas
  sempre saiu dos pagamentos ativos do lote (antes, da listagem; agora, de
  `remessas_do_lote`). Igual a antes.
- Lotes fake, fechamento, worker, filas, banco (sem migration) e as
  variáveis. No argocd só mudou a tag da imagem.

## Prioridade

Medium (a confirmar com o usuário). A tela de lotes reais falhava em 1 de
cada 5 cargas, mas sem perda de dado e com contorno (recarregar).

## Link Tarefa

- `<link do Jira da TS-5383>`
- `<link do Jira da TS-5377>`

## Risco

Médio. O que pode dar errado, o que acontece e o que segura:

- **Lote fechado por chave com mais de um fundo (premissa da D21):** o lote
  aparece só no fundo do 1º pagamento e some da listagem do outro. Segura:
  nos produtos que fecham por `proc_id` a checagem é completa (o lote
  multifundo 1836143 aparece nos dois fundos, na réplica). **A confirmar:** a
  premissa foi conferida só em 20/10 (85 lotes, nenhum multifundo); o
  histórico não coube no tempo da réplica. Também a confirmar se algum
  produto já deixou de fechar por `proc_id` depois de criar lote misturado
  (a regra lê o valor atual de `fechar_lote_por_proc_id`).
- **Lote cujos pagamentos são todos de contratos apagados:** passa a aparecer
  na listagem, com valor e quantidade zerados (antes sumia). Raro; **a
  confirmar** com dados reais.
- **Equivalência com a versão anterior:** os testes novos da TS-5383 conferem
  o texto do SQL com sessão falsa, não dados. **A confirmar:** comparação do
  resultado antigo × novo em chamadas reais; hoje há as medições da réplica
  (lote multifundo nos dois fundos) e a produção sem erro.
- **Cauda lenta que continua (medido em produção):**
  - 16 das 199 chamadas depois do deploy passaram de 8 s (8,0%; antes 83 de
    657, 12,6%); máximo 108 s, perto do limite de 120 s por consulta;
  - quem leva é a listagem de fundo com remessa de arquivo e lotes de dezenas
    de milhares de pagamentos com cache frio (fundo 26: valores 62 s, irmãos
    46 s, na mesma chamada). São duas consultas em sequência: a soma pode
    passar de 120 s e virar 504 no BFF (o BFF espera 120 s). Não houve;
  - a meta da tarefa 12 era p95 abaixo de 10 s: **não atingida** (20,6 s). A
    de zero 500 por `statement_timeout`, sim, até agora.
  - Segura: nada além dos limites. Sem variável para desligar; a correção é
    código (valores por pagamento e irmãos, tarefa 12, passo 5).
- **Hotfix, ordem errada de deploy:** front ou BFF na frente da cessão manda
  `lote_id` sem `proc_id`, e a cessão antiga responde 400 ("Informe proc_id
  ou chave" nos pagamentos; `proc_id` obrigatório nos rejeitados e na
  exportação). A cessão na frente é inofensiva: aceita os dois formatos.
- **Hotfix, custo por pagamento do lote:** `remessas_do_lote` lê todos os
  pagamentos do lote para achar as remessas. Em produção: 37 execuções, p95
  44 ms, máximo 123 ms. Num lote de 211 mil pagamentos (fundo 36) o passo
  equivalente levou 11,8 s na réplica.
- **CNAB de remessa sem arquivo:** o modal lista todos os `proc_id` do lote, e
  numa remessa por pagamento o download pode dar 404. **A confirmar:** 3
  respostas 404 em `real-batches/cnab` (2 antes do hotfix, 1 depois), causa
  provável remessa sem CNAB salvo.
- **Deploy da cessão reinicia API e workers** (mesma imagem), incluindo o
  worker de fechamento: tratado na GMUD da fase 1 (0 reenvios por queda,
  `attempt > 1`, desde a fase 1, até 21/10 14:10 UTC).

## Impacto

- **Tela/usuário:**
  - listagem de lotes reais: mesma tela, sem erro 500 desde o deploy (0 de
    199 chamadas);
  - detalhe do lote real: abre em lote com milhares de remessas (o lote
    1837116, 1.744 remessas, respondeu 5 vezes com 200, máximo 5,3 s);
  - CNABs: acima de 3, um botão abre o modal.
- **Banco:** só leitura, na réplica. Sem migration, índice ou tabela. As três
  consultas antigas da listagem não rodam mais (zero execuções depois de
  20/10 23:10 UTC); entram quatro novas, mais três do detalhe do lote.
- **Infra:** sem pod, fila ou variável nova. No argocd, uma linha por values
  (tag da imagem).
- **Deploy:**
  - cessão: reinício de API e workers, sem indisponibilidade medida (nenhum 4xx
    ou 5xx nas rotas de lotes e de pagamentos desde 20/10 23:05 UTC);
  - BFF e front: troca de pod, sem indisponibilidade medida;
  - o hotfix mexe em três serviços: ver a ordem em Plano de implantação.

## Plano de implantação

Como foi feito, horários em UTC (Brasília + 3 h).

**TS-5383 (só a cessão)**
1. **20/10 22:28** PR #2678 na `release/20261020` (merge `925ae44e4`); 22:47 a
   fase 1 (#2683); **22:53** release para a `master` pela #2682 (`2eb8faacd`).
2. **20/10 23:05:08** argocd da cessão, tag `prod-2eb8faa` (commit
   `f846929`). API e workers sobem juntos (mesma imagem).
   - Conferido no Datadog: primeira requisição de `prod-2eb8faa` às 23:06:05;
     última de `prod-f19ef2c` às 23:06:32.
   - Primeira listagem pelo código novo às 23:08 (fundo 40, depois 209 e 26),
     200. As quatro consultas novas aparecem; as três antigas não rodam mais
     depois de 23:10.

**Hotfix da TS-5377 (cessão, BFF e front)**
3. **21/10 00:19** os três PRs do hotfix na `release/20261020` de cada repo
   (cessão #2684, BFF #214, front #226); **00:24** releases para a `master`:
   BFF #216 (`ccb8306`), front #228 (`71f34a58`), cessão #2686
   (`bcf84478d`).
4. **21/10 00:33** argocd, nos três repos, em 8 segundos: cessão `31590c6`
   (`prod-bcf8447`, 00:33:14); front `f203cdb` (`prod-71f34a5`, nos três
   values: portal e as duas variantes de marca, 00:33:19); BFF `f12247f`
   (`prod-ccb8306`, 00:33:22).
   - **A ordem segura é cessão, BFF, front.** Os três commits foram juntos;
     a cessão foi a primeira, e os pods novos trocam em minutos. Nenhum 4xx
     ou 5xx nas rotas na janela.
   - Cessão `prod-bcf8447`: primeira requisição 00:34:10; última de
     `prod-2eb8faa` 00:34:38.
   - BFF `prod-ccb8306`: primeiros spans no intervalo das 00:30 (23 spans; a
     `prod-a1d5abd` chegou às 23:00–23:10 e sai ali).
   - Front: sem span do front antes da `prod-f7bb2d8`. Confirmado por via
     indireta, no BFF: a última chamada de pagamentos com `proc_id` na URL é
     de 20/10 entre 23:00 e 24:00; as com `lote_id` e sem `proc_id` começam
     na hora seguinte (33 depois, todas 200).
5. **Acompanhamento:** rota de lotes reais e rotas de pagamentos (cessão e
   BFF), 4xx e 5xx, e as consultas por `resource_hash` (ver Evidências).

## Plano de Rollback

Vale para **hoje** (22/10). Voltar a imagem desfaz mudança de outros; por isso
o caminho é `git revert` do merge e um deploy novo, por repo.

**O que subiu depois e entra no caminho**
- **Cessão:** `prod-fb6f409` (21/10 20:11 UTC, PR #2677, "onda 6", de outro dev),
  mais a variável `CELERY_MAX_MEMORY_PER_CHILD` nos values, e o mesmo tag no
  segundo ambiente de produção do argocd da cessão (a confirmar, ver
  Evidências). Voltar a imagem para `prod-bcf8447` desfaz o PR #2677
  (`emissores/registro.py`, `parsers/padrao/parsers.py`, `utils/monitor.py` e
  o `entrypoint.sh`), e a variável ficaria sem efeito. Voltar para
  `prod-f19ef2c` desfaz também a fase 1, a TS-5383 e o hotfix.
- **BFF:** `prod-bb877db` (21/10 22:29 UTC, release do portal, TS-5394), com o
  merge da `master`. Voltar a imagem desfaz a release inteira.
- **Front:** `prod-f7bb2d8` (mesma release). O hotfix foi portado à mão para a
  estrutura nova (`features/`), e a versão atual **depende dele**: a tabela de
  pagamentos e a exportação mandam só o `lote_id`. Voltar a imagem desfaz a
  release inteira.
- A `release/20261022` (TS-5418, callback de uma marca) ainda não está em
  produção; não mexe em `cessao/api/liquidacao`, então não atrapalha o revert.

**O que a versão atual ainda depende do hotfix**
- **Front** (`data-access/payments.service.ts`, `payments-table`): manda só
  `lote_id` para pagamentos e para a exportação. Sem o hotfix da cessão, dá
  400 nas duas.
- **BFF:** a exportação de rejeitados por `lote_id` (precisa do hotfix da
  cessão). Os pagamentos pelo BFF funcionam com ou sem o hotfix dele.
- **Cessão:** nada na `master` depende do hotfix além do front e do BFF.

**Rollback do hotfix** (volta o erro 414 e o botão de CNAB por remessa em lote
com milhares de remessas, como no lote 1837116). Ordem inversa do deploy:
1. **Front:** commit novo desfazendo a mudança na estrutura atual (volta a
   mandar `proc_ids` e o botão de CNAB por remessa). **Não há `git revert`
   limpo:** o revert do merge `71f34a58` na `master` atual dá conflito em 5
   arquivos de `features/` e num arquivo apagado de `pages/` (testado numa
   worktree destacada). Deploy nos três values do front.
   - Aba aberta com o front novo: o commit `65ea4633` da release do portal
     manda a aba recarregar ao abrir uma tela (a confirmar no teste).
2. **BFF (opcional):** `git revert -m 1 ccb8306` aplica sem conflito nos
   arquivos de código; conflita só no arquivo de teste (`test_business_listagem.py`), que
   a release do portal também mexeu. Só depois do passo 1: sem ele, a
   exportação do front novo daria 422.
3. **Cessão:** `git revert -m 1 bcf84478d` (6 arquivos, só em
   `cessao/api/liquidacao` e testes; aplica limpo na `master` atual, testado).
   Deploy: nova imagem e tag no argocd da cessão.

**Rollback da TS-5383** (só a cessão; a rota volta a falhar em ~1 de cada 5
cargas): `git revert -m 1 925ae44e4`. **Conflita** com o hotfix no
`repository.py`. Dois caminhos:
- reverter o hotfix primeiro (passos acima) e em seguida a TS-5383: limpo,
  6 arquivos em `cessao/api/liquidacao` e testes (testado);
- ou resolver o conflito à mão mantendo o hotfix.

Não há como desligar a TS-5383 sem deploy (sem variável nem chave).

**O que fica para trás:** nada de dado, fila, Redis ou migration. Sem esforço
no banco.

**Depois de qualquer rollback:** conferir no Datadog que as consultas antigas
(`3afbd330f1bd4d7f`, `44a7a7211a2af67b`, `35a91cd19cdc2168`) voltam a rodar e
que a listagem e o detalhe respondem 200.

## Evidências de validação

- **Testes:** <preenchido pelo orquestrador>
  - commits que a GMUD precisa testados: cessão `2eb8faacd` e `bcf84478d`,
    BFF `ccb8306`, front `71f34a58`;
  - testes novos nos commits (contados nos diffs): TS-5383, 5 (SQL com sessão
    falsa); hotfix, 15 na cessão, 3 no BFF e ao menos 14 no front.

Consultas de produção abaixo: Datadog, `env:production`, até 22/10 18:01 UTC.
Durações do APM vêm em nanossegundos, convertidas. Os percentis do Datadog são
aproximados. Spans de banco podem ser amostrados; as contagens de chamadas
vêm dos spans da rota (completos nesta janela).

**Quando cada versão atendeu** (cessão, spans `flask.request`)

| Versão | De (UTC) | Até (UTC) | Leva |
|---|---|---|---|
| `prod-f19ef2c` | 19/10 21:45 | 20/10 23:06:32 | antes de tudo isto |
| `prod-2eb8faa` | 20/10 23:06:05 | 21/10 00:34:38 | TS-5383 e fase 1 |
| `prod-bcf8447` | 21/10 00:34:10 | 21/10 20:13:39 | hotfix |
| `prod-fb6f409` | 21/10 20:13:22 | em uso | PR #2677 de outro dev |

BFF: `prod-a1d5abd` ~23:05 de 20/10, `prod-ccb8306` ~00:33 de 21/10,
`prod-bb877db` ~22:30 de 21/10. Front: sem span até a `prod-f7bb2d8`
(~22:30 de 21/10); ver o passo 4. Os commits `61576d3d9`, `66318bc7f`,
`03f6683e0` (cessão), `07276dc` (BFF), `68ae8528` e `54e75747` (front) são
ancestrais das versões de produção (`git merge-base --is-ancestor`), e a
`03f6683e0` não está na `prod-2eb8faa`.

**TS-5383: `GET /liquidacao/lotes/reais` (cessão)**

| | Antes: 13/10 23:05 a 20/10 23:06 UTC (7 dias) | Depois: 20/10 23:06 a 22/10 18:01 UTC (1,8 dia) |
|---|---|---|
| Versões | `prod-d72e01c`, `prod-3ea7d5f`, `prod-f19ef2c` | `prod-2eb8faa`, `prod-bcf8447`, `prod-fb6f409` |
| Chamadas | 837 (~120 por dia) | 199 (~112 por dia) |
| Erros 5xx | **180 (21,5%)** | **0** |
| p50 (sucesso) | 0,34 s | 0,17 s |
| p95 (sucesso) | 50,8 s | 20,6 s |
| Máximo (sucesso) | 171,6 s | 108,1 s |
| Chamadas acima de 8 s | 83 de 657 (12,6%) + os 180 erros | 16 de 199 (8,0%) |
| Tempo de servidor por chamada (média) | 32,9 s | 3,5 s |

Por dia (UTC, depois do deploy), todas 200:

| Dia | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 20/10, 23:06 a 24:00 (`prod-2eb8faa`) | 19 | 0,49 s | 1,5 s | 4,6 s |
| 21/10 | 146 | 0,10 s | 19,4 s | 108,1 s |
| 22/10, até 18:00 | 34 | 0,14 s | 24,2 s | 58,2 s |

- Versão imediatamente anterior (`prod-f19ef2c`, 19/10 21:45 a 20/10 23:06):
  170 chamadas, 28 com 500 (16,5%).
- **Falta 23/10.** A medição completa de dois dias úteis fecha com 23/10;
  repetir as consultas abaixo e anexar.
- Ressalva: o volume é pequeno e em rajadas (em 21/10 às 17:39 UTC foram 22
  chamadas do fundo 26 em 20 s, repetições de uma mesma tela).

Banco (`service:postgres`, instância da cessão), por `resource_hash`:

| Consulta | Antes (7 dias) | Depois (1,8 dia) |
|---|---|---|
| Irmãos | `3afbd330f1bd4d7f`: 377 execuções, **140 canceladas (37%)**, média 47,2 s, 4,9 h de banco | `788d1d5df137d8b` (remessas) e `db8a1f03fb515cca` (fundo): 98 execuções cada, **0 canceladas**, média 2,4 s, 3,9 min; máximo 45,9 s |
| Página sem produto | `44a7a7211a2af67b`: 135 execuções, 35 canceladas (26%), média 46,5 s | `9cc782411e60f129` (por exclusão): 47 execuções, 0 canceladas, média 2,3 s, máximo 31,5 s |
| Página com produto | `35a91cd19cdc2168`: 365 execuções, 2 canceladas, média 6,0 s | `4856ef7a427ac6f6`: 81 execuções, 0 canceladas, média 4,1 s, p95 30,8 s, máximo 62,2 s |

- As três consultas antigas: zero execuções depois de 20/10 23:10 UTC.
- A página com produto já era a parte boa; a cauda dela (62 s) é a soma dos
  valores em lote de remessa de arquivo (trace `6ad8f8d400000000d08ba98b449c07b7`,
  fundo 26: página 62 s, irmãos etapa 1 46 s, etapa 2 3 ms; 108 s no total).

**Hotfix: rotas do detalhe do lote real**

| Rota | Antes: 13/10 23:05 a 21/10 00:34 UTC | Depois: 21/10 00:34 a 22/10 18:01 UTC |
|---|---|---|
| Cessão `GET /liquidacao/pagamentos/query` | 123 chamadas, todas 200; p50 0,17 s; p95 27,9 s; máx 36,0 s | 55 chamadas, todas 200; p50 0,31 s; p95 19,1 s; máx 39,6 s |
| BFF `GET /operations/liquidation/payments` | 66 chamadas, todas 200; p50 0,39 s; p95 5,5 s; máx 31,9 s | 39 chamadas, todas 200; p50 0,49 s; p95 6,2 s; máx 6,8 s |

- **O hotfix não mudou a latência típica e não era esse o objetivo:** ele faz o
  detalhe abrir em lote com milhares de remessas. O erro 414 não aparece no
  Datadog (a URL é recusada antes do BFF); a evidência do estado anterior é a
  de 20/10 (`evidencias/lotes-reais-replica-2026-10-20.md`).
- Lote 1837116 (1.744 remessas): 5 chamadas no BFF `prod-ccb8306`, todas 200,
  p95 1,1 s, máximo 5,3 s.
- Rejeitados pela tela (`rejected=true`): 3 chamadas em `prod-ccb8306`
  (máx 0,53 s) e 3 em `prod-bb877db` (máx 0,22 s), todas 200.
- **Sem chamada em produção:** `GET /liquidacao/pagamentos/rejeitados` (cessão)
  e `payments/rejected/export` (BFF), nos 9 dias. A exportação só tem teste
  automatizado e a medição da réplica.
- Consultas novas do hotfix: `f69e5a3cd0bc3c0d` (resolve os `uuid` por
  remessa): 14 execuções, máximo 24,6 ms; `3a689adb9d89624`
  (`remessas_do_lote`): 37 execuções, p95 44 ms, máximo 123 ms. No trace
  `6ad8f99100000000c5a7b01b1a0ad29d` (lote 1837459, 39,6 s): `remessas_do_lote`
  123 ms; a contagem da paginação, que não mudou, 39,1 s.
- Cessão: **nenhum 4xx ou 5xx** nas rotas de lotes e de pagamentos desde
  20/10 23:05 UTC. BFF: sem 5xx nas rotas de liquidação; 3 respostas 404 em
  `real-batches/cnab` (ver Risco) e 4 respostas 401 (token, sem relação).

**Réplica** (20/10; `evidencias/lotes-reais-replica-2026-10-20.md`)

| Caso | Antes | Depois |
|---|---|---|
| Página, fundo 209 | mais de 60 s | 0,4 s |
| Irmãos, fundo 209 | mais de 120 s | 0,1 s (5,3 s frio) |
| Página, fundo 26 (lotes de 30 e 13 mil) | — | 0,8 s quente; 33 s frio |
| Detalhe do lote 1837116 (1.744 remessas) | mais de 60 s | 34 ms |
| Detalhe do lote 1837120 (43 mil pagamentos) | — | 0,42 s quente |

**Sandbox**
- A TS-5383 só rodou na sandbox a partir de 21/10 18:00 UTC, depois da
  produção. O fluxo do hotfix (detalhe só pelo `lote_id`) não teve chamada
  na sandbox. Nos dois casos a validação anterior ao deploy foi local e na
  réplica.

**Segundo ambiente de produção (a confirmar)**
- O argocd da cessão tem um segundo ambiente de produção (pasta de outra
  operação). Ele estava em `prod-f19ef2c` e foi para `prod-fb6f409` em 21/10
  20:14 UTC (commit `a87c914`, outro dev), ou seja, recebeu a TS-5383, a fase 1
  e o hotfix só então e sem esta GMUD. **A confirmar:** se o time dele cobre
  o registro, e se o rollback também precisa mudar a tag lá.

**Para repetir a medição** (Datadog, `aggregate_spans`)
- Rota: `env:production service:platform-cessao operation_name:flask.request
  resource_name:"GET /liquidacao/lotes/reais"`, COUNT, P50, P95, MAX e SUM de
  `@duration`, agrupado por `@http.status_code`. Para versão, `@version`.
- Banco: `env:production service:postgres operation_name:postgres.query
  @db.instance:platform-cessao resource_hash:(788d1d5df137d8b OR
  db8a1f03fb515cca OR 4856ef7a427ac6f6 OR 9cc782411e60f129)`, agrupado por
  `resource_hash` e `status`.
- Detalhe: `resource_name:"GET /liquidacao/pagamentos/query"` na cessão e
  `resource_name:*liquidation/payments*` no BFF (`fastapi.request`).
- Fundo de cada chamada: logs "Buscando lotes reais de liquidação paginados",
  campos `@fundo_id`, `@data_inicio` e `trace_id`.
