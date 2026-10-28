# 03 — Casos do fechamento depois da implantação (20/10/2026)

Revisão de todos os caminhos do fechamento novo (TS-5377), não só os que a
tela exercita, no primeiro dia em produção. Três revisões em paralelo,
somente leitura, sobre o código publicado:
- cessão `f19ef2cef`;
- BFF `fe2bee2`;
- front `d23eaef6`;
- argocd `5ff2408`.

Linhas citadas valem para esses commits. **[C]** = visto no código ou no
Datadog; **[H]** = hipótese, com o jeito de validar.

## Conclusão

- **O fluxo novo não fecha em dobro e não corrompe dado sozinho.** [C]
  - O UPDATE com `liquidacao_lote_id IS NULL` convive bem com o legado, que
    também tem a guarda (`models.py:6410-6427`).
  - Rota e task leem tudo do primário (só GETs com `@consulta_replica` usam a
    réplica).
  - Só o worker dedicado consome a fila.
- **O risco é outro.** Quase toda falha vira "a linha volta a ficar
  disponível e ninguém avisa". Três casos levam a isso:
  - a mensagem expira na fila;
  - o pod morre no meio do fechamento;
  - o soft limit é atingido.

  Além disso, grupo grande pode nunca fechar, e um lote pode ficar fechado e
  parado, sem esteira.
- **Hoje o risco é baixo.** O uso é pela tela, com grupos pequenos e ~49
  fechamentos por dia. Basta acompanhar pelo
  [roteiro](../evidence/async-closing-monitoring.md).
- **Antes de virar o jeito padrão** (varredura, Atlas, automático, grupos de
  100–600 mil), a fase 1 do plano é obrigatória. As corridas antigas do lote
  vigente (B14, B15) também precisam de guarda, porque a rota nova as herda.

## Estado em 20/10

- **Implantação** [C, Datadog]:
  - cessão e worker em produção desde 19/10 21:45 UTC (`prod-f19ef2c`);
  - BFF (`prod-fe2bee2`) e front desde ~12:26 UTC de 20/10.
- **Primeiro dia:** 25 pedidos e 25 fechados (52.139 pagamentos), sem falha.
  Onze fechamentos do fundo 209 esperaram até 25 s por uma trava de outra
  transação. Ver a
  [evidência de 20/10](../evidence/async-closing-datadog-2026-10-20.md).
- **R16 continua.** O pod do worker (sem reinício desde 19/10 21:45) imprime
  `CELERY_WORKER_CONCURRENCY=16` dentro do `start` do `entrypoint.sh`, que
  roda depois da carga da configuração (`entrypoint.sh:60`). O values
  pede 2.
- **Linhas `proc:`** seguem pelo `consolidate` legado. O BFF não manda o
  proc_id (`business.py:346-355` do BFF), então o fechamento é por produto,
  originador, fundo e origem. É o comportamento antigo; fechar por proc_id é
  a [tarefa 02](02-close-batch-by-proc-id.md).

## Estado em 26/10

Código conferido: cessão `b15aa94`, BFF `bb877db`, front `f7bb2d84`, argocd
`f5225da`.

- **Desde a fase 1** (20/10 23:10 UTC até 26/10 ~18:00 UTC) [C, Datadog,
  logs "Fechamento de lote fake solicitado" e "concluído"]: 130 pedidos e 130
  fechados, todos `closed` na primeira tentativa. Espera na fila de no máximo
  171 ms. Duração p50 3,7 s, p95 59 s, máximo 130 s. Maior grupo: 34.809
  pagamentos. Os seis acima de 60 s são do produto 1901 (13 a 35 mil
  pagamentos, 170 a 290 por segundo).
- **Fechados pela fase 1:** R8 (status "interrompido"), R9, R14, R17, R18,
  R19 (`acks_late`), R23 e R28.
- **Ainda abertos** [C, código]:
  - linhas por proc_id fora do fluxo novo: a rota recusa o produto
    (`refact.py:498`) e o front manda a linha ao legado (`close-batches.ts:75`).
    Inclui o B19;
  - fase 2 do front: R24 (só recarrega na transição local
    `closing→closed`, `close-batches.ts:507-535`), R25 (status com erro tenta
    de novo a cada 4 s, sem aviso, `close-batches.ts:503`), R11 (Excluir
    habilitado durante o fechamento, `close-batches.html:115`) e R7 (a rota
    enfileira sem conferir se há pagamento apto, `refact.py:489-520`);
  - D19 / R26: o UPDATE não filtra data e fecha os pendentes de todas as
    datas da chave;
  - worker: uma réplica, probes `test date`, values com concorrência 2 e
    produção com 16 (R16);
  - espera por trava de até 44 s em 21/10 com limite de 30 s, sem explicação
    (GMUD da fase 1);
  - fase 3 inteira. No ritmo do produto 1901, o limite de 480 s corta grupos
    acima de ~80 a 140 mil pagamentos; a varredura fecha grupos de 25 a 137
    mil por dia no produto 15 (D20).

