# 03 — Revisão adversarial antes de produção (TS-5377), 15/10/2026

Três revisões em paralelo, somente leitura, sobre as branches da TS-5377
(cessão `cb071c2d6`, BFF `9b073e2`, front `c8fbd26`, argocd `7f3c961`):
núcleo da cessão, BFF e front, e operação (deploy, infra, GMUD). Os achados
marcados **[C]** foram conferidos no código; **[H]** precisa de dado ou teste.

**Conclusão:** a solução não fecha em dobro (a proteção no banco segura todos
os cenários testados), mas **não está pronta para produção**: faltam o worker
de produção (criado pela automação no deploy; falta conferir a configuração), a ordem de deploy segura e três ajustes que evitam fechamento
perdido sem aviso. A GMUD tinha três afirmações erradas (corrigidas em
[gmud-ts-5377.md](../gmud-ts-5377.md)).

## Bloqueiam produção

| # | Achado | Onde | Efeito | Correção |
|---|---|---|---|---|
| R1 | **Worker de produção** **[C config]**: a fila não está nas listas fixas dos workers de produção, então o worker dedicado é o único consumidor | argocd `asgard-production/values.yaml:184-185, 236-237`; `vivo-production:230-231, 280-281` | **19/10: o Pietro informou que a infra é criada pela automação durante o deploy.** Resta conferir que o worker sai com `INICIAR_CONSUMER=0`, só a fila `fake_batch_closing_celery` e concorrência 2 | conferir a configuração gerada; checar 1 consumidor na fila depois do deploy |
| R2 | **Ordem de deploy** **[C]** | `entrypoint.sh:18-21` (`INICIAR_CONSUMER` só na imagem nova) | worker com imagem antiga roda o código antigo e sobe o consumer do RabbitMQ (aconteceu no sandbox, `sand-62dc772`, 14/10 16:08 UTC); front antes da cessão dá 404 nas linhas `origem:`. Com a automação no deploy, o worker já nasce com a imagem nova; sobra garantir o front depois da cessão | cessão (com o worker) → conferir consumidor → BFF → front |
| R3 | **Deploy mata o fechamento em andamento** **[C]** — rebaixado em 19/10: comportamento antigo de todos os workers; o fechamento morto é desfeito e a linha volta a ficar disponível, sem perda de dado (o legado tem o mesmo comportamento e nunca perdeu dado). O que muda é a visibilidade (R8); a janela de dado preso é a do R9, que o legado também tem | `Dockerfile:50` + `entrypoint.sh:22` (Celery filho do bash, sem `exec`); `tasks/fake_batch_closing.py:4` (sem `acks_late`); sem `terminationGracePeriodSeconds` no worker | o Celery não recebe o SIGTERM, não termina a task e leva SIGKILL; a mensagem já foi confirmada e se perde; nenhum log; no Datadog, zero "Warm shutdown" nos workers da cessão em 7 dias | `exec` no Celery (ou tini), grace period maior que o `time_limit`, avaliar `acks_late` (seguro pelo `IS NULL` + trava com dono) |
| R4 | **Limites de 540/600 s da task contra grupos grandes** **[C mecanismo, H volume]** — não é limite da rota: a rota responde 202 na hora; o limite é da task no worker, que faz o UPDATE | `tasks/fake_batch_closing.py:4`; UPDATE único em `refact.py:164-175` | psycopg2 só trata o soft limit depois da query: UPDATE longo → rollback e "Erro inesperado" sempre; hard kill deixa o backend do Postgres segurando locks | medir na réplica o SELECT equivalente para o maior grupo (produto 15, ~137 mil); `SET LOCAL statement_timeout`/`lock_timeout` abaixo do soft limit |
| R5 | **Fundo da parcela × fundo do processo** **[C código, H dado]** | `refact.py:143-147` filtra `Parcela.fundo_id` (como a listagem); legado e vigente usam `ProcessoEstado.fundo_id` (`models.py`, `create_by_originador`; `repository.py:463`) | se houver parcela com fundo nulo ou diferente do processo, um lote mistura fundos e o vigente é buscado pelo fundo errado | rodar a SQL 1 abaixo; se der diferente de zero, filtrar também pelo fundo do processo (ligado à D11) |
| R6 | **B9 (BFF)**: parceiro sem `internal_id` vê todos os produtos **[C, já registrado]** | `bugs-encontrados.md` | é o único controle de permissão do fechamento e do status novos | corrigir antes de liberar o fluxo |

## Médios

