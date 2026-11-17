# Tarefa 14, Fase 0: reentrega segura e arquivo em blocos (desenho para aprovação)

Administradoras sem análogo aparecem como "adm. V", "adm. B", "adm. S" e "adm. Q" (nomes reais no arquivo privado do projeto).

12/11/2026. Só leitura; nenhum código alterado. Código: platform-cessao `origin/master` `c041122eb` (= produção), salvo onde
o texto diz outra branch (TS-5582 `e4c557399`, TS-5572 `db1582065`). Números de linha são da master. **[C]** = visto no
código, na imagem do worker (Celery 5.2.2, kombu 5.5.4) ou na réplica de leitura em 12/11; **[H]** = hipótese, com como validar.

## Revisão de 17/11/2026: esteira nova atrás de chave por produto

Decisões de 17/11 (Pietro, `decisions.md`): a TS-5737 sobe na release de 24/11 junto com os 12 cards da tarefa 13; a
decisão 1 vira uma esteira de baixa nova ao lado da atual, ligada por produto; 4 = (a); 8 = (a). As seções 1 a 8 continuam
valendo para **o que** a esteira faz; esta revisão muda **onde** o código fica e **como** ele liga. Desenho para aprovação
antes de implementar.

1. **Chave.** Coluna nova `produto_config.liquidacao_baixa_refact` (boolean, `NOT NULL`, padrão `false`), em migration
   nova. Liga e desliga pelo `PATCH /produto/<id>/` (campo em `schema_produto_config`, `cessao/api/produto/schema.py`), sem
   reiniciar nada. Os 6 produtos do ML ligam um por dia, junto com a ligação da TS-5570. A chave e a esteira antiga saem na
   TS-5612, depois de validada.
2. **Desvio.** A task atual `esteira_baixar` ganha só o desvio: depois do preâmbulo (guarda de vazio da TS-5582,
   `_fechar_vigentes_antes_do_envio` da TS-5572) e antes do `ManagerBaixa`, lê a chave do produto do lote. Ligada, enfileira a
   task nova na mesma fila e retorna; desligada, segue o código de hoje. Precisa ser outra task porque `acks_late` e
   `reject_on_worker_lost` são atributos da task, não da chamada.
3. **Task nova** `esteira_baixar_refact(lote_id, rodada=0)` em `cessao/tasks/liquidacao_lote.py`, com as duas flags e
   import local do pacote novo (padrão da TS-5572 contra o ciclo de imports).
4. **Código novo** em `cessao/framework/liquidacao/refact_baixa.py`, ao lado do legado que ele substitui (`baixar.py`,
   `estados_baixa.py`), no mesmo padrão do `refact.py` da liquidação: um arquivo de refact ao lado dos oficiais, classes com
   prefixo `Refact` e tudo o que é novo com "refact" no nome (coluna, task, método dos geradores), para que promover o refact
   e apagar o legado na TS-5612 seja mover o conteúdo para os arquivos oficiais (Pietro, 17/11). Contém: contador, teto e rodadas
   (seção 3), trava (2.3), guarda por estado (2.1) num `ManagerBaixa` filho, estados filhos que gravam a marca antes do envio
   (2.2) e pedem o arquivo em blocos, e `event_id` determinístico no callback. `ManagerBase`, `ManagerBaixa`, estados,
   emissores e geradores atuais não mudam de comportamento.
5. **Blocos.** `LiquidacaoLoteProcesso.iterar_pagamentos` e `primeiro_pagamento` no modelo (aditivos). Cada gerador ganha um
   caminho em blocos usado só pela esteira nova; o caminho atual gera o mesmo arquivo de hoje. O teste golden compara os dois
   na mesma ordem por `id`.
6. **Rodadas sem `countdown`.** Versão e `consumer_timeout` do RabbitMQ de produção não puderam ser conferidos (17/11: a
   conta de desenvolvedor não lê o Amazon MQ e o endereço do broker só existe como segredo). Para não depender deles, o atraso
   das rodadas usa a opção (b) da 3.1: fila de espera sem consumidor, com TTL por rodada e `x-dead-letter-exchange` para a
   fila de destino, declarada pelo kombu. Nenhuma mensagem fica sem confirmação esperando a hora.
7. **Reenvio manual.** `reenviar_lote_liquidacao_task` apaga o contador (chamada ao pacote novo, inofensiva com a chave
   desligada) e segue pela esteira atual, que desvia se a chave estiver ligada.
8. **Lista de reenvio seguro** (D40): constante no pacote novo.

**Como cada administradora trata envio repetido [17/11, westworld `ee5f950`, cessão `origin/master`].**