## Estado em 28/10

**Produção:** **[C, Datadog]** logs "Fechamento de lote fake solicitado" e "concluído" do worker
de fechamento, de 20/10 23:10 a 28/10 14:20 UTC.
- 164 pedidos e 164 `closed`, todos na primeira tentativa. Nenhuma falha, descarte, trava
  perdida ou erro ao mandar o lote para a esteira.
- Espera máxima na fila: 171 ms.
- Duração: mediana 2,3 s, p95 58 s e máximo 130 s. Maior grupo: 34.809 pagamentos.
- Por produto: 1043 (44), 1901 (28), 713 (27), 1145 (20) e 1143 (18); os outros seis tiveram
  até 9 cada.
- Para repetir: `kube_namespace:production service:platform-cessao* "Fechamento de lote fake
  concluído"`, agrupado por `@status` e `@product_id`, com mediana, p95 e máximo de
  `@duration_ms`.

**Pendências do fechamento, em ordem:**
1. **Fase 2 (TS-5377):** está na sandbox desde 27/10 e ainda não foi testada.
   - Na rota: R7 e o vigente com guarda no fluxo novo (parte do B15).
   - Na tela: R8, R11, R24, R25, R26 e D19, R27, e o tratamento de 502 e 504.
   - No BFF: `payments_count` e exclusão com o escopo do parceiro.
   - O roteiro está em [02-03-sandbox-tests.md](02-03-sandbox-tests.md). Depois vêm a release e a
     GMUD, junto com a TS-5435.
2. **Worker dedicado (C6):** ainda tem uma réplica (`values.yaml` de produção, `replicas: 1`) e
   probes `test date`. O Celery roda sem `exec` no `entrypoint.sh` (R3), e o tempo de
   desligamento é menor que o `time_limit`. A concorrência 16 fica por enquanto (R16).
3. **Fase 0, itens sem registro de execução:** a política de memória do Redis
   (`maxmemory-policy`, `evicted_keys`) e o `statement_timeout` do papel da aplicação.
4. **Fase 3,** antes de a varredura ou o Atlas passarem pela rota nova:
   - C1/B14: o pagamento entra no vigente com guarda;
   - C2/B15: guarda no legado e no agendado, e trava por lote na `esteira_baixar`. No estresse
     de 27/10 o legado ainda despachou o mesmo vigente duas vezes: 6 em 180 casos, e 29 em 120
     no modo forçado;
   - C3/B16: exclusão com `FOR UPDATE`;
   - a C1 e a C2 precisam ser combinadas antes com o Rafael Frankl.
5. **Bugs herdados:**
   - B17: limpeza do cache depois do commit, no legado.
   - B18: continua. **[C, Datadog]** De 21/10 a 27/10 houve 11 ocorrências em
     `estados_cessao.py:82`. Falta ver se passam por `liberacao_processos`.
   - B21: lotes vazios no 1505.
6. **R7 na listagem** (linha que parece fechável e não fecha): tarefa 04, com a DBA.
7. **Adiados** ([after-v2](../after-v2.md)): P1, P3, P4, índices, D18 e D20 (b).

## 1. Tempo de execução

- **Sem medida do grupo grande.** O L3 nunca foi medido. Referência do legado
  em 7 dias, para as consultas equivalentes ao UPDATE novo (que faz as duas
  numa instrução, com um join a mais):

  | Consulta | p95 | Máximo |
  |---|---|---|
  | SELECT dos ids do grupo | 17 s | 5,2 min |
  | UPDATE `id IN` | 9,3 s | 2,6 min |

  Em 09/10 houve um SELECT de 510 mil linhas que levou 37 min.
