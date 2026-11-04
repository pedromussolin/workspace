# GMUD — TS-5536: lotes fake no fluxo novo (listagem, exclusão, worker), com TS-5377 e TS-5435

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
- **Deploy no meio de um fechamento (C6):** o worker (processo que executa as tarefas da fila)
  de fechamento não recebe o sinal de desligamento e é morto; o fechamento é refeito.
- **Cards:** TS-5536 (principal), TS-5377 (fase 2 do fechamento) e TS-5435 (fechamento por
  remessa e modalidade de fechamento). A TS-5537 (B18) saiu desta mudança em 04/11, combinado com a
  revisão do time: vai depois, com calma.

**O que muda**
- **platform-cessao** (`release/20261104`, PR #2743 → `master`, commit `79f799624`: a árvore da
  `release/20261103` testada na sandbox, sem a TS-5537, mais a concorrência por fila, PR #2744 na
  sandbox):
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
- **BFF** (backend do Portal; `release/20261104-artemis`, PR #264 → `master`, commit `cbb482f`;
  é a release do whitelabel, PR #263, mais a adaptação da TS-5536):
  - listagem, expandir e exclusão pelas rotas novas da cessão; a exclusão passa a receber a chave
    da linha e o dia (`key`, `date`) no lugar dos `proc_id`, e confere o produto do usuário;
  - a consulta de status devolve as exclusões.
- **Portal** (`release/20261104-artemis`, PR #287 → `master`, commit `25867603`; release do
  whitelabel, PR #285, mais a adaptação): mostra "N de M registros aptos"; o Fechar só habilita
  com apto; a exclusão manda a chave e o dia; a tela acompanha a exclusão pelo status; o diálogo
  central sem largura definida passa a ter teto de 560 px (o modal de confirmação não estica mais
  até a borda).
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
- **Modalidade fora de sincronia [H]:** flag mudada direto no banco não atualiza a modalidade; a
  tela fecha pela modalidade. Hoje os 156 produtos estão coerentes (réplica, 28/10).
- **Fluxo novo pouco exercitado na sandbox [C, Datadog]:** desde 02/11 nenhum pedido de
  fechamento nem de exclusão chegou à sandbox (ver Evidências).

## Impacto

- **Tela de lotes de liquidação (aba lotes fake):** "N de M registros aptos"; Fechar só com apto;
  Excluir apaga só os pagamentos sem lote da linha; a tela acompanha a exclusão; expandir pela rota
  nova. Linha por remessa fecha um lote por fundo e originador.
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
   - testes de tela críticos na sandbox, com registro no Datadog e no banco: S1, S2, exclusão, S8
     e S9 ok (ver Evidências);
   - teto de largura do diálogo central: na `release/20261104-artemis`, validado e conferido na
     sandbox pela #288 (front `sand-480323e`);
   - concorrência por fila na sandbox (PR #2744): conferida em 04/11, 13h56 (ver Evidências);
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
   - Job de migration concluído e, em cada ambiente, `attachments/sql/closing-modality-validate.sql`
     na réplica (só leitura) com **0 nulos e 0 divergentes** entre a coluna nova e as flags. Se
     divergir, `closing-modality-apply.sql` (só os divergentes, numa transação que só confirma com 0
     divergentes, `lock_timeout` de 5 s) e a validação de novo;
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
     TS-5435 (na rota de antes) e a modalidade.
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
5. **Sem deploy:** não há como desligar o fluxo por configuração. Zerar o worker acumula pedidos
   na fila; não usar.

## Evidências de validação

- **Testes:**
  - cessão `79f799624` (a release sem a TS-5537, com a concorrência por fila), 04/11/2026, suíte
    em Docker com o westworld 1.36.6 da release: **5.223 ok, 50 pulados, 0 falhas**, em 66 s. Os 2
    a menos que a rodada de 03/11 (`e5b886429`, 5.225) são os testes da TS-5537;
  - cessão `-sdbx` `b6ba0cc8d` (contém o `e5b886429`), com o westworld e o httpx da sandbox:
    5.918 ok, 50 pulados, 03/11 ~19:09 a 19:11 UTC;
  - os 8 testes de integração com Postgres e Redis reais ficam fora da suíte (entre os pulados);
    rodada no commit da release: a confirmar (sem registro no projeto);
  - migration: cabeça única (`7ddf133f1f84` na `master`, `c3f81d7a5e24` na release, conferido
    em 04/11). Upgrade, downgrade e upgrade no estresse local de 27/10
    (`evidence/closing-stress-2026-10-27.md`), na versão anterior ao `75fac8ce3` (17:56), que só
    trocou nomes, inclusive o do tipo no banco. Downgrade na versão final: a confirmar. O SQL do
    preenchimento é conferido na suíte (`test/database/test_batch_closing_modality.py`);
  - modalidade de cada produto (04/11, réplica de produção, `closing-modality-preview.sql`): a
    migration grava 131 `manual`, 13 `acumulado`, 9 `automatico_por_chave`, 2
    `automatico_por_remessa` e 1 `agendado` (156 produtos), sem combinação ambígua de flags. Na
    sandbox, `closing-modality-validate.sql`: 147 produtos, 0 nulos, 0 divergentes;
    `closing-modality-apply.sql` testado com `ROLLBACK` no lugar do `COMMIT` (0 a mudar);
  - BFF `cbb482f`, 04/11/2026, ~10:18 a 10:29 UTC: **4.480 ok**, com Redis de verdade; ruff e
    black limpos nos 17 arquivos Python do merge;
  - Portal `97da6501`: árvore idêntica à da `release/20261104-sdbx` (`b02006c2`, conferido),
    validada em 04/11: build, lint (0 erros), padrões, formatação, **6.477 testes ok**, audit sem
    vulnerabilidade;
  - concorrência por fila (`dc0c82d72`, na release pelo `79f799624`): `bash -n` e 11 casos com o
    `entrypoint.sh` simulado (um e dois pares, fila fora da lista, worker geral, valor inválido e
    zero, nome parecido, espaços, worker com consumer), todos com a concorrência esperada. Na
    sandbox, pela #2744 (`sand-15d185b`, 04/11 16:56 UTC): o `fake-batch-closing` subiu com
    `CELERY_WORKER_CONCURRENCY=2` e `CONCORRENCIA_POR_FILA=fake_batch_closing_celery=4` e saiu com
    `concurrency: 4 (prefork)`; o worker geral e o de liquidação, com a mesma lista, seguem com 16.
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
- **Testes de tela na sandbox (04/11, horário de Brasília; imagens cessão `sand-15d185b`, BFF
  `sand-5f42ec6`, Portal `sand-62312c5`).** A massa saiu de uma consulta somente leitura no banco
  da sandbox com a regra da listagem (`listar_lotes_fake`): 30 linhas com aptos em 60 dias, todas
  de produtos `manual`; nenhum produto da sandbox em `automatico_por_remessa`.
  - **S1, ok (14h20):** fundo 27, dia 14/09, linha `origem:PagPmt-2026-09-14T20:47:40…` (produto
    55). "Fechamento de lote fake solicitado" e "concluído" em 4 s, `payments_count` 2; no banco,
    os 2 pagamentos no lote 50020; a tela acompanhou pelo status (10 × 200).
  - **Exclusão, ok (14h21):** fundo 27, dia 17/09, linha `origem:PagPmt-2026-09-17T20:34:05…`.
    "Exclusão de lote fake solicitada" e "concluída" em 286 ms; no banco, só essa linha saiu (26 →
    25 pendentes e 20 → 19 linhas no dia); as outras ficaram. É a correção do B23.
  - **S2, ok (16h09):** duas abas na mesma linha (fundo 27, dia 14/09, 19 aptos). A segunda aba
    já mostrou a linha em "Fechando…" pelo status compartilhado e travou o botão; o BFF recebeu um
    pedido só (202) e o fechamento saiu com os 19 pagamentos num lote só, em 1 s. O 409 do servidor
    fica coberto pelos testes da suíte (a tela não deixa chegar até ele).
  - **S8, ok (16h20):** produto antigo 25, que passou a `automatico_por_remessa` só para o teste.
    A linha virou `proc:ab083496…` e fechou com 1 pagamento num lote, em 75 ms.
  - **S9, ok (16h48):** remessa `proc:d71542a2…` do produto 25, com 2 originadores: 200 pagamentos
    em 762 ms e **2 lotes**, um por fundo e originador (no banco: lote 50023 com 194 pagamentos do
    originador 28 e lote 50024 com 6 do originador 403, ambos no fundo 23).
  - **Produto 25 depois do teste:** a modalidade foi mudada direto no banco (a rota de atualização
    não aparece no Datadog), por isso as flags antigas não acompanharam; voltou a `manual` e, na
    validação, os 147 produtos da sandbox batem com as flags (0 divergentes).
  - **Achado:** o modal de confirmação abre quase da largura da tela com o texto longo novo. A
    causa é o `DialogService`, que deixa o diálogo central sem `width` com largura automática até o
    limite da tela (já assim na `master`). A correção, com teto de 560 px para o diálogo central sem
    `width`, entrou na `release/20261104-artemis` (`25867603`, PR #287): testes primeiro (2 vermelhos
    antes; o painel media 733 px), `validate.sh` com `RESULTADO: ok` (6.483 testes) e larguras
    medidas no navegador em 1440 px (Fechar lote 976 → 560, Excluir lote 880 → 560; no celular nada
    muda). Na sandbox pela PR #288 (`sand-480323e`): conferido na tela em 04/11.
  - Os de 03/11 (checklist, ~23h): listagem com aptos e expandir aparecem no Datadog; a exclusão
    e o S2 daquela noite não deixaram registro na sandbox e foram refeitos hoje (acima). S1–S14 de
    `tasks/02-03-sandbox-tests.md` rodam nesta semana, já em produção.
- **Produção, antes do deploy (Datadog, 04/11):** cessão em `prod-fd5fb6c` (API e workers);
  worker de fechamento com concorrência 16 (partida de 29/10 22:21); 409 pedidos de fechamento de
  21/10 a 04/11. Na sandbox, sem a variável no Parameter Store, o mesmo worker sobe com 2 (04/11
  00:49), o que isola a causa no Parameter Store de produção (`CELERY_WORKER_CONCURRENCY=16`,
  conferido em 04/11).