| Administradora | Como recebe | Reenviar duplica? |
|---|---|---|
| capitalis | não envia nada: arquivo vazio, devolve 200 **[C]** | não |
| adm. S | sem integração: devolve 200 e o envio é manual (`westworld <adm_s>.py:38-45`) **[C]** | não |
| dayvale | API, nome com a hora em milissegundos a cada envio (`dayvale.py:61-87`) **[C]** | **sim**; tem consulta de status por nome |
| fydd | nome com a hora a cada envio (`fydd.py:339-369`) **[C]** | **sim** |
| genius | SFTP, nome `<cnpj>_<data>_R_NNN.REM` gerado na cessão; o mesmo nome sobrescreve **[C]** | **[H]** se o `NNN` muda a cada envio |
| adm. Q | API: cria um lote do lado dela com o id do nosso lote e insere as liquidações uma a uma (`<adm_q>.py:284-345`) **[C]** | **[H]** se recusa id repetido |
| adm. V | API, com hash do conteúdo (`<adm_v>.py:31-60`) **[C]** | **[H]** se deduplica pelo hash |
| bgt | API: sobe o arquivo e cria uma operação (`bgt/bgt.py:64-130`) **[C]** | **[H]** provável |
| adm. B | SFTP, com nome gerado na cessão **[C]** | **[H]** geração do nome não conferida |

**O padrão do nome do arquivo não muda** (Pietro, 17/11: as administradoras validam o nome). Por isso nenhuma fica segura
por nome fixo. Os caminhos são consultar antes de reenviar, onde houver consulta (hoje só a dayvale, pelo nome guardado na
marca de envio), ou a confirmação da administradora de que recusa arquivo repetido (fydd, genius, adm. Q, adm. V, bgt e
adm. B). O caso só acontece se o worker morrer entre a administradora aceitar o arquivo e o commit da resposta; hoje o lote
fica parado sem aviso.

**Plano revisado** (substitui o "Plano de implementação" do fim). Branch `fix/TS-5737-reentrega-segura-baixa` da master,
`--no-track`, worktree `ts5737-cessao`. Commits `fix(TS-5737)`.

1. Chave: migration nova (o `down_revision` se acerta na montagem, como as da TS-5583 e da TS-5585), coluna no modelo,
   campo no schema. Testes: migration; `PATCH` liga e desliga.
2. Pacote `refact_baixa/`: contador, teto e rodadas por fila de espera. Testes da seção 7 (teto, rodadas) e declaração das
   filas.
3. Trava por lote (decisão 3: advisory lock, se não houver pooler em modo transação **[H]**; senão Redis com dono).
4. Guarda por estado em reentrega (`ManagerBaixa` filho).
5. Marca de envio e regra de reentrega (estados filhos, lista segura, `event_id` determinístico).
6. Task nova com as flags, desvio na `esteira_baixar` e `reenviar` apagando o contador. Testes: chave desligada segue o
   caminho atual sem mudança; ligada vai para a task nova; `test_worker_perdido.py`.
7. `iterar_pagamentos` e `primeiro_pagamento` no modelo.
8. Caminho em blocos, um commit por gerador, na ordem de volume (dayvale, fydd, genius, CNAB 444 e adm. V, bgt, adm. Q),
   com golden contra o caminho atual.
9. Validação: local (imagem do devcontainer); sandbox com a chave ligada num produto de teste (`kill -9` no filho e no pod);
   `EXPLAIN` da consulta de ids revisado pela DBA.

## Resumo

1. **Achado que muda o item 2.** Os 6 produtos do Mercato Libero (4, 15, 80, 81, 581, 1406) usam fundos com administradora
   `capitalis` e arquivo `cnab` **[C, réplica]**. O gerador é `Cnab240SisVazio`, que devolve `""`, e o comunicador devolve 200
   sem enviar nada (`westworld capitalis.py:24-45`). Para eles não há arquivo nem envio. O pico de +4,7 GB do reenvio de 11/11
   é o `lote.pagamentos` da guarda de lote vazio (`liquidacao_lote.py:93`): a carga levou ~4,5 min e o resto da esteira 14 s.
   **A TS-5582 já troca por `EXISTS`** (`lote_vazio.py:52-57`). Arquivo em blocos vale para as outras administradoras.
2. **`acks_late` + `reject_on_worker_lost` sozinhos não bastam.** Com eles o broker reentrega a mensagem, e a esteira tem
   quatro buracos: avança lote que espera a administradora, duas execuções ao mesmo tempo se a conexão cair, janela de envio
   duplicado e callback em dobro. O desenho fecha cada um (seções 2 e 3).
3. **O broker é RabbitMQ**, não Redis nem SQS: não existe `visibility_timeout`. O equivalente é o `consumer_timeout` do
   RabbitMQ (30 min por padrão desde a 3.8.15). A versão de produção está fora do repo **[H]**.
4. **Teto de tentativas:** contador em Redis por lote e estado, teto de 2 inícios. Estourou, a esteira reagenda o lote em
   3 rodadas (15 min, 1 h, 4 h; da 2ª em diante numa fila isolada) e só depois vira `errado` com log de evento (3.1).
5. **Código:** na própria task e em módulo novo `cessao/shared/baixa_liquidacao/`, não no `refact.py`. Parte da master,
   sai antes da pilha TS-5583 a TS-5572, e depende da TS-5582 em produção. Decisões na seção final.

## 1. Etapas da baixa

Termo: **idempotente** = repetir o passo não repete o efeito. Cada `save()` do estado comita a sessão inteira.