| # | Achado | Onde | Correção |
|---|---|---|---|
| R7 | **Listagem fake não aplica a regra da cessão (D9)** **[C]** — o B4 voltou: linha "fechável" que não fecha ou fecha parcial; docs diziam o contrário | `repository.py:860-1000` (sem `ProcessoEstado.estado_atual`) × `refact.py:157` | mesmo filtro na listagem e na expansão por chave; medir com a SQL 2 |
| R8 | **Descarte silencioso** **[C]**: `expires` igual ao TTL da trava; fila atrasada, worker morto ou Redis reiniciado → a chave some do `/status` e o front apaga o estado sem mensagem | `refact.py:54, 329-331, 356-363`; front `close-batches.ts:741` | tirar o `expires` (a trava com dono já cobre), gravar `failed` "expirou ou foi interrompido"; front avisar e recarregar quando `closing` some |
| R9 | **Vigente fechado e não despachado se a task morrer** **[C]** | vigente fechado e commitado no início (`service.py:1181-1185`); envio à esteira só no `finally` (`refact.py:451-454`) | despachar o vigente logo após o commit dele |
| R10 | **Front erra o estado da linha** **[C]**: `closed` visto sem `closing` antes não recarrega a lista; resposta de status antiga desfaz "Fechando…"; timers continuam após trocar de aba; recarga silenciosa pode deixar a tabela carregando | `close-batches.ts:690-760, 548-555, 321-362` | recarregar ao ver `closed` de chave na página; cancelar o status em andamento no `markClosing`; `takeUntilDestroyed` + flag no `scheduleTick` |
| R11 | **Excluir habilitado durante o fechamento** **[C botão, H efeito]** | `close-batches.ts:251-258`; exclusão relê e apaga depois (`tasks/liquidacao.py:138-155, 263-283`) | desabilitar excluir em `closing`; no legado, reconferir `liquidacao_lote_id IS NULL` antes de apagar |
| R12 | **Origem com `coalesce` não usa índice** **[C expressão, H plano]** | `refact.py:159-160` | `= origem` quando preenchida; `IS NULL OR = ''` quando vazia; conferir com a SQL 3 |
| R13 | **Redis sem timeout** **[C config, H efeito]**: Redis inacessível prende os 4 processos do uWSGI do pod (todas as rotas da cessão) | `cache/cache.py:13-14`; `app.ini:11-12` | usar `Cache.retrieve_client_controle()` (2 s) na trava e no status |
| R14 | **Trava perdida passa sem log e um job sem trava sobrescreve o resultado de outro** **[C]** | `refact.py:62-71, 283-292` | renovação que falha → warning e checar posse antes do UPDATE; não gravar "nada a fechar" sobre um `closed` mais novo |
| R15 | **Observabilidade** **[C]**: `job_id` não vira `task_id` no Celery; o BFF loga a mesma mensagem sem `job_id` (contagem dobra); 409/400 sem log na cessão; falha do Redis no fim apaga o log de conclusão; não há quem fechou | `refact.py:329, 385-405`; BFF `business.py:385-388` | `apply_async(..., task_id=job_id)`; logar antes de gravar; `user_email` no BFF; painel com solicitados, concluídos por status e tamanho da fila |

## Baixos

- Chave com número em formato estranho (`07`, `+7`, `7_0`) fecha o mesmo grupo
  com outra trava (BFF e cessão aceitam `int()`); remontar a chave canônica.
- O fechamento leva todos os pendentes da chave, de qualquer data (igual ao
  legado); avisar no diálogo ou decidir com o negócio.
- Falha ao enfileirar a esteira só loga; o lote fica `closed` e parado.
- Atraso da réplica pode trazer a linha de volta logo após fechar.
- Corrida com o acúmulo em vigente (herdada do legado).
- Front: polling de 4 s sem espera crescente quando o status falha; aviso de
  falha trocado por "Lote fechado" na mesma consulta; página vazia depois de
  fechar a última linha; contraste e `aria-live` na célula de status.
- Rolling update pode ter 2 pods do worker por alguns segundos (até 4
  fechamentos); worker com 2Gi contra 6Gi dos workers de produção; staging
  consome a fila com concorrência 16.

## Conferido e correto (não reabrir)

- Origem com `:`, espaços, acentos e `<>`: `rsplit(":", 3)` igual no BFF e na
  cessão.
- Fechar em dobro: em READ COMMITTED o Postgres reavalia
  `liquidacao_lote_id IS NULL`; rollback com 0 linhas não deixa lote vazio.
- A esteira nunca é chamada antes do commit.
- Vigente de outra linha: só fecha com origem e fundo, e a unique garante um.
- Duplo clique e outra aba: 409, tratado no front como `closing`.
- Recarregar a página: o estado vem do servidor ("Fechando…" e o motivo da
  falha por 10 min voltam).
- Redis e log: volume desprezível (JSON pequeno, TTL de 300/600 s).

## SQL para rodar na réplica

```sql
SET statement_timeout = '300s';

-- 1. R5: parcela sem fundo ou com fundo diferente do processo, nos pendentes
SELECT pa.fundo_id IS NULL AS parcela_sem_fundo,
       pa.fundo_id IS DISTINCT FROM pe.fundo_id AS fundo_diferente,
       count(*)
FROM liquidacao_processo pr
JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
JOIN contrato_parcela pa ON pa.id = lp.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
WHERE pr.data_criacao >= now() - interval '30 days'
  AND lp.liquidacao_lote_id IS NULL
GROUP BY 1, 2;

-- 2. R7: pendentes cadastrados cuja cessão ainda não está cadastrada
SELECT pe.estado_atual AS estado_da_cessao, count(*)
FROM liquidacao_processo pr
JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = pr.uuid
JOIN contrato_parcela pa ON pa.id = lp.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
WHERE pr.data_criacao >= now() - interval '30 days'
  AND pr.estado_atual = 'cadastrado'
  AND lp.liquidacao_lote_id IS NULL
GROUP BY 1
ORDER BY 2 DESC;

-- 3. R4 e R12: plano do SELECT equivalente ao UPDATE, para o maior grupo
-- (trocar pelos valores de uma linha grande real).
EXPLAIN (ANALYZE, BUFFERS)
SELECT lp.id
FROM liquidacao_pagamento lp
JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
JOIN contrato_parcela pa ON pa.id = lp.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
WHERE lp.liquidacao_lote_id IS NULL
  AND pr.estado_atual = 'cadastrado'
  AND pr.produto_id = :produto_id
  AND pe.data_delete IS NULL
  AND pe.estado_atual = 'cadastrado'
  AND c.originador_id = :originador_id
  AND coalesce(lp.origem_pagamento, '') = :origem
  AND pa.fundo_id = :fundo_id;
```

Rodar a SQL 3 também trocando `coalesce(lp.origem_pagamento, '') = :origem`
por `lp.origem_pagamento = :origem`, para comparar os planos (R12).
