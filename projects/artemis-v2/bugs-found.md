# Bugs encontrados no mapeamento

Achados durante o mapeamento de 05/10/2026 que ainda não têm tarefa. Cada um
diz como foi confirmado; ao virar tarefa, mover para `tasks/`.

## B1 — Filtro com mais de um status volta vazio

- **Onde:** BFF `src/modules/operations/liquidation_batches/business.py:240`
  manda `status=a,b` numa string só. A cessão declara `status` com
  `action="append"` (`cessao/api/liquidacao/viewer.py:174-180`), espera o
  parâmetro repetido e filtra `estado_atual IN ('a,b')`
  (`repository.py:685`, `966`).
- **Efeito:** escolher dois ou mais status na tela não traz nenhum lote.
- **Confirmado:** leitura do código dos dois lados.
- **Correção:** no BFF, um `("status", valor)` por status.

## B2 — Paginação instável em `pagamentos/query`

- **Onde:** o viewer lê `sort` mas não repassa
  (`cessao/api/liquidacao/viewer.py:1131-1144`); o repositório só ordena se
  houver `sort` (`repository.py:1094-1101`).
- **Efeito:** LIMIT/OFFSET sem ORDER BY; o Postgres não garante ordem, então
  linhas podem repetir ou sumir entre páginas.
- **Confirmado:** leitura do código.
- **Correção:** repassar `sort` e ter uma ordenação padrão com desempate por id.

## B3 — Cancelamento gravado como liquidação

- **Onde:** `atualiza_status_contrato_task`
  (`cessao/tasks/liquidacao_lote.py:151-227`) lê `tipo_liquidacao` com o tipo
  do model (`.columns(..., LiquidacaoPagamento.tipo_liquidacao)`), que devolve
  `EnumTipoRemessa.cancelamento`, e compara com a string `"cancelamento"`.
- **Efeito:** a comparação é sempre falsa; todo contrato vira
  `contrato_transacao` do tipo `liquidacao`, inclusive os cancelados.
- **Confirmado:** teste no SQLAlchemy 1.3.24 (a versão de produção) contra
  Postgres: o valor volta como `<EnumTipoRemessa.cancelamento: '0077'>` e
  `== "cancelamento"` dá `False`.
- **Correção:** comparar com `EnumTipoRemessa.cancelamento`. Avaliar se é
  preciso corrigir dados antigos.

## B4 — Lote fake visível que não fecha

- **Onde:** o fechamento exige o processo do contrato em `cadastrado`
  (`groups_pagamentos_aptos`, `cessao/database/models.py:6097`); a listagem
  fake não exige.
- **Efeito:** a linha aparece, o usuário clica em fechar e recebe 400
  "nenhum pagamento apto para liquidar".
- **Confirmado:** leitura do código. As ~3.300 respostas 400 do
  `POST /liquidacao/` em 30 dias vêm quase todas da varredura (3.274), que não
  passa pela tela; pela tela foram 4 em 7 dias. O bug existe, mas o impacto
  na tela é pequeno.
- **Correção:** alinhar o critério da listagem com o do fechamento, ou mostrar
  na linha por que ela não pode fechar.
- **13/10:** resolvido pela D9 (o fechamento deixa de exigir a cessão
  concluída), quando o P5 da tarefa 03 entrar.
- **Relacionado:** o status da linha fake é `min(estado_atual)` (ordem
  alfabética, `repository.py:933`), o que pode esconder pagamentos em
  processamento.

## B5 — Fechar lote não confere se o produto é do parceiro (segurança)

- **Onde:** BFF `POST /operations/liquidation/fake-batches/consolidate`
  (`src/modules/operations/liquidation_batches/viewer.py:324-359`) só checa o
  papel `liquidation-fake-batches:update`/`admin:update`. As listagens
  restringem aos produtos do parceiro; o fechamento não.
- **Efeito:** um usuário de parceiro com `update` pode fechar lotes de outro
  parceiro chamando a API direto.
- **Confirmado:** leitura do código.
- **Correção:** aplicar a mesma restrição de produtos das listagens.

## B6 — Baixa de um lote roda a cessão do produto inteiro

- **Onde:** `EstadoCallback.liberacao_processos`
  (`cessao/framework/liquidacao/estados_baixa.py:94-106`), na esteira de baixa
  do lote. Busca **todos** os `ProcessoEstado` do produto em `liberando` e roda
  a `ManagerCessao` sobre eles, dentro da task do lote.