| # | Passo (master) | O que faz | Lê do banco | Manda para fora | Quando grava o estado |
|---|---|---|---|---|---|
| 0 | `esteira_baixar` `liquidacao_lote.py:81-104` | acha o lote, descarta vazio, chama o `ManagerBaixa` | lotes; **`lote.pagamentos` inteiro (:93)** | nada | não grava |
| 1 | roteamento `baixar.py:78-123`, chamado em `:142` | só em `pendente`: modo da conciliação do par produto+fundo | logs do lote, compromisso de saldo | nada | `aguardar_conciliacao` ou `enviar_revisao` e commit |
| 2 | `pendente` `estados_baixa.py:204-216` e base `:57-70` | se o raw não tem 200 do passo (`:61-62`), **gera e envia**; depois transita | raw; os geradores leem pagamentos | arquivo à administradora (`emissores/liquidacao.py:110-126`) | `append_raw` comita logo após o envio (`:122`); `liquidar()` + commit depois (`:68-69`) |
| 3 | `liquidando` `:183-201` | vai a `liquidado` **sem conferir a administradora**; a pausa (`is_estado_async`) só é checada depois da transição (`base.py:30-33`) | `liquidacao_lote_adm` | nada | `liquidar()` + commit |
| 4 | `liquidado` `:169-180` | escolhe registro, cobrança ou callback | produto | nada | via base |
| 5 | registro e cobrança `:119-163` | baixa de registro e de boleto | pagamentos só no arranjo (`registradores/arranjo_pagamento.py:28`) | HTTP ao registrador ou emissor de boleto | raw `baixar_registro`/`baixar_cobranca` + commit |
| 6 | `callback` `:91-116`, `emissores/callback.py:37-50` | solta contratos `liberando` do produto e notifica o parceiro | `proc_ids` por `DISTINCT` no banco | **POST ao Convoy, sem `timeout`** (`baixa_convoy.py:207`), `event_id` novo a cada envio (`:177`) | raw `notificar` + commit; `liberar()` + commit |
| 7 | `liberado` `:78-88` | `concluir()`, dispara `atualiza_status_contrato_task`, commit | nada | mensagem Celery, **antes do commit** (`:86-87`) | `concluido` |
| 8 | `concluido` `:73-75`; `errado`, `rejeitado` | `concluido` é final; os outros não constam em `ManagerBaixa.ESTADOS` (`baixar.py:127-140`): `KeyError` engolido | nada | nada | nada |

Transversal: exceção dentro de um estado vai a `_trata_excecao` (`estadobase.py:105-113`): log, `errado`, commit e callback de
falha ao parceiro (`estados_baixa.py:35-55`). Exceção fora dos estados é engolida em `ManagerBase.iniciar` (`base.py:36-38`):
a task termina "com sucesso" e confirma a mensagem **[C]**.

**Caminho dos 6 produtos do ML [C]:** `produto_config` com registro e boleto `nao_aplica` nos 6 (réplica). Passos 0, 1, 2
(envio vazio), 3, 4 (cai no callback), 6, 7. Único efeito externo: o POST ao Convoy. Amostra de 3 dias na réplica: 152 lotes,
todos com `capitalis`/`cnab` (fundos 3, 36 e 704).

## 2. Reexecução: o worker morre e a mensagem volta

Já existe a base certa: o passo só envia se o raw não tem resposta 200 (`emissores/base.py:13-18`), e o reenvio manual
"executa apenas as etapas que não foram bem sucedidas" (`viewer.py:540-543`). A reentrega herda isso, com estes buracos:

| Onde morre | Na reentrega | Repete efeito externo? | Proteção proposta |
|---|---|---|---|
| antes de qualquer commit (guarda, roteamento, geração) | refaz tudo; nada tinha saído | não | nenhuma |
| **durante o envio ou depois dele, antes do commit do `append_raw`** (`emissores/liquidacao.py:114-122`) | estado `pendente`, raw sem 200: **envia de novo** | sim, onde a administradora não deduplica; no ML não (envio vazio) | marca de envio antes, regra de reentrega ambígua (2.2) |
| depois do commit do `append_raw`, antes do `liquidar()` | raw tem 200: pula o envio, só transita | não | nenhuma |
| **`liquidando`, esperando a administradora** | o manager vai a `liquidado` e ao callback de aprovação **antes de a administradora responder** (`:189-193`) | efeito de negócio errado | guarda por estado, **só em reentrega** (2.1) |
| depois do POST ao Convoy, antes do `append_raw` de `notificar` | POST de novo, `event_id` novo | sim, webhook em dobro | marca antes; `event_id` determinístico |
| 2 callbacks configurados e morte entre eles | `ja_enviado_ok("notificar")` já é verdadeiro pelo 1º: **pula o 2º** (`emissores/callback.py:40-49`) | notificação faltando | marca por callback |
| `liberado`, depois do `apply_async`, antes do commit | reenvia a task | não: `atualiza_status_contrato_task` tem `not exists` e `on conflict do nothing` (`liquidacao_lote.py:209-219`) | nenhuma |
| conexão com o broker cai, processo vivo | o broker reentrega e a original **segue rodando**: duas execuções juntas | sim | trava por lote (2.3) |
| exceção Python | engolida; a task confirma; **não há reentrega** | n/a | fora do escopo (alerta de lote parado) |

