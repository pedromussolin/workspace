Status: em andamento
Data: 03/11/2026
Tags: artemis, v2, liquidacao, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`. Os valores reais (hosts, usuários de banco, nomes por trás dos análogos) estão no arquivo local `~/.config/workspace/private/artemis-v2.md`.

Este arquivo foi montado em 26/10/2026 a partir do status do `README.md` e do histórico de commits da pasta. O que aqui não está escrito, o README e o histórico não dizem: confira antes de afirmar.

## Onde parei

### 03/11/2026

**Decisões do dia** (detalhe em `decisions.md`):
- Todo análogo no `refact.py` substitui o código antigo: (1) roda só na tela; (2) os outros
  escopos (`POST /liquidacao/`, automático, agendado, máquina de estados) passam a usá-lo;
  (3) o legado é apagado. Guarda e correção só no `refact.py`. A migração começa depois da
  semana de testes de tela.
- Código da cessão em PT-BR, inclusive o inglês que já existe no `refact.py` (tradução marcada
  para 04/11; escopo a decidir: só nomes internos ou também rotas, fila, task, chaves do Redis,
  JSON de status e chaves de log).
- Chart do argocd não muda (desligamento fica em 30 s).

**Cards novos:** TS-5536 (listagem, exclusão, busca de pagamentos e worker no fluxo novo) e
TS-5537 (B18), no épico TS-5278.

**Desenvolvido e revisado pelo Pietro (todos os testes passando):**
- **Cessão, `feature/TS-5536-listagem-fluxo-novo`:** listagem nova no `refact.py` (chave pela
  modalidade, `qtd_aptos` pela D9, `GET /liquidacao/fake-batches`); exclusão nova
  (`DELETE /liquidacao/fake-batches`: só pagamentos sem lote da linha, do dia na linha `origem:`;
  `FOR UPDATE` e reconferência; uma transação por liquidação; continua sozinha em tarefas de
  ~400 s; não depende do Redis para terminar; trava da linha compartilhada com o fechamento);
  status do fechamento devolve também a exclusão (`operation`); busca de pagamentos da linha
  (`GET /liquidacao/fake-batches/payments`). Prova de concorrência em Postgres e Redis reais.
- **BFF e front, mesma branch:** usam as três rotas; o Fechar só habilita com apto ("N de M
  registros aptos"); a exclusão manda a chave e o dia; a tela acompanha a exclusão pelo status.
- **Cessão, `chore/TS-5536-worker-fechamento`:** probes por arquivo e `exec` só no worker sem
  consumer; **argocd**, mesma branch: duas réplicas e probes (sobe junto com a imagem da cessão
  ou depois, nunca antes).
- **Cessão, `fix/TS-5537-callbacks-nulos-na-liberacao`:** `callbacks or []` na esteira da cessão.

**Achados:** B23 (excluir pela tela apaga remessas inteiras), B24 (Redis de produção cheio
descartou ~19,7 mi chaves em outubro), origem do B18 (TS-187, de 06/2025; 10 contratos do produto
15 presos) e causa do B21 (lotes nascem vazios no automático). Medição da listagem em
`evidence/fake-listing-replica-2026-11-03.md`: custo igual à antiga.

### Até 26/10/2026

O desenvolvimento da V2 começou em 05/10/2026. O escopo inicial é a tela de lotes de liquidação da platform-cessao, ou seja, o fechamento e a conciliação dos lotes, com a **performance** como ponto principal. A DBA revisa as queries; a parte de aplicação fica com a gente.

Situação das tarefas, pela tabela do `README.md` (última edição em 20/10):

| Tarefa | Situação |
|---|---|
| 01, réplica de leitura | concluída (PR #2628, 07/10; variável no Parameter Store), TS-5279 |
| 03, fechamento mais rápido e assíncrono | em produção (cessão 19/10, BFF e front 20/10), TS-5377; casos e plano de 20/10 em `tasks/03-post-production-cases.md` |
| 12, lotes reais: buscar os lotes antes dos valores | **prioridade máxima** (14/10); mapeada; depende da D21 |
| 02, dois modos de fechamento (chave ou proc_id) | desenho alinhado |
| 04, 05, 06, 07 | mapeadas (a 04 espera a revisão da DBA; a 06 espera a decisão D4) |
| 08, Genius: reenvio e logs de erro | mapeada (revisada em 13/10); depende das D12 a D16 |
| 09, lote automático da Voltis | aguardando dados (configs do produto) |
| 10, fluxo da Genius para a Dayvale | aguardando descoberta (APIs da Dayvale e TS-5207) |
| 11, fechamento por horário de corte | ideia; depende da 02 e da D8 |

O que o histórico de commits registra depois disso (20 a 22/10):

- **20/10, TS-5383:**
  - a premissa da D21 e o SQL foram validados na réplica;
  - publicada só com código, e depois registrada em produção com as primeiras horas;
  - hotfix do detalhe do lote real pelo `lote_id`.
- **20/10, fase 1 da TS-5377 (robustez do fechamento):** a GMUD seguiu pelas releases de 20/10. Com a fase 1 em produção, a GMUD passou a ser retroativa.
- **21/10:** métricas de produção do fechamento e dos lotes reais.
- **22/10:** a GMUD da TS-5377 de 19/10 virou retroativa; a GMUD da fase 1 recebeu o uso em produção e o rollback; a GMUD da TS-5383 recebeu o hotfix do detalhe pelo `lote_id`; as prioridades das GMUDs e o ambiente da Viva na TS-5383 foram registrados; os testes de 22/10 das GMUDs da TS-5377 e da TS-5383 foram registrados.
- **Último commit da pasta (22/10):** status das GMUDs da TS-5377 sem pendência de teste.

As GMUDs estão em `gmud-ts-5377.md`, `gmud-ts-5377-phase1.md`, `gmud-ts-5383.md` e `gmud-ts-5279.md`.

## Branches e worktrees

Worktrees em `~/repos/.artemis_v2/worktrees/`. Cópia do trabalho de 03/11 antes dos commits
(patch e árvore final de cada worktree) em `~/repos/.artemis_v2/agentes/backup-20261103/`
(`arvores.txt` tem a árvore aprovada de cada uma).

| Repo | Branch | Worktree | Situação em 03/11 |
|---|---|---|---|
| cessão | `fix/TS-5537-callbacks-nulos-na-liberacao` | `ts5537` | 1 commit, no remoto |
| cessão | `chore/TS-5536-worker-fechamento` | `ts5536-worker` | 2 commits, no remoto |
| argocd | `chore/TS-5536-worker-fechamento` | `argocd-ts5536` | 1 commit, no remoto |
| cessão | `feature/TS-5536-listagem-fluxo-novo` | `ts5536-listagem` | 8 commits, no remoto (base `8873832dd`) |
| BFF | `feature/TS-5536-listagem-fluxo-novo` | `bff-ts5536` | 7 commits, no remoto (base `3bf3e82`) |
| front | `feature/TS-5536-listagem-fluxo-novo` | `front-ts5536` | 4 commits, no remoto (base `bf378f60`) |

As três `feature/TS-5536-…` partem da `feature/TS-5435-fechamento-por-proc-id` (que contém a fase 2).

O README e o histórico não registram branches nem worktrees. O código da V2 vive nos repositórios da empresa; confira lá a situação de cada branch antes de continuar uma tarefa. Todas as referências `arquivo:linha` do README valem para os commits de `origin/master` de 05/10/2026 listados nele.

## Próximo passo

**Releases para a sandbox (03/11, à noite), todas publicadas e testadas localmente:**
- cessão: `release/20261103` (produção, depois dos testes) e `release/20261103-sdbx`, PR #2739;
- BFF e front: `feature/TS-5536-adapta-release-20261030` (a TS-5536 com a fase 2 e a TS-5435,
  adaptada à `release/20261030`) entrou só na `release/20261030-sdbx`: PRs #261 (BFF) e #283
  (front). A `release/20261030` de produção não tem nada da Artemis.

1. ~~Merge na sandbox~~ (03/11, ~21h): cessão #2739, BFF #261 e front #283 estão mergeados e no argocd.
   - Cessão: `sand-6f411b3` e as sondas por arquivo do `fake-batch-closing`, só no values da
     sandbox. As réplicas ficaram em 1: o usuário não quis 2 na sandbox.
   - O `30f4814` da branch `chore/TS-5536-worker-fechamento` do argocd continua sem merge. A parte
     de produção vai com a imagem nova.
   - BFF `sand-99f87d3`; front `sand-29325b0`.
   - Produção: em janela separada da reestruturação do whitelabel (decisão do usuário).
2. 04/11: tradução para PT-BR do `refact.py` e afins (decidir o escopo antes).
3. Semana: testes de tela na sandbox (S1–S14 de `tasks/02-03-sandbox-tests.md` mais listagem com
   aptos, exclusão, acompanhamento e expandir a linha).
4. Produção: nova release do BFF e do front a partir da `master` pós-20261030 com a branch de
   adaptação; cessão pela `release/20261103`. B18 com o time; argocd do worker só com a imagem nova.