- **R17 — limite de tempo** [C]:
  - O engine não tem `statement_timeout` nem `lock_timeout`
    (`app_factory.py:102-107`).
  - O soft limit (540 s) levanta `SoftTimeLimitExceeded`, que herda de
    `Exception`. O `except Exception` (`refact.py:381`) o engole: rollback,
    "Erro inesperado ao fechar o lote." e sucesso para o Celery.
  - Um grupo que passa de 540 s falha **sempre**, e o usuário tenta de novo
    sem saber por quê.
  - O psycopg2 bloqueado no `execute` só trata o sinal quando a query volta
    [H]. Acima de 600 s vem o SIGKILL (morte imediata do processo), sem
    resultado. O backend do Postgres segue com o UPDATE e os locks até
    terminar [H]. Validar em `pg_stat_activity`.
- **O que fazer:**
  - rodar a [SQL dos grupos pendentes](../attachments/sql/new_closing_pending_groups.sql)
    (consultas 1 e 2) na réplica;
  - pôr `SET LOCAL statement_timeout`/`lock_timeout` abaixo do soft limit,
    com motivo claro ("grupo grande demais"). O helper já existe:
    `limitar_tempo_das_consultas`, `repository.py:62`;
  - UPDATE em blocos só se a medida pedir (D20).

## 2. Fechamento perdido ou sem aviso

| # | Caso | Sequência | Efeito | Visível hoje? |
|---|---|---|---|---|
| R18 | Mensagem expira na fila [C] | trava e `expires` valem 300 s (`refact.py:54, 329-331`). Com as vagas ocupadas (concorrência 2) ou o pod fora, a mensagem passa de 300 s; no Celery 5.2.2 o `expires` vira TTL da mensagem no RabbitMQ e ela some sem log | nada fecha; o status perde a chave; o front apaga o "Fechando…" sem mensagem (R8) | não: só pela diferença entre "solicitado" e "concluído" |
| R19 | Pod morre com a task rodando [C] | sem `acks_late` (só tasks de cessão o usam); bash é PID 1 e o Celery roda sem `exec` (R3); 1 réplica; probes `test date` sempre passam (`values.yaml:256-275`) | mensagem já confirmada não volta; trava expira em até 5 min sem resultado | só pelo reinício do pod |
| R9 | Vigente fechado e sem esteira [C] | vigente commitado em `service.py:1184`, esteira só no `finally` (`refact.py:451-454`); SIGKILL não roda o `finally` | lote `pendente` fechado e parado; nada o reenvia (só `/liquidacao/reenviar` à mão) | não |
| R17 | Soft limit | ver seção 1 | "Erro inesperado" repetido | sim (log do Celery e "concluído" com `failed`) |
| R14 | Resultado sobrescrito [C] | o Lua grava o resultado sem conferir o dono (`refact.py:70-72`); um segundo job sem trava grava "Nenhum pagamento apto" por cima do `closed` | usuário vê falha num fechamento feito | não |
| R23 | Trava perdida em silêncio [C] | `_renew` ignora o retorno (`refact.py:283-292`); o cliente Redis não tem timeout (`cache.py:14`); `join()` do heartbeat sem prazo (`refact.py:303-306`) | segundo job entra com o primeiro rodando; Redis pendurado prende a task para sempre | não |

**R18 é o mais provável quando o R16 for corrigido.** Com 2 vagas, dois
fechamentos de 3 min seguidos já fazem o terceiro pedido esperar perto de
300 s. Hoje a concorrência 16 esconde isso, ao custo de memória (16 processos
em 3 GiB) e de pressão no banco.

## 3. Corridas com outros caminhos que fecham lote

UPDATE contra UPDATE está certo nos dois sentidos [C]: sob READ COMMITTED,
quem chega depois reavalia o `IS NULL`; com 0 linhas há rollback, sem lote
vazio. Os buracos estão em quem escreve sem essa guarda:

| # | Corrida | Onde | Efeito | Probabilidade |
|---|---|---|---|---|
| B14 | Pagamento "em trânsito" muda de lote [C] | a liquidação commita `cadastrado` (`estados_liquidacao.py:319-329`) e só depois entra no vigente por atribuição do ORM, sem guarda (`repository.py:459-473`) | se um fechamento (novo ou legado) pegar o pagamento no intervalo, a atribuição o move para o vigente; o lote fechado fica vazio ou parcial, e pode já ter ido à ADM [H] | possível, só em produto que acumula, durante remessa em processamento; herdada do legado |
| B15 | Vigente fechado sem trava [C] | leitura do vigente sem `FOR UPDATE` na entrada (`repository.py:443-451`) e no fechamento (`service.py:1165-1184`); fecham vigente o fluxo novo, o `POST /liquidacao/` e o beat das 19h UTC (`liquidacao_lote.py:239-317`) | pagamento entra num vigente já despachado (fica fora do arquivo); dois fechamentos despacham o mesmo vigente e a `esteira_baixar` não tem trava por lote | rara; herdada |
| B16 | Exclusão concorrente [C] | a task de exclusão carrega, apaga e commita sem revalidar o lote (`tasks/liquidacao.py:137-155`) | pagamento apagado de um lote recém-fechado; o log da exclusão grava lote `None` | rara |
| B17 | Legado: cache depois do commit [C] | `create_by_originador` limpa o cache sem try/except depois do commit (`models.py:6115-6119`) | erro do Redis deixa os lotes do legado commitados e sem esteira | rara; o fluxo novo já isola (`refact.py:470-483`) |