**Janela de envio [C].** `append_raw` só roda depois de o comunicador responder, e comita (`models.py:462-469`). Entre a
administradora aceitar e esse commit o estado não registra o envio. Idempotência do lado da administradora **[C]**:
`capitalis` não envia nada; `genius` faz SFTP no mesmo caminho remoto e sobrescreve (`westworld genius.py:104-134`; o nome
remoto sai de `gerar_file_name`, `cnab_500_liquidacao_genial.py:179-189`, **[H]** se é estável por lote); `dayvale` e `fydd` geram nome único
por timestamp (`dayvale.py:61-87`, `fydd.py:339-369`), então **duplicam**; `dayvale` tem consulta por nome de arquivo
(`check_operation_status`, `:153`). BGT, adm. V, adm. B, adm. S e adm. Q: **não verifiquei** a deduplicação.

**2.1 Guarda por estado, só na reentrega.** A mensagem reentregue traz `request.delivery_info["redelivered"]` **[C,
`celery/worker/request.py:158`]** (já é o padrão do consumidor pika, `consumer/__init__.py:99-110`). Antes do manager, se
`redelivered` e o estado for `errado`, `rejeitado`, `descartado` (TS-5582), `concluido`, `aguarda_conciliacao` ou
`conciliacao_manual`, ou `liquidando` com `liquidacao_lote_adm` ainda `liquidando`: não aplica transição, loga um evento e
confirma. **Não vale para mensagem nova**: os dois tratadores de retorno da administradora enfileiram a esteira **antes** de
gravar `liquidado` no `liquidacao_lote_adm` (`api/callback/service.py:802-804`, `consumer/callbacks/liquidacao.py:162-169`) e
hoje dependem de o manager avançar sem conferir. Uma guarda geral os deixaria `liquidando` para sempre **[C]**.

**2.2 Marca de envio (menor proteção para a janela).** Antes de `enviar_liquidacao` e do POST do callback, gravar no raw
`{"liquidar_envio": {execucao, arquivo, em}}` e comitar (+1 commit por envio). Na reentrega, se a marca existe sem resposta
200 depois dela: administradora na lista de **reenvio seguro** (`capitalis`; `genius` se o nome remoto for estável) reenvia;
as demais **não reenviam sozinhas**: lote `errado` com log "envio interrompido, conferir na administradora", e o operador usa
`/liquidacao/reenviar` (mensagem nova, `redelivered` falso, segue). Callback: reenvia sempre, com `event_id =
uuid5(lote, tipo)` e, se o Convoy v23.11.1 aceitar, `idempotency_key` **[H]**: ver na documentação do Convoy.

**2.3 Trava por lote.** Com `acks_late`, perda de conexão duplica a execução (`worker_cancel_long_running_tasks_on_connection_loss`
fica `False`, `consumer.py:354-361`, `defaults.py:296`; o repo não define) **[C]**. A segunda execução tenta a trava e,
sem conseguir, confirma e sai com um evento. Opções na decisão 3.

## 3. Teto de tentativas

Com `reject_on_worker_lost` a reentrega **não** incrementa `request.retries` (a mensagem volta intacta; só muda
`redelivered`). Poison message (mensagem venenosa): lote que sempre estoura derruba um pod a cada volta, com até 15 outras
tasks junto.

| Onde contar | Prós | Contras |
|---|---|---|
| **A. Redis: hash `baixa:inicios:<lote>`, campo = estado, `HINCRBY` + `EXPIRE` 12 h** | atômico, nada gravado no lote antes do trabalho pesado, sem migration, padrão do fechamento fake (`refact.py:84`, `:129-145`), zera com `DEL` | volátil: `flushall` ou Redis fora zera, e o desenho falha aberto (loga e segue) |
| B. Registro no lote (log ou raw) e contar por SQL | durável, aparece na tela de logs | +1 commit por início, regra de reinício confusa (`to_pendente` de `pendente` não gera log de mudança, `models.py` `_logar_alteracao_estado`) |
| C. Só `redelivered` (cabeçalho) | zero infraestrutura | boolean: a 3ª entrega é igual à 2ª, **não há teto** |

**Recomendo A.** Conta **depois** da guarda do TS-5572 e da checagem de vazio (o `autoretry` dele conta no `retries` da
mensagem nova, outro contador). Chave por estado de entrada: avançou de estado, é outra chave. `MAXIMO_DE_INICIOS_DA_BAIXA =
2` (original + 1 reentrega; igual a `FAKE_BATCH_CLOSING_MAX_ATTEMPTS`, `refact.py:84`). Ao estourar: `inserir_log` +
`to_errado()` + `save()` + log de evento `Esteira de baixa excedeu o teto de inícios` (extra: lote, estado, inícios, limite,
`redelivered`) e **rodada automática** (3.1); `errado` só depois da 3ª rodada, sem callback de falha ao parceiro (decisão 5).
`reenviar_lote_liquidacao_task` apaga a chave; o fim em `concluido` ou `errado` também.

**3.1 Rodadas automáticas (decisão de 12/11).** Ninguém precisa olhar o lote que estoura o teto. Causa passageira (deploy,
troca de máquina, queda do broker) se resolve esperando; lote que não cabe na memória precisa de um worker só para ele.

