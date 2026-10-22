# GMUD — TS-5377 fase 1: robustez do fechamento de lote fake

> **Status (22/10/2026, ~18:10 UTC):** já executada em produção em 20/10;
> registrar como retroativa. A evidência de uso real está preenchida (63
> fechamentos, 21/10 12:18 a 22/10 18:00 UTC, todos ok). Falta: testes
> (orquestrador), confirmar a prioridade, colar o link do Jira e entender por
> que o limite de espera por trava (30 s) não cortou esperas de até 44 s em
> 21/10 (Evidências, "a confirmar").

Tipo: Mudança não programada (já executada em 20/10/2026)

## Summary

platform-cessao e BFF: fechamento de lote fake pela tela deixa de perder
pedidos sem aviso e ganha limites de tempo no banco

## Descrição

**Contexto**
- **Primeiro dia do fechamento assíncrono em produção (20/10/2026,
  Datadog):** 25 fechamentos, todos ok. Mas 11 deles ficaram até 25 s
  parados esperando uma trava de outra transação no banco, sem limite de
  espera.
- **Estresse local, código de produção com concorrência 16:**
  - trava externa: 34 de 50 pedidos sumiram sem aviso;
  - worker parado: 10 de 10;
  - worker morto: 1 de 5.

  A linha volta ao normal na tela e nada fecha.

**O que muda**
- **platform-cessao** (PR #2683, pela `release/20261020`):
  - **Limites de banco:** cada fechamento tem limite de consulta (480 s) e de
    espera por trava (30 s), ajustáveis pelas variáveis
    `FAKE_BATCH_CLOSING_STATEMENT_TIMEOUT_MS` e
    `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS`. A tela recebe o motivo: tempo
    limite, "em uso por outro processo", interrupção ou fechamento parcial.
  - **Pedido sem trava:** o pedido é gravado junto com a trava. Se a trava
    some sem resultado, o status responde "interrompido" em vez de nada.
  - **Fila:** a mensagem não expira mais; só sai da fila quando o fechamento
    termina (`acks_late`). Um deploy ou a queda do worker a devolve à fila,
    com no máximo 2 tentativas.
  - **Esteira:** o lote vai para a esteira logo depois do próprio commit.
  - **Dono do pedido:** só ele grava o resultado. O cliente Redis da trava
    tem timeout de 2 s.
  - **Logs:** o de conclusão traz tentativa, espera na fila e quem pediu.
- **BFF** (PR #212, pela `release/20261020` do BFF): manda à cessão quem pediu (id do usuário no Azure AD,
  não o e-mail) e registra o id do job no log.

**O que não muda**
- A tela (front) e as rotas e contratos usados por ela.
- A rota antiga `POST /liquidacao/` (Atlas, varredura, linhas por proc_id).
- O banco: sem migration.
- O worker: mesmo deployment e fila, concorrência 16.

A `release/20261020` leva também a TS-5383 (lotes reais), com GMUD própria.

## Prioridade

Medium

## Link Tarefa

<link do Jira da TS-5377>

## Risco

Médio. O que pode dar errado, o que acontece e o que segura:

- **Linha com pagamentos presos por outra transação por mais de 30 s:** o
  código falha o fechamento com "Os pagamentos desta linha estão em uso por
  outro processo. Tente de novo em alguns minutos." (antes, esperava). **Não
  confirmado em produção:** em 21/10, 12:17-12:18 UTC, cinco fechamentos de 1
  pagamento esperaram de 21,6 a 44,3 s no UPDATE e fecharam, sem falha por
  "em uso" (ver Evidências). Segura: subir `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS`
  (variável e reinício do worker, sem deploy de código; as variáveis não estão
  em nenhum values do argocd, só o padrão no código; onde defini-las, a
  confirmar).
- **Grupo grande demais (acima de ~480 mil pagamentos no ritmo de
  produção):** falha com "O fechamento passou do tempo limite…", sem fechar
  nada pela metade. Antes, falhava aos 9 min com "Erro inesperado" ou sem
  resposta.
- **Redis lento ou fora do ar:** o pedido falha em 2 s com erro, em vez de
  prender processos da API da cessão. A linha mostra "interrompido" quando a
  trava vence.
- **Deploy no meio de um fechamento:** o fechamento é refeito pelo worker
  novo, no máximo 2 vezes. O UPDATE só pega pagamento sem lote, então não
  fecha em dobro (estresse: zero lote duplicado, vazio ou enviado duas vezes
  à esteira).
- **Versões misturadas durante o deploy:** a API nova com o worker antigo, e
  o contrário, convivem. O resultado no formato antigo (sem `job_id`) é
  aceito pelo código novo.

## Impacto

- **Tela:** mensagens novas de falha e "interrompido" no lugar de linha que
  voltava calada. Sem mudança de layout.
- **Banco:** dois `SET LOCAL` (limite que vale só para a transação) por
  fechamento. Sem migration.
- **Infra:** sem pod, fila ou variável obrigatória nova. As duas variáveis
  são opcionais, com padrão no código.
- **Deploy:**
  - sem indisponibilidade da tela;
  - o worker de fechamento reinicia;
  - um fechamento em andamento é refeito pelo worker novo; se for
    interrompido de novo, a tela mostra "interrompido".

## Plano de implantação

Passos **como foram feitos** em 20/10/2026 (UTC; o git estava em -03:00).

1. **PRs mescladas.** 22:47 PR #2683 (cessão) e 22:51 PR #212 (BFF) nas
   `release/20261020`; 22:53 release #2682 (cessão, merge `2eb8faacd`, leva
   também a TS-5383) e 22:54 release #213 (BFF, merge `a1d5abd`) na `master`.
