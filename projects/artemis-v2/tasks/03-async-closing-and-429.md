+++
card = "TS-5377"
type = "task"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
docs = ["03-closing-analysis.md", "03-post-production-cases.md", "03-pre-production-review.md"]

[tracker]
status = "done"
priority = "Highest"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-17
+++
# 03 — Fechamento de lote: mais rápido, sem espera e sem 429

- **Status:** em implementação (13/10/2026), **TS-5377**. Branch
  `feature/TS-5377-fechamento-lote-fake-assincrono` (cessão, BFF, front) e
  `feature/TS-5377-worker-fechamento-lote` (argocd).
- **Repos:** platform-cessao, BFF, front, platform-cessao-argocd (fila dedicada).
- **Implementação (13/10/2026):** commits locais, sem push; testes passando
  (cessão: suíte completa, 4643; BFF: 106 do módulo; front: 19 dos specs da
  tela e do serviço).
  - **Cessão:** `cessao/api/liquidacao/refact.py` (`FakeBatchKey`,
    `RefactLiquidacaoRepository`, `RefactLiquidacaoService`), task
    `close_fake_batch` na fila `fake_batch_closing_celery`, rotas
    `POST /liquidacao/fake-batches/close` e `/fake-batches/close/status`,
    trava e resultado no Redis em `liquidacao:fake-batch-closing:*`,
    `INICIAR_CONSUMER` no `entrypoint.sh`.
  - **BFF:** `POST /operations/liquidation/fake-batches/close` e
    `/fake-batches/close/status`; B5 também no consolidate legado.
  - **Front:** linhas `origem:` fecham pelo fluxo novo, com polling (4 s/60 s)
    e estado na célula; linhas `proc:` seguem no legado.
  - **Argocd:** worker `fake-batch-closing` (1 pod, concorrência 2). O PR
    inicial altera só o `asgard-sandbox` (homologação); `asgard-production` e
    `vivo-production` entram num PR seguinte, depois de validado.
  - **Código novo em inglês**, com nomes explícitos do processo; mensagens ao
    usuário em PT-BR.
  - **Code review (14/10):** corrigidos fila sem consumidor em staging (fila
    na lista padrão do `entrypoint.sh`), linha sem origem/fundo fechando
    lotes vigentes de outras linhas, lote vigente preso fora da esteira após
    erro, trava sem dono (renovação e liberação por `job_id`, em Lua), cache
    limpo sem commit; UPDATE refeito via ORM; D9 exige cessão
    `cadastrado` (revista em 14/10); BFF confere o produto da chave e valida tamanho das
    chaves. Bugs de código antigo do BFF viraram B9 a B11.
- **Implantação (19/10):** cessão em produção (`prod-f19ef2c`); worker de
  produção no argocd em `feature/TS-5377-worker-fechamento-lote-producao`
  (`61ecc97`, só asgard-production). BFF (`prod-fe2bee2`) e front em
  produção em 20/10, ~12:26 UTC.
- **Fase 1 de robustez: em produção desde 20/10 ~23:06 UTC** (cessão
  `prod-2eb8faa`, BFF `prod-a1d5abd`), branches
  `fix/TS-5377-robustez-fechamento-lote`. GMUD retroativa em
  [gmud-ts-5377-phase1.md](../gmud-ts-5377-phase1.md).
  - **Cessão (`refact.py`, task, schema, viewer):**
    - `SET LOCAL statement_timeout` (480 s) e `lock_timeout` (60 s),
      configuráveis por `FAKE_BATCH_CLOSING_STATEMENT_TIMEOUT_MS` e
      `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS`;
    - motivos claros para tempo, trava, parcial e interrupção;
    - vigente e lote novo vão para a esteira logo após o próprio commit
      (R9);
    - pedido gravado na rota, e o status devolve "interrompido" quando a
      trava some sem resultado (R8, R18);
    - sem `expires`; `acks_late` e `reject_on_worker_lost`, com no máximo 2
      tentativas (R19);
    - resultado gravado só pelo dono do pedido e, para a mensagem atrasada,
      só sobre pedido pendente (R14);
    - cliente Redis com timeout de 2 s; renovação que perde a trava liga um
      aviso e o job desiste antes do commit (R13, R23);
    - `task_id = job_id`; o log de conclusão traz `attempt`,
      `queue_wait_ms` e `requested_by` (R28).
  - **BFF:** manda `requested_by` (oid do Azure AD, não o e-mail) e loga o
    `job_id` devolvido pela cessão.
  - **Validação:**
    - suíte completa da cessão com 4.803 testes, zero falhas (`master`:
      4.782);
    - BFF com 114 testes do módulo;
    - scripts Lua em Redis 6.2 real (18 cenários);
    - limites de banco em Postgres 13 real (trava, tempo e `SET LOCAL` sem
      vazar).
  - **Estresse (20/10):** [evidence/closing-stress-2026-10-20.md](../evidence/closing-stress-2026-10-20.md).
    Com falha (trava externa, worker parado ou morto) a `master` perdeu
    pedidos sem aviso e a branch nenhum. O teste achou trava órfã com o Redis
    lento (E1), corrigida na branch com trava e pedido num script Lua só.
    Propostas: espera por trava de ~30 s (E3) e "linha já fechada" no clique
    que chega logo depois de um fechamento (E2).
  - **Ordem de deploy:** cessão (API e worker juntos), depois o BFF. O
    resultado no formato antigo, sem `job_id`, não bloqueia o novo.
