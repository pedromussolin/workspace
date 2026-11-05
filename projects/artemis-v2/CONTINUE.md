Status: em andamento
Data: 04/11/2026
Tags: artemis, v2, liquidacao, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`. Os valores reais (hosts, usuários de banco, nomes por trás dos análogos) estão no arquivo local `~/.config/workspace/private/artemis-v2.md`.

Este arquivo foi montado em 26/10/2026 a partir do status do `README.md` e do histórico de commits da pasta. O que aqui não está escrito, o README e o histórico não dizem: confira antes de afirmar.

## Onde parei

### 04/11/2026

**Produção feita (~19h10 às ~19h25, adiantada da janela das 20h, depois do whitelabel).** Detalhe
na `gmud-ts-5536.md` (portal: GDM-352), em "Evidências", item "Produção, execução".
- **Cessão** `prod-579ad13` (`release/20261104`, PR #2743, sem a TS-5537) em `asgard-production` e
  `viva-production`. A migration `c3f81d7a5e24` rodou às 19:20 e foi validada: 156 produtos, 0
  divergentes.
- **Argocd** (merge da `chore/TS-5536-worker-fechamento`): `fake-batch-closing` com 2 réplicas,
  sondas e 4 tarefas por pod, pela `CONCORRENCIA_POR_FILA` do Parameter Store.
- **BFF** `prod-f0511cb` e **Portal** `prod-2ff9802` (`release/20261104-artemis`, PRs #264 e #287),
  nas três marcas.
- **Sandbox antes:** S1, exclusão, S2, S8 e S9 ok. Achado e corrigido: diálogo de confirmação
  largo demais; o `DialogService` ganhou teto de 560 px (PR #287; sandbox pela #288).
- **Do dia:** concorrência por fila no lugar da `CELERY_WORKER_CONCURRENCY` do values (o
  Parameter Store vencia); TS-5537 fora, a pedido do time; scripts da modalidade em
  `attachments/sql/closing-modality-{preview,validate,apply}.sql`; pendências do `viva-production`,
  renomear a coluna da modalidade e variáveis repetidas nos workers em `after-v2.md`.
- **Para o negócio:** resumo em linguagem simples mandado no grupo; a operação acompanha o primeiro
  uso em 05/11.

**Nova frente (noite):** o Rafael Frankl sai da empresa e a liquidação do Mercato Libero que ele
rodava na EC2 de automações vem para a V2. Criada a [tarefa 13](tasks/13-mercato-libero-settlement.md),
só com o contexto, e a [evidência de 04/11](evidence/mercato-libero-ec2-calls-2026-11-04.md): a
máquina segue chamando a cessão todo dia, com pico às 16h–17h de Brasília. As telas de operações
dele foram para o projeto novo `projects/operations-screens-migration/`, que guarda o inventário
da máquina (tarefa 01 de lá). Recorte da 13, a pedido do Pietro: a V2 cuida do sistema em diante,
com o fechamento automático por horário de corte da tarefa 11 no lugar da varredura, tudo na rota
nova (`refact.py`), inclusive o `POST /liquidacao/` que a varredura chama (migra antes ou junto).
A chegada dos dados fica com o time. Contingência pelo agendamento antigo pendente na D25.

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

1. **05/11, operação:** acompanhar no Datadog o primeiro uso em produção (passo 6 da GMUD: listagem
   com aptos, fechar uma linha, excluir). Registrar na `gmud-ts-5536.md` e montar o texto para colar
   na GDM-352 (a API não comenta na GMUD).
2. **05/11, Mercato Libero:** recorte da tarefa 13 definido (fechamento automático pela tarefa 11;
   a chegada dos dados fica com o time). Seguir os "Próximos passos" dela: com o Rafael, a data de
   saída, o que o script grava no banco e a hora em que os dados ficam completos; depois conferir
   a contingência (D25).
3. **`viva-production`:** pedir a validação da modalidade com `closing-modality-validate.sql` e
   decidir o worker de fechamento (`after-v2.md`).
4. **Semana:** S1 a S14 de `tasks/02-03-sandbox-tests.md`, já em produção.
5. **Depois:** tradução do `refact.py` para PT-BR; TS-5537 (B18) numa release seguinte; renomear
   `modalidade_fechamento_lote`; limpar as variáveis repetidas nos workers da cessão.