2. **Cessão, API e worker juntos (argocd, 23:05:08, commit `f846929`).** Tag
   `prod-2eb8faa` em `asgard-production`.
   - Conferido (Datadog): primeiro log da API em `prod-2eb8faa` às 23:05:45; o
     worker de fechamento reiniciou às 23:05:46 e escuta
     `fake_batch_closing_celery` com concorrência 16 desde 23:05:54.
3. **BFF (argocd, 23:05:12, commit `ab7f4d1`).** Tag `prod-a1d5abd`.
   - Conferido: primeiro log em `prod-a1d5abd` às 23:07:38.
4. **Portal:** sem deploy (a tag do Portal só mudou no hotfix, 21/10 00:33).
5. **Acompanhamento** pelo roteiro
   `evidencias/acompanhamento-fechamento-assincrono.md`: pedidos ×
   conclusões, motivos de falha, "Trava do fechamento de lote fake perdida",
   "Fechamento de lote fake descartado". Resultado nas Evidências.

## Plano de Rollback

Vale para **hoje (22/10/2026)**. Voltar a imagem da cessão para `prod-f19ef2c`
(a anterior à fase 1) **desfaria também**: a TS-5383 (lotes reais, parte da
mesma release `2eb8faa`), o hotfix de pagamentos pelo lote (`prod-bcf8447`) e a
onda 6 de outro dev (`prod-fb6f409`, com `CELERY_MAX_MEMORY_PER_CHILD`).
Por isso o caminho é reverter só os merges da fase 1 e fazer deploy novo.
Testado em 22/10 numa cópia descartável do código atual:

1. **BFF (primeiro).** Reverter o PR #212 (merge `d863e1d`): o BFF deixa de
   mandar `requested_by` e de logar o `job_id`; a cessão aceita o pedido com ou
   sem `requested_by`. O BFF atual (`prod-bb877db`) foi reestruturado (TS-5394):
   o `git revert` pode dar conflito em `business.py` e `viewer.py` (a
   confirmar); resolver à mão, mantendo o resto. O log "Fake batch closing
   requested" do `prod-bb877db` já é outro (campos em
   `fake_batch_closing.*`).