- **Casos depois da implantação (20/10):** [03-post-production-cases.md](03-post-production-cases.md)
  — revisão de todos os caminhos (tempo, fechamento perdido, corridas com o
  legado, tela) e plano em fases; acompanhamento em
  [evidence/async-closing-monitoring.md](../evidence/async-closing-monitoring.md).
- **Pendências depois da implantação (19/10)** — retomar por aqui:
  1. ~~**R16**~~ — **20/10: 16 virou o padrão, por enquanto** (decisão do Pietro).
     Histórico: **R16, concorrência 16 no worker de produção.** O values pede 2; o pod
     (`platform-cessao-fake-batch-closing-worker`, 19/10 21:45 UTC,
     `prod-f19ef2c`) subiu com 16. Causa provável: a carga da configuração
     no fim do `entrypoint.sh` (`entrypoint.sh:60`) exporta as variáveis do
     Parameter Store por cima das do pod; no sandbox o mesmo values sobe com
     2. **Confirmar** se o Parameter Store de produção da cessão define
     `CELERY_WORKER_CONCURRENCY`. **Corrigir:** remover a variável de lá (os
     outros workers ficam em 16, o padrão do entrypoint) ou ler a
     concorrência do worker dedicado de uma variável que o Parameter Store
     não define. **Por que importa:**
     - banco: o limite de 2 fechamentos simultâneos (decisão de 13/10) é o
       que protege o primário; com 16 o paralelismo volta perto do de antes
       (em 08/10, ~20 fechamentos em paralelo deixaram consultas presas
       umas nas outras). Cada fechamento é mais barato agora (UPDATE único);
     - memória: 16 processos dividem 3 GiB (os workers de produção usam
       12 GiB para 16). Parados, compartilham memória e o pod fica estável;
       com vários fechamentos juntos pode estourar, o pod é morto e os
       fechamentos em andamento somem sem aviso (R8).
     - **Risco prático hoje:** baixo, ~49 fechamentos por dia pela tela,
       quase nunca simultâneos. Pesa se vários operadores fecharem juntos ou
       se a varredura passar para a rota nova.
  2. **Limites de tempo nas três pontas** (decisão de 19/10): timeout curto
     no cliente Redis (R13), `statement_timeout` configurável no fechamento
     (R4) e limite do Celery acima dele. Hoje a task tem 540/600 s fixos no
     decorator (`cessao/tasks/fake_batch_closing.py:4`), não configuráveis.
  3. **R7 a R15** da revisão (listagem sem a regra da cessão, descarte
     silencioso, vigente fechado e não despachado, estado da linha no front,
     excluir habilitado, índice da origem, trava perdida, observabilidade).
  4. **Desligamento dos workers (R3, rebaixado):** o Celery não recebe o
     sinal de desligamento no deploy; comportamento antigo de todos os
     workers da cessão, sem perda de dado (o fechamento é desfeito). Corrigir
     com `exec`/init e prazo de desligamento, numa tarefa própria.
  5. **Fora da TS-5377:** "Erro na esteira 'NoneType' object is not
     iterable" em `estados_cessao.py:82` (`_existe_callback`), logo após
     lote criado pela varredura; apareceu em 13, 15, 16 e 19/10. Causa
     levantada em 20/10: [B18](../bugs-found.md); não impede o lote de
     seguir.
  6. ~~**Implantação:** faltam BFF e front~~ — no ar em 20/10 (BFF
     `prod-fe2bee2`). vivo-production sem worker (sem Portal lá).
