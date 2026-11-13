Status: em andamento
Data: 13/11/2026
Tags: artemis, v2, liquidacao, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`. Os valores reais (hosts, usuários de banco, nomes por trás dos análogos) estão no arquivo local `~/.config/workspace/private/artemis-v2.md`.

Este arquivo foi montado em 26/10/2026 a partir do status do `README.md` e do histórico de commits da pasta. O que aqui não está escrito, o README e o histórico não dizem: confira antes de afirmar.

## Onde parei

### 11 a 13/11/2026

**Pausa para reorganizar o board (13/11).** A gestão pediu sprints definidas, com escopo fechado. O
Pietro vai reorganizar o board do Jira a partir da tabela abaixo; até lá, nada novo começa.

**Estado por card da tarefa 13 (13/11).** Detalhe e prazos em `tasks/13-plan.md`. Release única,
montada só com todos prontos, na ordem das migrations: 5583 → 5569 → 5570 → 5585 → 5567 → 5572.

| Card | Pronto | Falta |
|---|---|---|
| TS-5582 lotes vazios | cessão, BFF e front; branches enviadas | PRs na release |
| TS-5596 limpeza dos vazios antigos | script, simulação, blocos e runbook | revisão da DBA; execução em produção |
| TS-5583 duas colunas | branch enviada (8 commits) | PR na release |
| TS-5567 acúmulo natural | Fase 1, Fase 2 sem migration e remessa (cessão, BFF, front) | Tarefa 24 (automático) foi para a TS-5612 |
| TS-5569 agendamentos em tabela | branch enviada (9 commits, sobre a 5583) | PR depois da 5583 |
| TS-5584 Excel na shared | branch enviada (8 commits) | snapshot OpenAPI no BFF depois da PR |
| TS-5570 horário por produto | completa | PR na release |
| TS-5585 resumo diário e aviso | shared e cessão | horário do job (nasce desligado) |
| TS-5571 aprovação antes do corte | cessão e front | PR na release |
| TS-5624 tela de configuração do produto | cessão, BFF e front | validar a tela no navegador |
| TS-5568 `POST /liquidacao/` no fluxo novo | BFF sem o consolidate | PR; a rota legada sai na TS-5612 |
| TS-5572 automático no fluxo novo | completa | PR na release |
| TS-5620 omnis e lemans_2 sem o Atlas | pipeline do CSV no parser-script (enviado); liquidar no portal (cessão, BFF, front, **sem commit**) | ver abaixo |
| TS-5612 limpeza pós-deploy | lista em `tasks/13-plan.md` | sem sprint até o fluxo novo estabilizar |

**TS-5620 em detalhe.**
- **Liquidar no portal:** a cessão confere produto e estado em rota nova do `refact.py`; BFF e front
  usam. Worktrees `ts5620-cessao`, `ts5620-bff` e `ts5620-front`, **sem commit, esperando a revisão
  do Pietro**. Aberta: trava no Redis contra o duplo clique.
- **Upload de 1109 e 1373:** o arquivo vai do portal ao S3 de dois clientes novos do parser-script,
  que publica uma mensagem por linha no RabbitMQ da cessão com o contrato do datawall (a cessão não
  muda). Parser-script pronto: `feature/TS-5620-liquidacao-csv-padrao`, 4 commits, enviada em 12/11,
  82 testes. A ordem dos campos do JSON foi provada rodando as mesmas versões do datawall (1.10.1
  da linguagem e cheshire 5.8.1), para a deduplicação da cessão casar com a do datawall.
- **Quem grava no S3:** o apl-shared-service (decisão de 12/11). Proposta de 12/11, **a aprovar**:
  (a) origem nova "arquivo enviado" nos fluxos do `report_transfer` do shared, rota
  `POST /flows/upload`, BFF repassa pelo `_post_file` do cliente do shared, botão "Subir arquivo" na
  tela **[recomendo: produto novo vira configuração e o histórico de execuções vem pronto]**; ou
  (b) módulo novo e simples, destinos fixos em variável de ambiente. **[H]** o histórico de execuções
  se prende ao id da tarefa agendada; conferir se o upload cabe sem migration. As linhas recusadas
  pelo parser-script só aparecem no log, não na tela.
- **No deploy:** dois clientes no argocd do parser-script (bucket, SQS e app); variáveis da conexão
  S3 do shared no Parameter Store; `CELERY_BROKER_URL` do parser-script apontando para o RabbitMQ da
  cessão; teste na sandbox com arquivo real de 1109 ou 1373.
- **Data do lote** no portal: em aberto.

**Tarefa 14 (esteira de baixa que não aguenta lote gigante), sem card.** Desenho da Fase 0 em
`tasks/14-phase0-design.md` (12/11; só leitura, nada implementado).
- Decidido: Fase 0 = reentrega segura + arquivo em blocos; teto com 3 rodadas automáticas (15 min,
  1 h, 4 h; da 2ª em diante numa fila isolada) antes de `errado` (seção 3.1).
- Abertas: código fora do `refact.py` (decisão 1 do desenho); envio interrompido, com a proposta de
  consultar a administradora antes de reenviar (decisão 4); ordem do arquivo por `id` (decisão 8).
- **Achado de 12/11:** a rodada de 4 h usa `countdown`, e o Celery segura a mensagem sem confirmação
  até a hora. Se o `consumer_timeout` do RabbitMQ de produção estiver ligado (30 min por padrão a
  partir da 3.8.15), o broker fecha o canal e devolve também as baixas em andamento. Conferir versão e
  limite antes de implementar; recomendo pedir à operação para aumentar o limite.


**TS-5582 em execução (Em andamento no Jira desde 10/11).** D26 = `descartado`; a limpeza dos vazios
antigos saiu para a **TS-5596** (prazo 18/11); BFF e front entraram no card (aviso de descartado na
tela, filtro e cor). Decisões em `decisions.md`; escopo no topo de `tasks/13-plan-ts-5582.md`.
- Worktrees em `~/repos/.artemis_v2/worktrees/` (`ts5582-cessao`, `ts5582-bff`, `ts5582-front`),
  branch `feature/TS-5582-lotes-vazios-liquidacao` a partir da master de 10/11. Tudo implementado e
  testado **sem commit**, esperando a revisão do Pietro (cessão 5.705 testes ok; BFF 4.492 ok; front
  253 da área ok, 2 falhas de layout que já existem na master).
- Instruções e logs dos agentes em `~/repos/.artemis_v2/agentes/ts5582/`.
- Mensagens E1 (ETL, com aviso do estado `descartado`) e E2 (negócio, reescrita sem jargão) prontas
  em `~/repos/.artemis_v2/agentes/ts13-mapeamento/` (fora do repo: nomes reais). Falta enviar.

### 09/11/2026

**Tarefa 13, planos de implementação.** Desenho em `tasks/13-closing-design.md`; índice dos
planos em `tasks/13-plan.md`, um plano por card (`tasks/13-plan-*.md`).
- Revisados linha a linha contra o código: TS-5582, TS-5583, TS-5567 e TS-5569.
- Escritos, com a revisão pausada para poupar tokens: TS-5584, TS-5570, TS-5585, TS-5571,
  TS-5568, TS-5572 e a tela de configuração do produto. A TS-5570 ainda precisa trocar os jobs de
  horário único pela lista `horarios` da TS-5569 (11 jobs mais o do produto 1604).
- Cards criados no Jira: TS-5582, TS-5583, TS-5584 e TS-5585. O da tela de configuração ainda não.
- Decisões de 07/11 e 08/11 em `decisions.md`; pendentes D26 a D30. B26 (lotes vazios) explicado
  em `bugs-found.md`.
- O PC foi formatado em 09/11 e os agentes de revisão pausados se perderam. Retomar com agentes
  novos pelo brief de revisão, na cópia local `~/repos/.artemis_v2/agentes/ts13-plans/`
  (`REVIEW-BRIEF.md`, `BRIEF.md`, `INDEX.md`), restaurada do backup.

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
rodava na EC2 de automações vem para a V2. Criada a [tarefa 13](../vm-migration/tasks/13-mercato-libero-settlement.md),
só com o contexto, e a [evidência de 04/11](evidence/mercato-libero-ec2-calls-2026-11-04.md): a
máquina segue chamando a cessão todo dia, com pico às 16h–17h de Brasília. As telas de operações
dele foram para o projeto novo `projects/vm-migration/`, que guarda o inventário
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

**Situação em 13/11** (conferida com `git status` em cada worktree):
- **Enviadas, sem nada local:** `ts5567-{cessao,bff,front}`, `ts5568-bff`, `ts5569-cessao`,
  `ts5570-cessao`, `ts5571-{cessao,front}`, `ts5572-cessao`, `ts5582-{cessao,bff,front}`,
  `ts5583-cessao`, `ts5584-shared`, `ts5585-{cessao,shared}`, `ts5596-cessao`,
  `ts5624-{cessao,bff,front}`, `ts5620-parser` (apl-cessao-parser-script). Estado das PRs não
  conferido.
- **Sem commit:** `ts5620-cessao` (`feature/TS-5620-liquidar-lote-real`), `ts5620-bff` e
  `ts5620-front` (`feature/TS-5620-liquidate-batch`), esperando a revisão do Pietro.
- `preview-front` (`preview/artemis-v2-front`) tem 1 arquivo alterado, fora dos cards.
- Rascunhos dos agentes da tarefa 14 em `~/repos/.artemis_v2/agentes/ts14/`; mapeamento da TS-5620
  em `~/repos/.artemis_v2/agentes/ts13-exec/atlas-omnis/` (fora do repo).

| Repo | Branch | Worktree | Situação em 03/11 (em produção desde 04/11) |
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

1. **Board:** o Pietro reorganiza o Jira em sprints a partir da tabela "Estado por card (13/11)".
   Faltam cards para a Fase 0 da tarefa 14 e, se ficar separado, para o upload da TS-5620.
2. **Decisões do Pietro:** desenho do upload no shared ((a) fluxos do `report_transfer` ou (b)
   módulo simples); trava do duplo clique (TS-5620); decisões 1, 4 e 8 da Fase 0 da tarefa 14.
3. **TS-5620:** revisão e commits do liquidar (`ts5620-cessao`, `ts5620-bff`, `ts5620-front`);
   depois da aprovação, upload no shared, BFF e front; data do lote.
4. **Antes da release:** TS-5624 no navegador, revisão da DBA na TS-5596, snapshot OpenAPI da
   TS-5584; depois montar a release única na ordem das migrations.
5. **Tarefa 14:** conferir versão e `consumer_timeout` do RabbitMQ de produção.
6. **Antigas, sem data:** `viva-production`, S1 a S14 de `tasks/02-03-sandbox-tests.md`, tradução
   do `refact.py`, TS-5537 (B18), TS-5565 (confirmar se a passagem com o Rafael aconteceu).
