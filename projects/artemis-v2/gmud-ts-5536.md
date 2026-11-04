# GMUD — TS-5536: lotes fake no fluxo novo (listagem, exclusão, worker), com TS-5377, TS-5435 e TS-5537

> **Status (04/11/2026, 13h30):** rascunho para a janela de hoje, **20h às 22h (Brasília)**, ou
> 23:00 a 01:00 UTC. Não criada no portal. Faltam os itens **[a preencher]** e "a confirmar".
> A reestruturação do whitelabel (18h às 20h) tem GMUD própria e vem antes desta.

Tipo: Mudança programada

## Summary

Lotes de Liquidação: lotes fake mostram os aptos e a exclusão apaga só o pendente

## Descrição

**Contexto**
- **Exclusão perigosa (B23, réplica de produção, 60 dias até 03/11):** excluir uma linha pela tela
  apaga as remessas inteiras dela, inclusive pagamentos já em lote real e enviados à
  administradora, sem como desfazer. Pela tela foram 5 pagamentos (19/10), nenhum em lote.
- **Linha "fechável" sem pagamento apto (R7) e linha por remessa que a tela não fecha (B22):** a
  listagem antiga não sabe quais pagamentos podem entrar no lote nem a modalidade do produto.
- **Contratos presos (B18, TS-5537, réplica e Datadog):** 10 contratos do produto 15 ficam em
  "liberando" com o cedente já concluído; 41 erros "'NoneType' object is not iterable" em 30
  dias. Origem: TS-187, 06/2025.
- **Deploy no meio de um fechamento (C6):** o worker (processo que executa as tarefas da fila)
  de fechamento não recebe o sinal de desligamento e é morto; o fechamento é refeito.
- **Cards:** TS-5536 (principal), TS-5377 (fase 2 do fechamento), TS-5435 (fechamento por
  remessa e modalidade de fechamento) e TS-5537 (B18).