- **Efeito:** a baixa de um lote faz trabalho de cessão sem relação com ele. O
  tempo da task cresce com o volume de cessões pendentes do produto, e uma
  falha nessa cessão cai no tratamento de erro da baixa (`:115-116`).
- **Confirmado:** leitura do código (achado da análise de 09/10). Custo em
  produção não medido.
- **Validar:** no Datadog, a duração dos spans de `esteira_baixar` que passam
  por `liberacao_processos` e quantos processos ela pega por execução.
- **Correção:** entender por que a cessão é liberada aqui (histórico ou regra
  de negócio) antes de mexer; se não houver motivo, mover para a esteira de
  cessão.

## B7 — Laço sem pausa na baixa do registro

- **Onde:** `EstadoBaixandoRegistro.aplica_transicao_estado`
  (`cessao/framework/liquidacao/estados_baixa.py:151-166`). Enquanto houver
  requisição de arranjo não registrada (`emissores/registro.py:98-104`), ele
  devolve o próprio estado com `is_estado_async() = False`. O laço da
  `ManagerBase.iniciar` (`cessao/framework/base.py:28-33`) repete na hora, sem
  pausa.
- **Efeito:** um `COUNT` atrás do outro no mesmo worker, dentro da mesma
  transação, até a contagem zerar. Se a requisição nunca for registrada, o
  worker fica preso.
- **Confirmado:** leitura do código. Não se sabe se acontece em produção: o
  emissor de registro não se aplica a produtos de arranjo
  (`registro.py:69-77`), então depende de existir requisição de arranjo
  pendente em lote de produto que usa registro.
- **Validar:** no Datadog, tasks `esteira_baixar` longas com muitas execuções
  da consulta de contagem.
- **Correção:** tratar o estado como assíncrono (pausa e retoma por
  callback ou reagendamento), ou limitar as tentativas.

## B8 — Status de contrato pode não ser gravado (corrida)

- **Onde:** `EstadoLiberar.aplica_transicao_estado`
  (`cessao/framework/liquidacao/estados_baixa.py:78-88`) enfileira
  `atualiza_status_contrato_task` (`:86`) **antes** de gravar o lote como
  `concluido` (`:87`). A task só grava `contrato_transacao` se todos os lotes
  do contrato estiverem `concluido` (`tasks/liquidacao_lote.py:209-214`).
- **Efeito:** se o worker pegar a task antes do commit, o lote ainda aparece
  como `liberado`, o contrato é descartado e nada tenta de novo. O contrato
  quitado fica sem o marco de liquidação, que é usado para permitir nova
  cessão do título, nas regras de duplicidade e na baixa do registro.
- **Confirmado:** a ordem está no código. Se acontece em produção, não foi
  medido.
- **Validar:** contar lotes `concluido` com contratos de parcelas todas
  fechadas e sem `contrato_transacao` de liquidação ou cancelamento.
- **Correção:** enfileirar depois do commit. Relacionado ao B3 (mesma task) e
  ao opcional O3 da [tarefa 03](tasks/03-closing-analysis.md).

## B9 — Parceiro sem `internal_id` enxerga todos os produtos (segurança)

- **Onde:** BFF `src/shared/repository/users.py:33-50` e
  `src/shared/business/users.py:128-131`. Para quem não é PLGN,
  `get_partner_internal_id_list` devolve `[]` quando falta `client_id`, ele não
  é inteiro ou nenhum produto tem `internal_id`. A busca de fundos vai sem
  `identificador_parceiro`, e a cessão só filtra com a lista preenchida
  (`cessao/api/fundo/repository.py:27`).
- **Efeito:** um parceiro com cadastro incompleto lista, fecha e consulta
  status de lotes de qualquer produto. Enfraquece o B5.
- **Confirmado:** leitura do código no code review da TS-5377 (14/10). Não se
  sabe se há usuários nessa situação.
- **Correção:** em `get_allowed_product_ids`, lista vazia para não PLGN vira
  `[]` (nenhum produto) ou 403, nunca busca sem filtro.

## B10 — Rotas de lote sem checagem de produto (segurança)

- **Onde:** BFF `liquidation_batches/viewer.py`: `delete_batch`,
  `get_payments_by_proc_id` (com `key`/`proc_id`) e
  `export_rejected_payments`.
- **Efeito:** parceiro com o papel certo exclui lote ou lê pagamentos de outro
  produto passando a chave ou o proc_id.
- **Confirmado:** leitura do código no code review da TS-5377 (14/10).
- **Correção:** a mesma restrição de produtos da listagem e do fechamento.