2. **Cessão, reverter e fazer deploy.** `git revert -m 1 8c7870222` (PR #2683).
   - Aplica limpo sobre `fb6f409`; mexe só em `refact.py`, `schema.py`,
     `viewer.py` (2 linhas), `tasks/fake_batch_closing.py` e testes.
   - **Não reverter** a PR #2684 (pagamentos pelo lote) nem a #2682 inteira.
   - Subir a tag nova em `asgard-production` e em `viva-production`.
3. **Efeito de voltar à versão de 19/10:**
   - voltam a mensagem que expira em 300 s e some sem aviso, o `acks_late`
     ausente (pod morto perde o pedido e a linha volta calada), o cliente
     Redis sem timeout (Redis lento prende a API da cessão) e o UPDATE sem
     limite de espera por trava nem de consulta (até o soft limit de 540 s,
     terminando em "Erro inesperado");
   - o worker não muda de deployment nem de fila (sem passo no argocd).
4. **Mensagens em voo:** antes do deploy, esperar o worker esvaziar (solicitado
   = concluído por `job_id`; RabbitMQ com 0 prontas e 0 sem confirmação; até 10
   min, o `time_limit`). Com `acks_late`, o deploy de qualquer versão devolve
   à fila a mensagem em andamento e o worker novo a refaz (a confirmar em
   produção: nenhum deploy pegou um fechamento em andamento; `attempt` > 1 foi
   zero).
5. **O que fica para trás:**
   - chaves no Redis (`liquidacao:fake-batch-closing:*`, validade de até 1 h)
     com o formato novo (`job_id`, tentativas); o código de 19/10 aceita o
     registro sem dono e sobrescreve, então não precisa limpar;
   - um pedido interrompido no momento do rollback aparece como "Fechando…" na
     tela até vencer, porque o código antigo não conhece o "interrompido".
6. **Sem deploy de código:** os limites de banco aumentam pelas duas variáveis
   (`FAKE_BATCH_CLOSING_STATEMENT_TIMEOUT_MS`,
   `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS`), com reinício do worker; elas não
   estão no argocd (a confirmar onde definir; o Parameter Store pode
   sobrepor o valor do pod).

## Evidências de validação

- **Testes** (rodados de novo em 22/10/2026, 17:58–18:06 UTC, nos commits de produção):
  - cessão `2eb8faacd`: 4.849 testes, 4.808 ok, 41 pulados, zero falhas;
  - BFF `a1d5abd`: 545 testes, as mesmas 8 falhas da conciliação que já falhavam antes do merge (corrigidas na release de 21/10), nenhuma nova.
  - Números de 20/10, antes da subida (suíte completa da cessão: 4.803 testes,
    zero falhas, nos commits `d80f0f21c` e `2ab73da63`; BFF: 114 testes do
    módulo, commit `4e1cb09`), ficam como histórico.
- **Infraestrutura real:**
  - scripts Lua da trava em Redis 6.2 real: 19 cenários, entre eles pedido
    interrompido, mensagem atrasada, pedido mais novo e registro no formato
    antigo;
  - limites em Postgres 13 real: espera por trava vira "em uso", consulta
    longa vira "tempo limite", e o `SET LOCAL` não vaza para a transação
    seguinte.
- **Estresse local** (`evidencias/estresse-fechamento-2026-10-20.md`),
  código de produção × esta mudança, concorrência 16:

  | Cenário | Produção | Esta mudança |
  |---|---|---|
  | Rajada de 150 em 30 s | ok | ok |
  | Trava externa | 34 de 50 sumidos | 0 sumidos |
  | Worker parado | 10 de 10 | 0 |
  | Worker morto | 1 de 5 | 0; a linha fecha uma vez |
  | Redis fora | rota presa até 30 s | erro em 2 s, sem trava órfã |

- **Sandbox:** PRs #2681 (cessão) e #211 (BFF) entregues em 20/10, sem
  fechamento exercitado lá antes da produção.
- **Produção (20/10/2026, Datadog):**
  - cessão `prod-2eb8faa` (release #2682, com a TS-5383): API e workers
    reiniciados às 23:05–23:06 UTC;
  - o worker de fechamento escuta `fake_batch_closing_celery` com
    concorrência 16 desde 23:05:54;
  - BFF `prod-a1d5abd` (release #213) às 23:07–23:08 UTC;
  - os commits `d80f0f21c`, `2ab73da63` (cessão) e `4e1cb09` (BFF) estão
    nessas versões (`git merge-base --is-ancestor`).
- **Na subida:**
  - o `platform-cessao-beat` caiu uma vez às 23:05:48, porque falhou o
    download da ferramenta que carrega a configuração, sem relação com a
    mudança, e voltou sozinho às 23:06:09;
  - nenhum erro do código novo até 23:25 UTC.
- **Uso real depois da subida (Datadog, `env:production`, 20/10 23:06 a 22/10
  ~18:05 UTC):**
  - **Quando cada versão atendeu:** cessão `prod-2eb8faa` 20/10 23:05:45 a
    21/10 00:33; `prod-bcf8447` (hotfix) 21/10 00:33 a 20:12; `prod-fb6f409`
    (outro dev) desde 21/10 20:13. BFF `prod-a1d5abd` 20/10 23:07:38 a 21/10
    00:34; `prod-ccb8306` até 21/10 22:33; `prod-bb877db` desde então.
  - **Os primeiros fechamentos com o código novo foram só em 21/10 12:18 UTC:**
    nenhum dos pedidos da noite de 20/10 ocorreu em `prod-2eb8faa` nem em
    `prod-a1d5abd`. A evidência vem de `prod-bcf8447` e `prod-fb6f409` (cessão)
    e de `prod-ccb8306` e `prod-bb877db` (BFF), que contêm os commits
    (`d80f0f21c` e `2ab73da63` em `2eb8faacd`, `bcf84478d` e `fb6f40933`;
    `4e1cb09` em `a1d5abd`, `ccb8306` e `bb877db`, todos por
    `git merge-base --is-ancestor`).
  - **Resultado:** 63 pedidos e 63 "Fechamento de lote fake concluído", todos
    `closed` (cada `job_id` tem 1 "solicitado" e 1 "concluído"); 142.661
    pagamentos, 10 produtos, maior grupo 34.202 pagamentos. Uma consulta
    posterior já listava 65 concluídos; os 2 a mais não foram classificados
    (a confirmar). Por versão: `prod-bcf8447`, 40 fechamentos, 96.657
    pagamentos, 21/10 12:18 a 20:02; `prod-fb6f409`, 23 fechamentos, 46.004
    pagamentos, 21/10 20:39 a 22/10 18:00.
  - **Falhas e motivos:** zero `failed`, zero motivo preenchido (tempo limite,
    "em uso por outro processo", interrompido, parcial); zero "descartado",
    "Falha no fechamento", "Trava ... perdida", falha ao renovar a trava, falha
    ao enviar à esteira ou ao limpar o cache.
  - **`attempt`:** preenchido em 63 de 63, sempre 1 (nenhum reenvio por queda ou
    deploy).
  - **`queue_wait_ms`:** mínimo 5 ms, mediana ~20 ms, p95 ~109 ms, máximo 171 ms
    (65 amostras, valores aproximados); fila sem espera.
  - **Duração:** mediana 4,5 s, p95 35,9 s, máximo 52,2 s (grupo de 34.202
    pagamentos).
  - **`requested_by`:** preenchido em 63 de 63 no "concluído" (id do usuário do
    Azure AD; valor não copiado aqui).
  - **BFF, "Fechamento de lote fake solicitado":** 41 registros em `prod-ccb8306`
    (21/10 12:17 a 20:38), todos com `job_id` e `requested_by` preenchidos.
  - **Atenção, nome do log mudou:** em `prod-bb877db` (a partir de 22/10 13:31)
    o BFF loga "Fake batch closing requested", com `job_id` e `requested_by` em
    `fake_batch_closing.*` (22 de 22 preenchidos). A consulta do roteiro de
    acompanhamento, pela mensagem em português, deixou de pegar o BFF.
  - **Cessão:** `POST .../fake-batches/close` 202 em todas as 91 chamadas desde
    19/10 (28 + 40 + 23); sem 409, 400 ou 5xx.
  - **Worker:** 4 partidas (19/10 21:45, 20/10 23:05, 21/10 00:33, 21/10
    20:13), todas em deploy; concorrência 16 em todas.
- **A confirmar, achado que a GMUD não deve esconder:** das 63, 13 passaram de
  20 s e 7 de 30 s. Em 21/10, 12:17:16 a 12:18:00 UTC, cinco fechamentos de 1
  pagamento (produto 1043, fundo 209) esperaram de 21,6 a 44,3 s no UPDATE e
  terminaram todos às 12:18:00,37: o padrão da espera por trava de 20/10. O
  `lock_timeout` de 30 s da fase 1 **não** cortou a de 44,3 s e nenhum
  fechamento falhou por "em uso". Causa não levantada. Hipóteses: o
  `SET LOCAL` não vale na sessão que executa o UPDATE (pooler de conexões),
  ou a espera não é por trava do banco. Validar: amostras de atividade do
  Database Monitoring de 12:17 a 12:18 UTC de 21/10 (quem bloqueia) e um teste
  com `SHOW lock_timeout` dentro da transação do fechamento.
- **Fora desta GMUD, sem relação:** em `prod-fb6f409` (outro dev) as rotas
  `close` e `close/status` ficaram mais lentas (p95 de 203 ms e 101 ms, contra
  28 ms e 5 ms antes); a conferir se é carga ou efeito da onda 6.