- **Varredura do Mercato Libero:** ela grava direto no banco com usuário
  próprio, e o SQL dela não está em nenhum repositório. **Confirmar com o
  Rafael Frankl** se as escritas usam `liquidacao_lote_id IS NULL`. Atlas e
  fetch-api só chamam a rota HTTP [C].
- **Apagar lote direto no banco** devolve os pagamentos ao lote fake (FK
  `ON DELETE SET NULL`). Lote já enviado à ADM e apagado voltaria a ser
  fechável, com risco de liquidação em dobro [C mecanismo].

## 4. O que o usuário vê (front e BFF)

| # | Caso | Efeito | Correção |
|---|---|---|---|
| R8 | Chave some do status (R18, R19, kill) | "Fechando…" volta a "Cadastrado" sem aviso (`close-batches.ts:738-742`) | avisar "não foi possível confirmar o fechamento", recarregar a lista e cancelar o status em voo no `markClosing` |
| R24 | Fechou e a linha continua | só recarrega na transição local `closing→closed` (`close-batches.ts:731-733`). Falha quando outro usuário ou aba fechou rápido, a aba ficou oculta mais de 10 min ou a réplica atrasou (listagem com `@consulta_replica`) | tratar `closed` de linha visível como motivo para recarregar e manter o botão desabilitado |
| R25 | Status falhando | retry fixo de 4 s, sem backoff, sem teto e sem aviso (`close-batches.ts:719, 754-760`); "Fechando…" para sempre | backoff até 60 s, aviso depois de 3 falhas e "demorando, confira depois" em ~15 min |
| R26 | Fecha mais do que a linha mostra | a linha não agrupa por data (`repository.py:978`), o UPDATE não filtra data e o diálogo não avisa; vale também para o legado | D19; gravar `payments_count` no resultado e mostrar no aviso |
| R27 | Falha parcial | vigente fechado e despachado, depois erro: aparece "Erro inesperado" e os `batches` do resultado são ignorados | motivo "falha depois de fechar o(s) lote(s) X" |
| R7 | Linha fechável que não fecha | listagem sem a regra da cessão; o status da linha é `min(estado)` alfabético | mesmo filtro na listagem; `exists()` na rota antes de enfileirar, com 400 imediato |
| R11 | Excluir habilitado durante o fechamento | `close-batches.ts:258` | incluir `isClosing` |
| B9 | Parceiro sem produtos vê tudo | persiste no BFF | 403 quando o parceiro não tem produto |
| R28 | Quem fechou? | ninguém guarda o usuário; `task_id` do Celery ≠ `job_id`; o BFF loga sem `job_id`; 409/400 da cessão viram `logger.error` no BFF (`errors.py:130`) | `requested_by` na trava, no log e no resultado; `apply_async(task_id=job_id)`; log de início com `queue_wait_ms` |

O BFF usa o mesmo timeout para `close` e `status`
(`config/__init__.py:164`, 60 s por padrão, sobrescrito por variável em
produção). Um 504 no `close` não prova falha, mas o texto sugere que sim.
Chamar `refreshCloseStates()` ao receber 502/504.

## 5. Quando virar o padrão

O que muda se a varredura, o Atlas e o automático passarem por esta rota:

- **Volume:** a varredura fecha grupos de 25–137 mil por dia no produto 15.
  Com 2 vagas e `expires` de 300 s, uma rodada perde pedidos (R18). Ela não
  lê a resposta, então ninguém percebe.
- **Auditoria:** o resultado fica no Redis por 10 min. Não há registro de
  quem pediu, do que fechou nem de quanto tempo levou (D18).
- **Retomada:** sem `acks_late` e sem registro durável, um deploy no meio da
  rodada perde fechamentos (R19).
- **Concorrência com o automático e o beat:** B14 e B15 passam a acontecer
  mais, porque a rota fecha vigentes no horário em que as remessas chegam.