## B11 — Parceiro sem fundos recebe 500

- **Onde:** BFF `src/shared/business/users.py:136` lança
  `Exception("User has no associated products.")`.
- **Efeito:** vira 500 genérico. Depois da TS-5377 também atinge o consolidate
  legado e a rota de status, que a tela consulta em loop.
- **Confirmado:** leitura do código no code review da TS-5377 (14/10).
- **Correção:** responder 403.

## B12 — Acúmulo de liquidações ignora o estado da cessão (importante)

- **Onde:** `EstadoCadastrado.acumula_liquidacao`
  (`cessao/framework/liquidacao/estados_liquidacao.py:350`) chama
  `RepositoryLiquidacao.insert_pagamento_into_lote`
  (`cessao/api/liquidacao/repository.py:459-472`) em produto com
  `acumula_liquidacoes`.
- **Efeito:** o pagamento entra no lote vigente (lote real) assim que a
  liquidação vira `cadastrado`, sem checar a cessão. Ao fechar o vigente, o
  lote segue para a `esteira_baixar` e o arquivo pode ir para a administradora
  antes de a cessão terminar. Contraria a D9 revista (14/10): a listagem e o
  fechamento da TS-5377 exigem a cessão `cadastrado`, o acúmulo não.
- **Confirmado:** leitura do código. **Não confirmado:** quantos casos
  acontecem na prática (falta medir na réplica).