- **Revisão antes de produção (15/10):** [03-pre-production-review.md](03-pre-production-review.md).
  Bloqueios R1–R6 (worker de produção, ordem de deploy, deploy que mata o
  fechamento em andamento, limites de tempo em grupos grandes, fundo da
  parcela × processo, B9); médios R7–R15.
- **Análise completa:** [03-closing-analysis.md](03-closing-analysis.md)
  (mapa do fluxo, consultas, síncrono × assíncrono, estimativa).
- **Evidências:** [Datadog, 09/10/2026](../evidence/batch-closing-datadog-2026-10-09.md).
- **Decisões:** [D6](../decisions.md) (rota em lote), **D9** (regra de
  elegibilidade), **D10** (assíncrono, decidida em 09/10).
- **Relacionadas:** [02](02-close-batch-by-proc-id.md) (mesmo UPDATE no modo
  por proc_id), [04](04-listing-performance.md) (revisão de queries com a DBA),
  [11](11-closing-by-cutoff-time.md) (substitui varredura e
  automático legado).

## Item original

> Rota de fechamento de lote (em batch ou permitir mais requests para o cessão
> para evitar 429)

## Problema

`POST /liquidacao/`, 30 dias até 09/10:

| Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 200 | 676 | 16,6 s | 7,1 min | 15,5 min |
| 500 | 71 | 14,2 min | 43,5 min | 1h42 |
| 400 | 3.299 | 2,0 s | 5,0 s | 8,6 min |
| 429 | 89 | 10 ms | 14 ms | — |

- **O tempo é espera de banco** em três pontos:
  - o agrupamento (Q1): 256 h de banco;
  - a busca de ids (Q2): 501 h;
  - a montagem da resposta: até 99% de uma requisição.
- **A esteira já é assíncrona.** O que demora é o próprio fechamento.
- **49 dos 71 erros 500** são a trava do 429 expirando aos 600 s. O 500 sai
  mesmo com o lote criado.
- **O 429** é o clique repetido. O front guarda "em andamento" só em memória,
  e a marca some ao recarregar a página.
- **Q1 e Q2 usam regras diferentes** para decidir que pagamento entra no lote
  (análise, seção 2).

Quem chama a rota:

- a **tela**, pelo BFF;
- o **Atlas**: um grupo por chamada, e só lê código e mensagem da resposta;
- a **varredura**: automação externa (EC2 de automações), do Rafael Frankl
  (liquidação do Mercato Libero), que recebe 400 em 95% das chamadas.

## Proposta

Primeiro deixar cada fechamento barato; depois tirá-lo da requisição
(assíncrono, D10).

### Etapa 0 — levantamentos

- **L1:** ~~dono da varredura~~ Rafael Frankl (liquidação do Mercato Libero). Falta combinar o contrato da resposta com ele.
- **L2:** produtos por modo de fechamento (SQL na réplica).
- **L3:** medir na réplica o UPDATE único com o maior grupo real (define o
  TTL da marca e quanto a task segura a fila).
- **L4:** ~~decisão D9~~ decidida em 13/10 e **revista em 14/10**: exige a cessão `cadastrado`; produto da liquidação.

### Etapa 1 — ganhos rápidos (fora da TS-5377)

Seguindo o `refact.py`, o fluxo novo nasce em rota própria, só para o front,
e o legado não muda. P1, P3 e P4 mexem só no legado (rota antiga, Atlas,
varredura, esteira compartilhada) e foram para
[after-v2.md](../after-v2.md). A rota nova não usa a Q1: a linha da
tela já traz fundo e origem.

1. ~~**P1:** a Q1 recebe a origem~~ — adiado em 13/10.
2. ~~**P2:** resposta montada numa consulta~~ — cortado em 13/10.
3. ~~**P3:** trava expirada deixa de virar 500~~ — adiado em 13/10.
4. ~~**P4:** `EXISTS` na esteira~~ — adiado em 13/10.