## 6. Plano

**Fase 0 — hoje, sem deploy**

1. Acompanhar pelo [roteiro](../evidence/async-closing-monitoring.md):
   pedidos × conclusões, duração e descartes.
2. Rodar a [SQL dos grupos](../attachments/sql/new_closing_pending_groups.sql)
   na réplica (fecha o L3 e responde à D20).
3. R16: conferir se o Parameter Store de produção define
   `CELERY_WORKER_CONCURRENCY`.
4. Redis: `CONFIG GET maxmemory-policy` e `INFO stats` (`evicted_keys`). Se
   for `volatile-lru`, travas e resultados (todos com TTL) podem ser
   expulsos.
5. Banco: `SHOW statement_timeout` com o usuário da aplicação (padrão do
   papel).

**Fase 1 — cessão, antes de abrir para mais usuários ou para a varredura**

1. **Pedido aceito gravado na rota** (resultado `closing` com `job_id` e TTL
   de 1 h). Assim o `/status` distingue "em andamento" (trava) de
   "interrompido" (sem trava, resultado ainda `closing`) e devolve `failed`
   com motivo. Resolve R8 e R18 sem depender do front.
2. Tirar o `expires` (a trava com dono já impede o job velho) ou subi-lo para
   bem acima da espera aceitável.
3. `acks_late=True` e `reject_on_worker_lost=True` na task. É seguro: o
   UPDATE é idempotente pelo `IS NULL`, e a trava com dono descarta o job
   repetido (R19).
4. Despachar o vigente logo após o commit dele (R9).
5. `statement_timeout`/`lock_timeout` abaixo do soft limit, com motivo claro
   (R17).
6. Lua grava o resultado só se for o dono; `renew` devolve o resultado e
   aborta ao perder a trava; cliente Redis com timeout
   (`Cache.retrieve_client_controle()`); `join` com prazo (R14, R23, R13).
7. `task_id=job_id`, log de início com `queue_wait_ms` e `requested_by`
   (R28).
8. ~~R16 corrigido~~ (20/10: concorrência 16 é o padrão, por enquanto). Duas
   réplicas do worker, com probes que testam o Celery de verdade.

**Fase 2 — front e BFF:** R8, R24, R25, R27, R11, R7 (botão), aviso com
contagem e R26.

**Fase 3 — antes de virar o padrão**

- B14: entrada no vigente com `UPDATE ... WHERE liquidacao_lote_id IS NULL`
  conferindo o rowcount.
- B15: fechar o vigente com `UPDATE ... SET fechado = true WHERE fechado =
  false RETURNING` e trava por lote no início da `esteira_baixar`.
- B16: exclusão revalidando o lote com `FOR UPDATE`.
- Registro durável dos fechamentos (D18) e job que reenvia lote `pendente`
  sem esteira há N minutos.
- UPDATE em blocos, se a D20 pedir.
- Desligamento gracioso do worker (R3).
- Confirmar com o Rafael Frankl o SQL direto da varredura.

## Decisões abertas

- **D18 — onde fica o registro de cada fechamento.** Redis (hoje, 10 min) ×
  tabela no banco (pedido, chave, quem, status, lotes, pagamentos, início,
  fim, motivo). Recomendação: tabela, antes de virar o padrão, pela
  auditoria, pela retomada e por um status que não some.
- **D19 — fechar por data.** A chave não tem data, então fechar leva os
  pendentes de todas as datas, igual ao legado. Opções: manter e avisar na
  tela; ou pôr a data na chave. Recomendação: manter, avisar e mostrar a
  contagem.
- **D20 — grupo grande.** UPDATE único com `statement_timeout` (falha clara)
  × blocos com commit por bloco no mesmo lote, despachado no fim e retomado
  pelo mesmo lote. Decidir depois da SQL da fase 0.

## Conferido e correto (não reabrir)

- UPDATE novo × legado: sem pagamento em dois lotes nem lote vazio na
  criação [C].
- Rota, status e task leem do primário; atraso da réplica afeta só a
  listagem [C].
- Só o worker dedicado consome `fake_batch_closing_celery` em produção
  [C, Datadog: um pod lista a fila desde o deploy].
- `esteira_baixar` com lote vazio só registra warning e não falha [C].
- O erro "Erro na esteira 'NoneType' object is not iterable" existe desde
  06/10 (19 vezes até 19/10) e não vem da TS-5377. Causa em
  [B18](../bugs-found.md).