- **Correção:** só acumular quando a cessão estiver `cadastrado`; o resto fica
  sem lote, aparece na listagem fake e cai no fechamento novo. Muda o
  comportamento de todos os produtos que acumulam, então precisa de aval do
  negócio. Fica fora da TS-5377 (legado intocado). Ver
  [after-v2.md](after-v2.md#acúmulo-de-liquidações-e-a-cessão-b12).

## B13 — Repasse para a Genius usa só o primeiro arquivo do parceiro

- **Onde:** no modo repasse, o CNAB enviado à Genius vem de um único arquivo
  do parceiro. Na cessão, do anexo do **primeiro contrato** do lote, filtrado
  pelos contratos do lote (`geradores/remessa_genius.py:51-80`, `:95-135`). Na
  liquidação, do proc_id do **primeiro pagamento**, sem filtro
  (`geradores/cnab_500_liquidacao_genius.py:63-77`, `:132-175`).
- **Efeito (hipótese):** num lote com contratos ou pagamentos de mais de um
  arquivo do parceiro, a cessão deixa de fora os contratos que não estão no
  primeiro arquivo, e a liquidação manda o arquivo inteiro do primeiro proc_id,
  inclusive pagamentos que não são do lote, e não manda os outros.
- **Confirmado:** leitura do código (14/10/2026) e Datadog (15/10/2026): em
  30 dias, 3 nomes de arquivo foram enviados por 2 a 5 lotes de liquidação
  do mesmo fundo em segundos, todos com data anterior ao envio (arquivo do
  parceiro). Esses lotes concentram avisos de recusa sem pagamento
  correspondente. Ver
  [evidência](evidence/genius-resend-datadog-2026-10-15.md#2-mesmo-nome-de-arquivo-em-lotes-diferentes).
- **Validar:** contar lotes de fundos da Genius em modo repasse com mais de um
  proc_id (liquidação) ou com contratos de mais de um arquivo (cessão).
- **Relacionado:** [tarefa 02](tasks/02-close-batch-by-proc-id.md) (fechar
  por proc_id daria um arquivo por lote) e D3 (decidida em 13/10: um lote por
  proc_id e fundo).
- **Correção:** depende da validação; se existir, montar o arquivo a partir de
  todos os arquivos do lote ou fechar esses produtos por proc_id.

## B14 — Pagamento em trânsito muda de lote (corrida, importante)

- **Onde:** a liquidação commita `cadastrado` em `EstadoSalvo`
  (`cessao/framework/liquidacao/estados_liquidacao.py:319-329`) e só depois
  `acumula_liquidacao` põe o pagamento no vigente com
  `pagamento.liquidacao_lote = lote` (`cessao/api/liquidacao/repository.py:459-473`),
  um UPDATE por id sem `liquidacao_lote_id IS NULL`.
- **Efeito:** se um fechamento (novo ou legado) pegar o pagamento nesse
  intervalo, a atribuição seguinte o tira do lote fechado e o põe no vigente.
  O lote fechado fica vazio ou parcial, e pode já estar na esteira. Se o
  arquivo desse lote já tiver saído, o pagamento vai em dois arquivos
  (hipótese).
- **Confirmado:** leitura do código (20/10/2026, `f19ef2cef`). Só em produto
  com `acumula_liquidacoes`, durante remessa em processamento.
- **Validar:** consulta 3 de
  [attachments/sql/new_closing_pending_groups.sql](attachments/sql/new_closing_pending_groups.sql);
  lotes com `data_atualizacao` de pagamento posterior ao fechamento.
- **Correção:** atribuir ao vigente com UPDATE guardado (`IS NULL`) e conferir
  o rowcount, ou na mesma transação que grava `cadastrado`. Ver
  [03-post-production-cases.md](tasks/03-post-production-cases.md#3-corridas-com-outros-caminhos-que-fecham-lote).

## B15 — Lote vigente fechado e alimentado sem trava (corrida)

- **Onde:** a entrada no vigente lê sem `FOR UPDATE`
  (`repository.py:443-451`; `lock=False` em `:370-381`); o fechamento também
  (`service.py:1165-1184`: SELECT `fechado == False` e `save()`). Fecham
  vigente o fluxo novo, o `POST /liquidacao/` e o beat das 19h UTC
  (`tasks/liquidacao_lote.py:239-317`). A `esteira_baixar` não tem trava por
  lote (`tasks/liquidacao_lote.py:81-104`; idempotência só por
  `ja_enviado_ok`).
- **Efeito:** um pagamento entra num vigente já fechado e despachado e pode
  ficar fora do arquivo da ADM. Dois fechamentos simultâneos despacham o mesmo
  vigente, e dois workers podem gerar o arquivo (hipótese).
- **Confirmado:** leitura do código (20/10/2026). Herdado do legado.
- **Correção:** `UPDATE liquidacao_lote_vigente SET fechado = true WHERE ...
  AND fechado = false RETURNING`, `FOR UPDATE` na entrada e trava por lote no
  início da `esteira_baixar`.

## B16 — Exclusão de liquidação concorrente com fechamento

- **Onde:** a task de exclusão carrega os pagamentos, apaga e commita sem
  revalidar o lote (`tasks/liquidacao.py:137-155`). A validação roda antes,
  na rota (`validator.py:87-126`).
- **Efeito:** um pagamento recém-fechado é apagado do lote; o log da exclusão
  grava `liquidacao_lote_id` `None` (valor lido antes).
- **Confirmado:** leitura do código (20/10/2026). Rara.
- **Correção:** na task, `FOR UPDATE` nos pagamentos e abortar se o lote já
  não for nulo.

## B17 — Legado: limpeza do cache depois do commit derruba a esteira

- **Onde:** `create_by_originador` chama `fechar_liquidacao_lote_fake_cache`
  sem try/except depois do commit (`models.py:6115-6119`); um `KeyError` no
  `del` também é possível (`listeners.py:223-224`).
- **Efeito:** erro do Redis sobe antes de `_enviar_para_esteira`
  (`viewer.py:404`) e os lotes commitados ficam sem esteira.
- **Confirmado:** leitura do código (20/10/2026). O fluxo novo já isola isso
  (`refact.py:470-483`).
- **Correção:** o mesmo try/except do fluxo novo.

## B18 — "Erro na esteira 'NoneType' object is not iterable"

- **Onde:** `_existe_callback` itera `objeto_esteira.callbacks`
  (`framework/cessao/estados_cessao.py:80-89`), que é `None` por padrão em
  `TituloContrato` (`dataclass.py:96-108`). Dois caminhos montam o título sem
  callbacks: `liberacao_processos` (`framework/liquidacao/estados_baixa.py:96-104`), chamado no fim
  da baixa de qualquer lote, e `esteira_aditamento` (`tasks/cessao.py:49-54`).
  O `_trata_excecao` chama `_finaliza_esteira` de novo e levanta outra vez.
- **Efeito:** a liberação dos contratos `liberando` do produto é abortada e o
  contrato continua `liberando`. O lote em si segue.
- **Confirmado:** código (20/10/2026); Datadog: 19 ocorrências de 06/10 a
  19/10 no `platform-cessao-worker`. Não vem da TS-5377.
- **Validar:** stack trace (passa por `liberacao_processos` ou por
  `esteira_aditamento`?) e contagem de contratos `liberando` por produto.
- **Correção:** `callbacks` com lista vazia por padrão.

## B19 — Remessa por proc_id não fecha quando o último a terminar é rejeitado

- **Onde:** só o estado `cadastrado` tenta fechar o lote
  (`framework/liquidacao/estados_liquidacao.py:342-358`); rejeitado e errado
  não chamam `lote_automatico`. O portão conta os processos terminais já
  commitados e só fecha se a conta bater o total do Redis
  (`database/models.py:5549-5583`). A rede de segurança (beat das 19h UTC,
  `backstop_por_proc_id`) só roda para produto com `baixa_por_agendamento`
  ligado (`tasks/liquidacao_lote.py:240-245`). Linhas da `master` `b15aa94`.
- **Efeito:** **[C]** se o último processo da remessa termina rejeitado,
  ninguém vê a conta completa e o lote fica fake até alguém fechar pela tela.
  **[H]** o mesmo vale quando os últimos cadastrados commitam juntos e cada um
  não vê os outros; validar comparando a ordem de término das remessas que
  não fecharam sozinhas. Não há log quando o portão não abre.
- **Confirmado:** réplica e Datadog (26/10/2026), produto da Dots: remessa
  de 6.972 com 6.808 cadastrados e 164 rejeitados, nenhum em processamento e
  nenhum lote. O último a terminar foi um rejeitado, 152 ms depois do último
  cadastrado. O produto está com `baixa_por_agendamento` nulo. No Datadog, só
  os três logs de entrada da remessa, sem erro de task.
- **Correção:** tentar o portão também ao terminar em rejeitado ou errado (o
  claim no Redis já evita fechamento duplo) e contar os terminais num contador
  do Redis incrementado depois do commit, em vez de contar no banco. Avaliar o
  backstop para todo produto com `fechar_lote_por_proc_id`.
- **Status (27/10):** fica para a migração do automático (fluxo novo só na tela); a remessa presa fecha pela linha `proc:` na tela.
- **Onde entra:** item 4 da [tarefa 02](tasks/02-close-batch-by-proc-id.md)
  (automático por proc_id), não no fechamento novo da TS-5377: este só aceita
  chave `origem:` (`api/liquidacao/refact.py:203-207`); a linha `proc` segue no
  legado (decisão de 13/10). O gatilho pode ir antes, sozinho.
- **Paliativo sem deploy:** ligar `baixa_por_agendamento` no produto (só o
  beat lê esse campo). Fecha às 19h UTC, depois do corte padrão da
  conciliação (14h BRT): o lote cairia na conciliação manual.

## B20 — Rotas do BFF sem o escopo do parceiro (já controlado no BFF)

- **Onde:** o BFF já lista essas rotas como pendentes no teste de arquitetura
  `tests/test_arch_partner_scope.py` (`PENDING_ROUTES`, teto que só desce; 87 em `bb877db`), com
  a nota de cada uma (pagamentos, exportações, saldo, extrato, CNAB, conciliação). Não é achado
  novo: em 27/10 eu o registrei sem ver essa lista.
- **Fase 2 (A2 do [plano](tasks/02-03-implementation-plan.md)):** o `DELETE /batches` passou a
  conferir o `product_id` e saiu da lista (teto 86). O `proc_id` da exclusão continua sem
  conferência própria. **[H]** A cessão filtra os pagamentos pelo produto e pelo proc_id, então
  o proc_id de outro parceiro não acharia nada; validar na rota de exclusão da cessão.
- **Resto:** segue a lista do BFF, fora desta tarefa.

## B21 — Lotes reais sem pagamento no produto 1505

- **Onde:** réplica, 27/10/2026, consulta 4 de
  [proc_id_batches_profile.sql](attachments/sql/proc_id_batches_profile.sql):
  2 dos 30 lotes do 1505 criados de 21 a 27/10 não têm nenhum pagamento.
- **Efeito:** **[C]** lote vazio na tela de lotes reais. **[H]** causas
  possíveis: exclusão de pagamento depois do fechamento (B16) ou lote criado
  sem a guarda do rowcount. Validar pela data dos lotes contra os logs de
  exclusão e de criação.
- **Correção:** depende da causa; a B16 (C3 do plano) cobre a primeira.

## Menores

- `export_batches` no BFF está sem `self` (`business.py:326-328`); a rota
  `GET .../fake-batches/export` daria 500. O front não chama.
- `GET .../real-batches//statement` no BFF tem barra dupla no caminho; o
  front não chama.
- O BFF cria um `httpx.AsyncClient` novo a cada chamada à cessão, sem reuso de
  conexão (`src/services/platform_cessao/__init__.py:29-90`).