| Rodada | Quando | Onde roda |
|---|---|---|
| 1 | 15 min depois do estouro | a mesma fila |
| 2 | 1 h depois | fila isolada `liquidacao_baixa_isolada_celery`, worker com 1 tarefa por vez (`CONCORRENCIA_POR_FILA`, `13-workers-proposal.md`) |
| 3 | 4 h depois | fila isolada |
| fim | ~5 h 15 depois do 1º estouro | `errado` + log de evento `Esteira de baixa esgotou as rodadas` (extra: lote, estado, rodada); monitor no Datadog sobre o evento (configuração, sem código) |

- **Contador:** campo `rodada` no mesmo hash Redis, por lote (não por estado), com o `EXPIRE` renovado a cada rodada. Ao
  reagendar, apaga os campos de início. `reenviar` e o fim em `concluido` ou `errado` apagam o hash. Redis fora: falha
  aberta, como o teto.
- **Mesmas proteções:** a mensagem da rodada é nova (`redelivered` falso), então leva o argumento `rodada=n` (padrão 0) e a
  esteira trata `rodada > 0` como reentrega: guarda 2.1 e regra 2.2 valem. Pod antigo não recebe mensagem com `rodada`
  na prática: o atraso mínimo (15 min) é maior que a troca de pods do deploy.
- **Atraso:** `apply_async(countdown=..., queue=...)`. **Cuidado [C, documentação do Celery]:** a mensagem com `countdown`
  fica no worker sem confirmação até a hora. Se o `consumer_timeout` do RabbitMQ (seção 4) for menor que 4 h, o broker
  fecha o canal e devolve tudo que estava sem confirmação, inclusive baixas em andamento. A versão e o `consumer_timeout`
  passam a ser pré-requisito. Se o limite valer: (a) subir o `consumer_timeout` no broker (operação) **[recomendo]**;
  (b) fila de espera sem consumidor, com TTL por rodada e `x-dead-letter-exchange` para a fila de destino, declarada pelo
  kombu.

## 4. Interação com o que existe

| Item | Valor no código | Efeito com `acks_late` |
|---|---|---|
| Broker | `get_sqs_conf` lê `get_rabbit()["cessao_uri"]` (`config/__init__.py:736-756`, `RABBITMQ_CESSAO_AMQP` `:236`); `pika` e `kombu` amqp **[C]**; o nome "sqs" é legado e `queue_name_prefix` é opção de SQS **[H]** | RabbitMQ não tem `visibility_timeout` (kombu `pyamqp` não define, **[C]**). O risco análogo é o `consumer_timeout`: delivery sem ack por mais de 30 min (padrão da 3.8.15 em diante) fecha o canal, a mensagem volta e a original segue rodando. Mensurado: 1 milhão no ML levou ~5 min. Genius e Dayvale: tempo não medido, ~3 a 5 consultas por pagamento (auditoria) **[H]**. Conferir versão e `consumer_timeout` (`rabbitmqctl environment`, API de gestão `/api/overview`) |
| `autoretry` | master: nenhum. TS-5572: `autoretry_for=(VigenteSemTravaParaOEnvio,)`, 5 x 60 s (`liquidacao_lote.py:120-130` da branch) | com `acks_late`, `retry` confirma a mensagem velha (`request.py:513-520`) e publica outra com `retries+1`: não mistura com o contador da seção 3 |
| `soft_time_limit`, `time_limit` | nenhum na task nem global (`app_factory.py:51-90`) | o limite duro **confirma** mesmo com `acks_late` (`request.py:496`): o lote ficaria parado. O suave cai em `_trata_excecao` e vira `errado`. **Não definir agora** |
| Reenvio manual | `reenviar_lote_liquidacao_task` (`liquidacao_lote.py:50-66`): `to_pendente()` + `esteira_baixar`; confirma cedo | mensagem nova, `redelivered` falso, passa pela trava; apaga o contador |
| `CELERY_MAX_MEMORY_PER_CHILD` | 2097152 KiB só no worker geral (argocd `<ambiente A>/values.yaml:184-185`) | confere depois da task e troca o filho sem `WorkerLostError`: não reentrega nem protege de pico |
| `worker_prefetch_multiplier` | 1 (`app_factory.py:63`): 16 mensagens por pod | a task longa ocupa uma vaga e o filho dela: sem perda de vazão. Pod morto devolve as não confirmadas |
| `task_acks_late` global | não definido; `acks_on_failure_or_timeout` = True (`defaults.py:245`) | só as flags da task decidem |
| Deploy | `terminationGracePeriodSeconds` ausente no argocd **[C]**; o padrão do Kubernetes é 30 s **[H]** | SIGTERM espera pouco, depois SIGKILL: é o caso de 09/11 e o que `acks_late` resolve |

## 5. Arquivo em blocos

Formatos (`emissores/liquidacao.py:26-37`): adm_v(json), adm_b(json, cnab), adm_s(cnab), **capitalis(cnab, vazio)**, bgt(csv),
genius(cnab), fydd(txt), dayvale(txt), adm_q(json). Os geradores do ML: só `Cnab240SisVazio` (`cnab240Sispag.py:104-110`).