### Etapa 2 — fechar o grupo numa instrução

5. **P5:** regra única (D9) e um UPDATE que procura e marca os pagamentos de
   uma vez, sem trazer ids ao Python.
6. ~~**P6:** índices~~ — adiado em 13/10 para
   [after-v2.md](../after-v2.md).
7. **P7:** um log por fechamento, com duração e quantidade de pagamentos.
   Calibra a concorrência da fila e o TTL da marca.

### Etapa 3 — clique sem espera e sem 429 (D10, decidida em 09/10)

8. **P8 — fechamento assíncrono:**
   - a rota grava a marca `fechando:<chave da linha>` no Redis (`SET NX`,
     TTL curto) e enfileira a task numa fila dedicada, com concorrência
     limitada (decidido em 13/10: deployment próprio no argocd e variável
     nova de filas no `entrypoint.sh`, com a lista atual como padrão). Marca já existente → 409. Sai o `@max_calls`;
   - a task fecha (etapas 1 e 2), renova o TTL enquanto roda e grava na marca
     o resultado: `fechado` (id do lote) ou `falhou` (motivo), que expira
     minutos depois;
   - endpoint leve de status: recebe as chaves das linhas e lê as marcas
     (`MGET`), sem tocar na listagem;
   - front: tira a marca em memória (`close-batches.ts:113`, `:548-552`) e
     faz polling adaptativo (curto com linha em fechamento, longo ou manual
     sem nenhuma; pausa com a aba oculta). Recarrega a listagem só quando uma
     marca muda;
   - dedupe: pedido que cobre várias linhas (varredura) é expandido em uma
     task por chave, cada uma com a sua marca. O agendado e o automático
     passam a usar a mesma task quando a tarefa 11 os reescrever;
   - a proteção contra fechar em dobro continua no
     `WHERE liquidacao_lote_id IS NULL` do UPDATE;
   - antes de mudar a resposta da rota, combinar com o Rafael Frankl
     (varredura do Mercato Libero).

### Opcionais

- **O1:** estado `excluindo` na exclusão. O `DELETE` já é assíncrono e não tem
  problema medido.
- **O2:** rota em lote (D6).
- **O3:** status dos contratos em lote e a corrida no enfileiramento
  (`estados_baixa.py:86-87`).
- **O4:** N+1 e `fundo` repetido na geração do arquivo da ADM.
- **O5:** entender o `liberacao_processos` dentro da esteira de baixa.

## Pontos para estressar

- **D9 (decidida em 13/10):** a regra única exige a cessão concluída
  (`cadastrado`, revisão de 14/10 sobre a resposta do negócio de 13/10) e usa o
  produto da liquidação. Coincide com a Q1, que já exige a cessão.
- **Cessão que não seguiu:** sem tratativa automática; caso extraordinário,
  tratado à mão.
- **Varredura (Rafael Frankl, Mercato Libero):** não lê a resposta e aceita o
  assíncrono. Em aberto: quais tabelas ele grava direto no banco
  (com usuário de banco próprio).
- **Lote gigante (610 mil pagamentos):** medir o UPDATE único na réplica; ele
  define o TTL da marca e quanto a task segura a fila.
- **SQL escrito à mão:** o filtro de soft delete (exclusão lógica, quando a
  linha é só marcada como apagada) é injetado pelo ORM e não vale para
  `text()`. O `contrato_processo.data_delete IS NULL` precisa estar explícito.
- **Permissão:** o BFF só checa o papel, não se o produto é do parceiro
  ([B5](../bugs-found.md)).

## Validação

Comparar com a [evidência de 09/10](../evidence/batch-closing-datadog-2026-10-09.md),
usando as mesmas consultas.

**Testes**

- Fechar uma origem não consulta outras origens.
- Pagamento de processo excluído não entra pelo UPDATE novo.
- Dois POSTs idênticos: um fecha, o outro recebe 409, e nenhum recebe 429.

**Produção**

- Zero 500 por `ReleaseUnlockedLock` e zero 429.
- Queda da soma de banco de `253a4f59e2dcb949`, `9544189cfdc7d6a9` e
  `af6c090c7fa63323`.
- Queda do aviso "Tentativa de criar lote sem pagamentos".
- `esteira_baixar` com p99 abaixo de 47,8 s.