**O que muda**
- **platform-cessao** (`release/20261104`, PR #2743 → `master`, commit `8515b71b7`: a árvore da
  `release/20261103` testada na sandbox mais a concorrência por fila, PR #2744 na sandbox):
  - rotas novas: `GET /liquidacao/fake-batches` (listagem, com `qtd_aptos`),
    `DELETE /liquidacao/fake-batches` (exclusão por linha) e
    `GET /liquidacao/fake-batches/payments` (expandir a linha); as duas leituras usam a réplica
    (cópia só de leitura do banco);
  - `POST /liquidacao/fake-batches/close/status` devolve também as exclusões (campo `operation`);
  - exclusão nova: só pagamentos sem lote da linha (na linha por origem, só o dia mostrado);
    pula liquidação em processamento ou com pagamento em lote; uma transação por liquidação; roda
    na mesma fila do fechamento (`fake_batch_closing_celery`, `cessao/app_factory.py:71`), em
    tarefas de até ~400 s que continuam sozinhas;
  - fechamento (fase 2 e TS-5435): fecha o vigente só se ainda aberto, recusa linha sem
    pagamento apto, recusa clique repetido até 30 s depois do fechamento (409); linha por
    remessa (`proc:`) fecha um lote por fundo e originador;
  - migration (alteração da estrutura do banco) `c3f81d7a5e24`: coluna nova
    `produto_config.modalidade_fechamento_lote` (manual, acumulado, automático por chave,
    automático por remessa, agendado), preenchida a partir das quatro flags, que continuam;
    encadeada em `7ddf133f1f84`, a cabeça atual da `master`;
  - cadastro e atualização do produto gravam a modalidade; acúmulo junto com fechamento por
    remessa é recusado (400 no cadastro);
  - worker de fechamento: sondas por arquivo (`cessao/utils/sondas_worker_celery.py`) e `exec`
    no `entrypoint.sh` só no worker sem consumer, para o Celery receber o sinal de desligamento;
  - concorrência por fila (`entrypoint.sh`): o Parameter Store é o mesmo para todos os pods e o
    `guardian` o aplica por cima do values, por isso a `CELERY_WORKER_CONCURRENCY=16` de lá vencia
    o `2` do values (o worker de fechamento subiu com 16 em 29/10). Agora cada worker dedicado pega
    o `N` da sua fila em `CONCORRENCIA_POR_FILA="fila=N,..."`; quem não está na lista segue igual.
    Produção: `fake_batch_closing_celery=4`, 4 por pod;
  - B18: `callbacks or []` em `cessao/framework/cessao/estados_cessao.py:84`.
- **BFF** (backend do Portal; `release/20261104-artemis`, PR #264 → `master`, commit `cbb482f`;
  é a release do whitelabel, PR #263, mais a adaptação da TS-5536):
  - listagem, expandir e exclusão pelas rotas novas da cessão; a exclusão passa a receber a chave
    da linha e o dia (`key`, `date`) no lugar dos `proc_id`, e confere o produto do usuário;
  - a consulta de status devolve as exclusões.
- **Portal** (`release/20261104-artemis`, PR #287 → `master`, commit `97da6501`; release do
  whitelabel, PR #285, mais a adaptação): mostra "N de M registros aptos"; o Fechar só habilita
  com apto; a exclusão manda a chave e o dia; a tela acompanha a exclusão pelo status.
- **Argocd** (repositório de configuração do deploy; `platform-cessao-argocd`, branch
  `chore/TS-5536-worker-fechamento`, commits `30f4814`, `6880187` e `46911fc`, sem PR; só
  `asgard-production`, a sandbox fica como está): `fake-batch-closing` com **2 réplicas** (era 1),
  sondas por arquivo (vida: `/tmp/celery_vivo` com menos de 2 min; prontidão:
  `/tmp/celery_pronto`) e sem a `CELERY_WORKER_CONCURRENCY` do values, que nunca valia. Até 8
  fechamentos ou exclusões ao mesmo tempo (2 × 4), contra 16 hoje. Continua o **único** consumidor
  da fila em produção: o `worker` e o `liquidacao` têm a lista de filas fixa no values, sem ela.

**O que não muda**
- O legado: `POST /liquidacao/`, fechamento automático e agendado, máquina de estados da
  liquidação, listagem e exclusão antigas (nenhum arquivo de `cessao/framework/liquidacao/` no
  diff). Quem usa as rotas antigas não é afetado.
- Variável nova: só a `CONCORRENCIA_POR_FILA`, no Parameter Store de produção e da sandbox, criada
  em 04/11 (a de produção conferida; a da sandbox, pelo log de partida). Fila nova: nenhuma.
- Fora desta mudança: a tradução do `refact.py` para PT-BR (fica para depois).

## Prioridade

Medium (proposta; confirmar com o usuário)

## Link Tarefa

<link do Jira da TS-5536>

## Risco

Médio. O que pode dar errado, o que acontece e o que segura.

- **Pod novo antes da migration [C no chart e no código]:** no template do
  `standard-service-chart` (2.4.17; produção usa 2.4.16, a confirmar se igual) a migration é um Job
  comum, sem gancho do argocd que a rode antes. A coluna nova está no modelo
  (`cessao/database/models.py:1498`), então um pod novo que leia `produto_config` antes de a coluna
  existir dá erro, na tela e na esteira. Segura: sync seletivo no ArgoCD, primeiro só o Job de
  migration e, com ele concluído, o resto (passo 2); migration curta (156 produtos); na sandbox,
  em 27/10, nenhum erro de coluna inexistente. Os logs da migration da cessão não chegam ao
  Datadog.
- **Migration esperando trava [H]:** incluir a coluna pede trava exclusiva na `produto_config`;
  uma transação longa na tabela faz a migration esperar e as leituras ficam na fila atrás dela. A
  migration não define `lock_timeout`. Segura: janela noturna; acompanhar o Job; DBA de prontidão
  (a confirmar).
- **Sondas antes da imagem nova [C no argocd e no código]:** a imagem atual não cria os
  arquivos das sondas; com o `30f4814` antes da tag, os pods nunca ficam prontos e são reiniciados a
  cada ~3,5 min (120 s + 3 × 30 s), matando fechamentos. Segura: o `30f4814` só junto com a tag ou
  depois.
- **Deploy no meio de um fechamento ou exclusão [C no código]:**
  - nesta troca, o pod que sai ainda roda a imagem antiga, sem `exec`: é morto depois de 30 s
    (`terminationGracePeriodSeconds`, fixo no chart), sem desligamento gracioso;
  - a mensagem volta à fila (`acks_late` e `reject_on_worker_lost`: a mensagem só sai da fila quando
    a tarefa termina) e o pod novo refaz. Repetir é seguro: o fechamento só pega pagamento sem
    lote; a exclusão retoma do cursor;
  - na 3ª entrega o job desiste e a tela mostra "interrompido" (`refact.py:84`, `:2226`, `:2559`);
  - em produção, nenhum reenvio foi observado até hoje (a confirmar);
  - chance baixa: 1 pedido de fechamento entre 20h e 22h nos últimos 14 dias (409 no total).
- **Dois reinícios do worker:** tag e branch do worker em commits separados reiniciam o worker duas vezes.
  Segura: conferir a fila vazia antes do segundo.
- **Janela entre o BFF e o Portal [C no código]:** o Portal da release das 18h manda `proc_id` na
  exclusão; o BFF novo exige `key` e responde 422. Nada é apagado. Listagem e status só ganham
  campos. Segura: subir o Portal logo depois do BFF.
- **Concorrência do worker de fechamento [C, Datadog, Parameter Store e código]:** hoje sobe com
  16 (log de partida de 29/10), porque a `CELERY_WORKER_CONCURRENCY=16` do Parameter Store vence o
  values. Com a concorrência por fila, ficam 4 por pod × 2 réplicas = até 8. Se a
  `CONCORRENCIA_POR_FILA` faltar ou vier inválida, o worker avisa no log e volta à geral: 16 por
  pod, até 32 no banco primário. Segura: conferir no log de partida dos dois pods a lista e
  `concurrency: 4` (passo 3); `statement_timeout` de 480 s e `lock_timeout` de 30 s por espera;
  uso baixo (409 pedidos em 14 dias).
- **Redis descartando chaves (B24) [C, Datadog]:** o Redis (armazenamento em memória das travas e
  dos status) descartou ~19,7 mi chaves em outubro (nenhuma de 16/10 a 03/11; 89% de memória em
  30/10). Sem a trava, o fechamento para e a tela avisa; a exclusão segue pelas guardas do banco.
- **B18 libera contratos [C, código e réplica]:** na próxima baixa do produto 15, os 10 contratos
  presos vão para `cadastrado`. Segura: alinhar com o time antes (pré-requisito).
- **Modalidade fora de sincronia [H]:** flag mudada direto no banco não atualiza a modalidade; a
  tela fecha pela modalidade. Hoje os 156 produtos estão coerentes (réplica, 28/10).
- **Fluxo novo pouco exercitado na sandbox [C, Datadog]:** desde 02/11 nenhum pedido de
  fechamento nem de exclusão chegou à sandbox (ver Evidências).

## Impacto

- **Tela de lotes de liquidação (aba lotes fake):** "N de M registros aptos"; Fechar só com apto;
  Excluir apaga só os pagamentos sem lote da linha; a tela acompanha a exclusão; expandir pela rota
  nova. Linha por remessa fecha um lote por fundo e originador.
- **Contratos:** 10 contratos do produto 15 saem de "liberando" na próxima baixa do produto.
- **Banco:** coluna e tipo novos na `produto_config`; um UPDATE de preenchimento na migration.
- **Infra:** worker de fechamento com 2 pods e sondas novas; a fila `fake_batch_closing_celery`
  leva também a exclusão; chave nova no Redis `liquidacao:fake-batch-deletion:status:*` (até 1 h).
- **Deploy:** com migration; variável nova `CONCORRENCIA_POR_FILA` no Parameter Store, já
  criada; API e workers da cessão reiniciam; sem
  indisponibilidade prevista da tela, fora os riscos acima.

## Plano de implantação

Horários em Brasília. A ordem é cessão (migration e worker), BFF e Portal.

0. **Antes das 20h:**
   - whitelabel em produção e conferido (BFF #263 e Portal #285 na `master`);
   - B18: time de acordo com a liberação dos 10 contratos (decisão de 03/11 com o Pietro);
   - testes de tela críticos na sandbox, com registro no Datadog: S1 (fechar linha por origem,
     com acompanhamento), S8 (fechar por remessa), exclusão e S2 **[a preencher]** (ver
     Evidências);
   - concorrência por fila na sandbox (PR #2744): log de partida do `fake-batch-closing` com a
     `CONCORRENCIA_POR_FILA` e `concurrency:` igual ao valor dela; worker geral com 16 **[a
     preencher]**;
   - Parameter Store de produção: `CONCORRENCIA_POR_FILA=fake_batch_closing_celery=4` (conferido
     em 04/11, 13h);
   - PRs #264 e #287: conferir que mostram só a adaptação sobre a `master` nova;
   - nenhum fechamento ou exclusão em andamento: no Datadog, "solicitado" = "concluído" por
     `job_id`; fila `fake_batch_closing_celery` vazia.
1. **Cessão: merge da PR #2743 na `master`.** Conferir a imagem `prod-<sha do merge>` **[a
   preencher]** e uma cabeça de migration só (`c3f81d7a5e24`).
2. **Cessão: tag no argocd, nos dois ambientes de produção** (`asgard-production` e
   `viva-production`, `prod-fd5fb6c` → imagem nova; commit "Update image tag in values.yaml").
   - **Sync seletivo:** com o auto-sync do app desligado no ArgoCD, sincronizar primeiro só o Job
     de migration, esperar o Completed e então o resto. Se o app não deixar desligar o auto-sync,
     seguir com a tag única e acompanhar o Job (ver Risco);
   - Job de migration concluído e coluna criada (a confirmar como conferir: painel do argocd ou
     DBA), em cada ambiente;
   - API e workers na versão nova (Datadog, por `version`), sem erro com
     `modalidade_fechamento_lote`.
3. **Argocd do worker: merge da branch `chore/TS-5536-worker-fechamento`** (3 commits, só
   `asgard-production`) logo depois do passo 2, com a imagem nova no ar e a fila vazia; nunca
   antes.
   - 2 pods `fake-batch-closing` prontos, sem reinício;
   - log de partida de cada pod: escutando só `fake_batch_closing_celery`,
     `CONCORRENCIA_POR_FILA=fake_batch_closing_celery=4` e `concurrency: 4 (prefork)`;
   - worker geral e de liquidação seguem com `concurrency: 16`.
4. **BFF: merge da PR #264 e tag `prod-<sha>`** **[a preencher]**.
   - Datadog: versão nova; `GET /operations/liquidation/fake-batches` com 200.
5. **Portal: merge da PR #287 e tag `prod-<sha>`** **[a preencher]**, logo depois do BFF, em
   todas as marcas.
   - Tela abre com "N de M registros aptos".
6. **Teste em produção:** listagem com aptos; fechar uma linha ("Fechamento de lote fake
   concluído", `closed`); acompanhamento. Exclusão só num caso real que a operação queira
   excluir, porque apaga de vez.
7. **Acompanhamento:** roteiro `evidence/async-closing-monitoring.md`, mais os eventos de
   exclusão; S1–S14 de `tasks/02-03-sandbox-tests.md` nesta semana.

## Plano de Rollback

1. **Parcial, se o problema for na tela (preferido):** Portal e depois BFF voltam às tags do
   whitelabel de hoje **[a preencher: tag do whitelabel de 04/11]**.
   - A cessão fica: rotas novas sem uso, rotas antigas iguais. Ficam o fechamento da fase 2 e da
     TS-5435 (na rota de antes), a modalidade e a B18.
   - O BFF antigo aceita o status novo (`status` é texto e campos extras são ignorados) [C no
     código].
   - Entre os dois passos, a exclusão pelo Portal antigo dá 422 (minutos).
2. **Total:** depois do item 1.
   - **Esvaziar:** nenhum fechamento ou exclusão em andamento e a fila com 0 prontas e 0 sem
     confirmação. Fechamento: até 10 min (`time_limit` de 600 s). A exclusão encadeia até 50
     tarefas de ~400 s; esperar ou aceitar que pare: a imagem antiga não conhece a tarefa
     `excluir_lote_fake` e descarta a mensagem (comportamento do Celery, a confirmar). O que foi
     apagado fica apagado.
   - **Argocd:** reverter os 3 commits da branch do worker (1 réplica, sondas `test date`) antes
     ou junto da tag.
   - **Cessão:** tag de volta para `prod-fd5fb6c`, em `asgard-production` e `viva-production`. A
     release parte de `fd5fb6ced`, a `master` de hoje; conferir no dia que nada mais subiu depois.
   - A `CONCORRENCIA_POR_FILA` pode ficar no Parameter Store: a imagem antiga não a lê.
3. **Migration:** o downgrade (desfazer a migration) não é preciso: o código antigo não usa a
   coluna, que tem padrão `manual`.
   - Esperado, não testado: o Job de migration da imagem antiga roda `flask db upgrade` com o
     banco numa revisão que ele não conhece e falha, sem efeito nos pods (não é gancho).
   - Se quiser desfazer: downgrade para `7ddf133f1f84` com a imagem nova, antes de voltar a tag
     (apaga a coluna e o tipo).
4. **O que fica para trás:**
   - a coluna, se não houver downgrade: produto alterado depois fica com a modalidade velha;
     derivar de novo antes de subir o fluxo novo outra vez;
   - lotes criados pelo fluxo novo são lotes normais e seguem a esteira;
   - pagamentos excluídos não voltam (exclusão em cascata, como sempre);
   - chaves no Redis vencem em até 1 h; a fila já existia;
   - contratos liberados pela B18 ficam `cadastrado` (estado correto).
5. **Sem deploy:** não há como desligar o fluxo por configuração. Zerar o worker acumula pedidos
   na fila; não usar.

## Evidências de validação

- **Testes:**
  - cessão `e5b886429`, 03/11/2026, ~18:59 a 19:00 UTC, suíte em Docker: **5.225 ok, 50
    pulados, 0 falhas**. A rodada é do commit da release: em 04/11 o `e5b886429` coleta 5.275
    testes (5.225 + 50); antes do merge da TS-5537 seriam 5.273. Não rodada de novo;
  - cessão `-sdbx` `b6ba0cc8d` (contém o `e5b886429`), com o westworld e o httpx da sandbox:
    5.918 ok, 50 pulados, 03/11 ~19:09 a 19:11 UTC;
  - os 8 testes de integração com Postgres e Redis reais ficam fora da suíte (entre os pulados);
    rodada no commit da release: a confirmar (sem registro no projeto);
  - migration: cabeça única (`7ddf133f1f84` na `master`, `c3f81d7a5e24` na release, conferido
    em 04/11). Upgrade, downgrade e upgrade no estresse local de 27/10
    (`evidence/closing-stress-2026-10-27.md`), na versão anterior ao `75fac8ce3` (17:56), que só
    trocou nomes, inclusive o do tipo no banco. Downgrade na versão final: a confirmar. O SQL do
    preenchimento é conferido na suíte (`test/database/test_batch_closing_modality.py`);
  - BFF `cbb482f`, 04/11/2026, ~10:18 a 10:29 UTC: **4.480 ok**, com Redis de verdade; ruff e
    black limpos nos 17 arquivos Python do merge;
  - Portal `97da6501`: árvore idêntica à da `release/20261104-sdbx` (`b02006c2`, conferido),
    validada em 04/11: build, lint (0 erros), padrões, formatação, **6.477 testes ok**, audit sem
    vulnerabilidade;
  - concorrência por fila (`54be206d0`, na release pelo `8515b71b7`): `bash -n` e 11 casos com o
    `entrypoint.sh` simulado (um e dois pares, fila fora da lista, worker geral, valor inválido e
    zero, nome parecido, espaços, worker com consumer), todos com a concorrência esperada. Na
    sandbox, pela #2744: **[a preencher: log de partida]**.
- **Sandbox (Datadog, `env:sandbox`, UTC), desde o merge de 03/11 23:45:**
  - versões: cessão `sand-6f411b3` (merge da #2739; contém o `e5b886429`); BFF `sand-99f87d3` e,
    desde 04/11 ~04:00, `sand-5f42ec6`; Portal `sand-29325b0` e depois `sand-6b2a1a7`. Todas
    contêm a adaptação (`git merge-base --is-ancestor`);
  - listagem: 90 eventos "Listagem de lotes fake concluída" (`sand-6f411b3`); cessão
    `GET /liquidacao/fake-batches` 90 × 200, p95 (95% das chamadas abaixo disso) 248 ms, máx.
    464 ms; BFF 40 × 200, p95 410 ms (`sand-99f87d3`) e 163 ms (`sand-5f42ec6`); trace
    `14193398427483852868` (04/11 10:23:59: BFF 100 ms, cessão 36 ms, 200);
  - só 1 listagem com linha: 04/11 02:16:23, 1 linha;
  - expandir: `GET /liquidacao/fake-batches/payments` 3 × 200, p95 47 ms; trace
    `13600285833268479593` (02:19:35, 48 ms);
  - status: cessão `POST /liquidacao/fake-batches/close/status` 7 × 200, p95 116 ms; BFF 6 × 200,
    p95 207 ms; trace `13595065313321491092` (02:19:30: BFF 112 ms, cessão 4 ms);
  - **fechar e excluir: nenhum registro.** De 02/11 12:00 até agora, nenhum "Fechamento de lote
    fake solicitado", nenhuma "Exclusão de lote fake solicitada" e nenhum `DELETE` de lote fake,
    na sandbox nem em outro ambiente fora da produção;
  - worker: "Warm shutdown" (desligamento gracioso) do `fake-batch-closing` em 04/11 00:49:00
    (`sand-6f411b3`): com o `exec`, o Celery recebe o sinal;
  - migration na sandbox: nenhum log com `modalidade_fechamento_lote` de 27/10 23:30 a 28/10
    06:00, na subida dela.
- **Testes de tela (checklist de 03/11, ~23h em Brasília):** listagem com aptos, expandir,
  exclusão pela tela e S2 (clique repetido) marcados ok. A listagem e o expandir aparecem no
  Datadog (acima). A exclusão e o S2 não deixaram registro na sandbox: onde rodaram, a confirmar.
  S1 e S8 pendentes, críticos até as 20h **[a preencher]**. S1–S14 de
  `tasks/02-03-sandbox-tests.md` rodam nesta semana, já em produção.
- **Produção, antes do deploy (Datadog, 04/11):** cessão em `prod-fd5fb6c` (API e workers);
  worker de fechamento com concorrência 16 (partida de 29/10 22:21); 409 pedidos de fechamento de
  21/10 a 04/11. Na sandbox, sem a variável no Parameter Store, o mesmo worker sobe com 2 (04/11
  00:49), o que isola a causa no Parameter Store de produção (`CELERY_WORKER_CONCURRENCY=16`,
  conferido em 04/11).