**Leitura em blocos, em duas fases.** `liquidacao_pagamento` tem 780 milhões de linhas (347 GB) e só os índices `lote_id`
e `id`, sem `(lote_id, id)` **[C, réplica]**. Paginar por `id > último` com filtro de lote força varredura repetida; criar o
índice composto nessa tabela é caro. Proponho: (1) uma consulta de ids do lote (`ORDER BY id`; 1 milhão de inteiros ~36 MB
em lista ou 8 MB em `array`); (2) blocos por chave primária (`id = ANY(:ids)`) com `joinedload` de parcela, contrato,
sacado, endereço e só as relações que o gerador usa. O bloco é lido em **sessão curta separada**, fechada a cada bloco, para
liberar o grafo sem `expunge` e sem soltar o `lote` do chamador **[H]** conferir que nenhum gerador altera `pagamento`. API:
`LiquidacaoLoteProcesso.iterar_pagamentos(bloco=5000, carregar=...)` e `primeiro_pagamento()` (substitui `pagamentos[0]`).
Ordem passa a ser `id` (hoje a relação não tem `order_by`, `models.py:5920`); conferir com a operação.

| Gerador | Como monta hoje | Em blocos |
|---|---|---|
| Dayvale `remessa_dayvale_liquidacao.py:115-124`, `base:278-294` | gerador de detalhes + `StringIO.writelines`; contadores no trailer | trocar o laço; não precisa do lote inteiro |
| FYDD `remessa_fydd_liquidacao.py:454, 490-516` | 3 laços (2 validações + geração) | uma passada só, validando durante |
| Genius `cnab_500_liquidacao_genial.py:795-857` | lista de linhas + `"\n".join` | `writelines` incremental; o ramo "problemático" agrupa por parcela: acumular só o subconjunto problemático |
| CNAB 444 `cnab444.py:144-209` e `models.py:6166-6204` | `pagamentos_join()` já agrupa por parcela, `.all()` com 8 entidades | blocos por **parcela** (mesma estratégia de ids); `StringIO` |
| BGT `csv_liquidacao_bgt.py:70-111` | `IN` com todas as parcelas e `StringIO` | blocos; `JOIN` no lugar do `IN` (auditoria #10) |
| adm. V, adm. Q `liquidacao_<adm_q>.py:26-45` | lista de dicionários, JSON | blocos; o JSON ainda guarda a lista de dicionários |
| Capitalis | `""` | nada |

**Memória por bloco (auditoria 11/11, medida sintética, piso).** 16,9 KB por pagamento no pior caso (1 parcela por contrato):
bloco de 5.000 = ~85 MB (+2 MB de buffer do driver); bloco de 2.000 = ~34 MB. O que sobra é o arquivo: 500 colunas x 621
mil = 311 MB, ~0,9 GB com `getvalue`, zip e base64 (`westworld dayvale.py:339-377`). Pico estimado ~0,3 base + 0,09 +
0,9 = **~1,3 GB** (hoje 11,4 GB) **[H]**; 1 milhão: ~1,8 GB (extrapolação linear). Escrever em disco e subir no fim exige
westworld novo (os comunicadores recebem `str`): **fora desta fase**. Nenhum formato exige o lote inteiro para o cabeçalho
(Dayvale e FYDD consomem os detalhes depois do cabeçalho; totais vão no trailer). O resto é o ramo agrupado da Genius.

## 6. Onde o código vai e de qual branch

- **Task e flags:** `cessao/tasks/liquidacao_lote.py` (`esteira_baixar`). Ela já é a entrada única dos 8 chamadores
  (`service.py:371`, `refact.py:2491`, `callback/service.py:802`, `consumer/callbacks/liquidacao.py:75,163`,
  `conciliacao_liquidacao.py:170`, `estados_liquidacao.py:340`, `liquidacao_lote.py:41,60,307`): corrigi-la **é** a versão
  definitiva dos fluxos legado e novo.
- **Contador, trava e marca de envio:** módulo novo `cessao/shared/baixa_liquidacao/` (espelha `shared/saldo_liquidacao/`).
- **Guarda por estado:** `ManagerBaixa` (`framework/liquidacao/baixar.py`), sem mudar `ManagerBase`, que a cessão também usa.
- **Leitura em blocos:** `LiquidacaoLoteProcesso` em `database/models.py`, ao lado de `pagamentos_join`.
- **Por que não `refact.py`:** os geradores precisam da leitura em blocos e não podem importar o `refact` no topo: o `refact`
  importa `cessao.tarefas`, que importa tasks, framework, emissores e geradores (ciclo já contornado com import local na
  TS-5572, `liquidacao_lote.py` da branch). Decisão 1.
- **Branch:** da `master` (`c041122eb`), `--no-track`, ID do card ainda a definir. Sai **antes** da pilha TS-5583, 5569, 5570,
  5585, 5567, 5572 (nenhuma contém a TS-5582, que entra antes, `13-open-lot-design.md` seção 5). Conflitos previstos, todos
  triviais: com a TS-5582 nas linhas 93-100 de `esteira_baixar`; com a TS-5572 no decorador (juntar `acks_late`,
  `reject_on_worker_lost` e o `autoretry`) e na primeira linha (`_fechar_vigentes_antes_do_envio` fica antes das minhas
  guardas). A TS-5572 já tem `acks_late` + `reject_on_worker_lost` em `fechar_remessas_automaticas_presas` (`liquidacao_lote.py:286-290` da branch).
- **Dependência:** sem a TS-5582 em produção, a próxima segunda do ML repete +4,7 GB. Estado das PRs: `gh` não existe aqui,
  **não conferi**.

## 7. Testes

| Prova | Teste |
|---|---|
| flags | `test/tasks/test_worker_perdido.py`: incluir `esteira_baixar` (`acks_late` e `reject_on_worker_lost` verdadeiros) |
| guarda por estado | parametrizar todos os estados de `ManagerBaixa.ESTADOS` + `errado`, `rejeitado`, `descartado` com `redelivered` verdadeiro e falso; `liquidando` com `liquidacao_lote_adm` em `liquidando` e `liquidado`; mensagem nova segue avançando |
| morte e reentrega | banco real do teste (Postgres 13), lote de 3 pagamentos, comunicador falso que conta chamadas; injetar `BaseException` "worker morto" antes do envio, depois do envio e antes do `append_raw`, depois do `append_raw`, no POST do callback; reexecutar com `esteira_baixar.push_request(delivery_info={"redelivered": True})`; afirmar envios por administradora (seguro reenvia, outras param em `errado` com log) |
| teto | 1º e 2º início passam, o 3º reagenda a rodada 1 na mesma fila com 15 min; estado novo é chave nova; `reenviar` zera; Redis fora falha aberto com aviso |
| rodadas | rodada 1 na mesma fila, 2 e 3 na isolada com 1 h e 4 h; estouro na 3ª vira `errado` com o evento; `rodada > 0` aplica a guarda 2.1 com `redelivered` falso |
| trava | duas execuções com conexões diferentes: a 2ª sai; conexão fechada libera |
| reentrega de verdade | **sandbox**: `kill -9` no filho e depois no pod durante um lote sintético; ver a mensagem voltar (`redelivered`), o contador e o estado final. Automático opcional: `celery.contrib.testing.worker` com `memory://` e uma task que faz `os._exit` na 1ª entrega (risco de teste instável) |
| blocos | capturar SQL com `before_cursor_execute`: nenhuma consulta traz todos os pagamentos do lote; N=25, bloco=10 gera 1 consulta de ids + 3 de bloco |
| volta da lista inteira | para cada gerador, `PropertyMock(side_effect=AssertionError)` em `LiquidacaoLoteProcesso.pagamentos` durante `gerar_saida()`; mais o teste de SQL acima (falha se a coleção `_pagamentos` for carregada) |
| equivalência | arquivo em blocos igual ao da lista (golden por gerador), N=25, bloco=10, mesma ordem por `id` |
| memória | `tracemalloc` só do iterador (sem o buffer do arquivo): pico de N=2.000 e N=4.000 abaixo de `bloco x 25 KB`, e o de 4.000 não maior que o de 2.000 mais folga |

## 8. Riscos de deploy e reversão

- **`consumer_timeout`** (seção 4): tarefa acima de 30 min duplica. Conferir a versão antes; se for ≥3.8.15, medir o maior lote
  Genius e Dayvale ou subir o timeout no broker (operação).
- **Trava no banco:** advisory lock exige 1 conexão dedicada por baixa e não funciona atrás de pooler em modo transação.
  Conferir `db_pool_size` e o pooler **[H]**. Alternativa: trava Redis com dono (decisão 3).
- **Redis** do contador e da trava: falha aberta com aviso; o teto fica sem proteção enquanto ele estiver fora.
- **Fila isolada:** deploy novo no argocd (na hora do deploy) e `liquidacao_baixa_isolada_celery=1` no `CONCORRENCIA_POR_FILA`
  (Parameter Store). Limite de memória do pod pela conta do maior lote (`13-workers-proposal.md`) **[H]**. Sem o worker, a
  rodada 2 fica parada na fila: subir o worker antes da imagem nova.
- **Consulta de ids** em tabela de 347 GB: `EXPLAIN (ANALYZE, BUFFERS)` do lote 1841860 na réplica e revisão da DBA antes do merge.
- **Ordem do arquivo** muda para `id`; **sessão separada** por bloco; arquivo Genius `/tmp/cnab_liquidacao.REM` fixo continua um risco de dados (auditoria #9), fora do escopo.
- **Mensagens em voo na troca de versão:** sem mudança de assinatura da task; compatível. Web e worker não precisam subir juntos.
- **Reversão:** as flags e o resto são código: reverter a imagem. Opcional: `acks_late` e a trava por variável de ambiente
  (Parameter Store + reinício dos pods) para desligar sem imagem nova. Blocos: um commit por gerador permite reverter um.
  Sem migration, sem argocd.
- **Fora do escopo, mas relevante:** `requests.post` do Convoy sem `timeout` (`baixa_convoy.py:207,238`); `liquidar_task`
  (`liquidacao_lote.py:30-47`) também gera e envia o arquivo (mesmos blocos, sem `acks_late`); `atualiza_status_contrato_task`
  é disparada antes do commit de `concluido` (`estados_baixa.py:86-87`), **[H]** corrida que a idempotência dela esconde.

## Para decisão do usuário

Decidido em 12/11: o teto reagenda em rodadas com fila isolada (3.1), em vez de parar em `errado`. Decididas em 17/11: 1
(esteira nova com chave por produto, ver a revisão no topo), 4 = (a) e 8 = (a); a lista de reenvio seguro é a D40.

1. **Onde mora o código** (regra: correção da liquidação vai no `refact.py`). (a) Task + `shared/baixa_liquidacao/` + método
   no modelo, sem `refact.py` **[recomendo: a esteira é compartilhada, a task já é a versão final e o ciclo de imports
   impede os geradores de usar o `refact`]**; (b) tudo no `refact.py` com `esteira_baixar` delegando, ao custo de imports
   locais nos geradores.
2. **Item 2 (blocos) depois do achado do ML.** (a) Entregar antes a TS-5582 (resolve o ML) e fazer os blocos para as demais
   administradoras na ordem de volume **[recomendo, e medir na réplica o maior lote por administradora antes de priorizar]**;
   (b) manter a ordem original: blocos e reentrega juntos; (c) descartar os blocos por ora.
3. **Trava por lote.** (a) Advisory lock do Postgres em conexão dedicada, some sozinha se o processo morrer **[recomendo,
   se não houver pooler em modo transação]**; (b) trava Redis com dono, TTL e renovação (padrão do fechamento fake, mais
   código); (c) sem trava, aceitando execução dupla na perda de conexão.
4. **Envio ambíguo (2.2).** (a) Marca antes do envio e reentrega só para administradora de reenvio seguro; as outras param em
   `errado` **[recomendo]**; (b) reenviar sempre; (c) parar sempre. Quais administradoras entram na lista de reenvio seguro
   (só `capitalis`, ou `genius` também) é regra de negócio.
5. **Ao estourar o teto,** avisar o parceiro com o callback de falha (`REJECTED`)? (a) Não, só `errado` + log + evento
   **[recomendo: falha de infraestrutura não é recusa do lote]**; (b) sim, como `_trata_excecao` faz hoje.
6. **Teto:** 2 inícios **[recomendo, igual ao fechamento fake e ao consumidor]** ou 3.
7. **Dentro da Fase 0?** `timeout` no POST do Convoy (recomendo sim: sem ele um POST pendurado segura o filho e passa do
   `consumer_timeout`) e `acks_late` em `liquidar_task` (recomendo não: gera e envia, precisa de 2.2 primeiro).
8. **Ordem do arquivo** por `id` (hoje indefinida). Confirmar com a operação que nenhuma administradora depende da ordem **[H]**.

## Plano de implementação (depois da aprovação)

Substituído pelo plano revisado de 17/11, no topo. Mantido como registro.

Branch `fix/TS-<id>-reentrega-segura-baixa` da master, `--no-track`. Commits atômicos `fix(TS-<id>)`. Sem migration.

1. **Guarda por estado em reentrega** (`baixar.py`, `base.py` intacto). Teste: tabela de estados da seção 7.
2. **Contador de inícios + teto + rodadas** (`shared/baixa_liquidacao/inicios.py`, `liquidacao_lote.py` com o argumento
   `rodada`, `reenviar_lote_liquidacao_task` apaga a chave). Testes: teto, rodadas, reinício, Redis fora.
3. **Trava por lote** (`shared/baixa_liquidacao/trava.py`). Testes: duas conexões, liberação.
4. **Marca de envio e regra de reentrega** (`emissores/liquidacao.py`, `emissores/callback.py`, `baixa_convoy.py`:
   `event_id` determinístico; marca por callback). Testes: morte em cada ponto.
5. **Flags** `acks_late=True, reject_on_worker_lost=True` em `esteira_baixar` (último commit da série de reentrega, depois de
   1 a 4) e `test_worker_perdido.py`. Validação no sandbox com `kill -9`.
6. **`iterar_pagamentos` e `primeiro_pagamento`** (`models.py`). Testes: SQL capturado, memória do iterador, equivalência.
7. **Trocar o laço, um commit por gerador**, na ordem de volume (decisão 2): Dayvale, FYDD, Genius, CNAB 444 e adm. V, BGT, adm. Q.
   Cada um com o teste de `PropertyMock` e o golden.
8. **Validação:** local primeiro (imagem do devcontainer), depois sandbox (morte do filho e do pod; lote sintético grande no
   Dayvale, com `EXPLAIN` revisado pela DBA); só então release.

## Ainda por validar [H]

Versão e `consumer_timeout` do RabbitMQ de produção (agora também pelo atraso de 4 h da rodada 3); pooler entre o worker e o Postgres; idempotência de BGT, adm. V, adm. B,
adm. S e adm. Q; nome remoto estável na Genius; `idempotency_key` no Convoy v23.11.1; maior lote por administradora (Genius,
Dayvale, FYDD); `terminationGracePeriodSeconds` efetivo dos pods; estado das PRs da TS-5582 e TS-5583.
