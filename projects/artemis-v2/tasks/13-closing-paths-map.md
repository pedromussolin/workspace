# Mapa dos fechamentos de lote de liquidação (platform-cessao)

> Revisão de 05/11: a consequência de G4 (o fluxo novo não fecha vigente sem pagamento solto) foi
> conferida em `api/liquidacao/refact.py:965` (`has_fake_batch_payments`). A varredura roda 4 vezes por
> dia útil, não 1 ([automações](13-automations-survey.md)).

Base: `origin/master` 579ad13e3 (produção de 04/11/2026). Só leitura. Caminhos relativos a `cessao/`.
Legenda: **[C]** visto no código; **[H]** hipótese (a consulta que valida vem no texto).
Termos: *lote real* = `LiquidacaoLoteProcesso`; *lote fake* = pagamentos sem lote (`liquidacao_lote_id` nulo) que a tela agrupa por chave, sem registro no banco; *D9* = regra "cessão do contrato em `cadastrado`"; *esteira* = task `esteira_baixar` (manda o lote à administradora); *vigente* = lote real aberto que acumula pagamentos.

## 1. Conclusão

1. Há **dois motores de fechamento** convivendo. O **legado** lê as 4 flags e roda em tempo de execução, no beat das 19h e em `POST /liquidacao/`. O **novo** lê só `modalidade_fechamento_lote` e só a tela nova o usa (`POST /liquidacao/fake-batches/close`). **[C]**
2. A modalidade (criada em 27/10) é um "resumo" das flags. Nenhum caminho de execução legado a lê. Só a leem `api/liquidacao/refact.py:689,1003,1723,2343`. **[C]**
3. As flags **não são independentes**: `lote_liquidacao` é a chave-mestra do fechamento em tempo de execução; `fechar_lote_por_proc_id` só tem efeito dentro dela e no backstop das 19h; `acumula_liquidacoes` age antes e por fora; `baixa_por_agendamento` liga a varredura das 19h; `liquidacao_automatico` só decide se o lote criado em tempo de execução vai à esteira. **[C]**
4. Como a derivação modalidade<-flags escolhe uma só e o runtime legado soma flags, **produto pode ter modalidade X e comportamento de X+Y** (seção 6). Caso mais provável: produto criado sem flags explícitas. **[C]** no código, **[H]** em produção.
5. Legado x novo para a mesma chave diferem em fundo (cessão x parcela), agrupamento por remessa (legado mantém o extrato; novo ignora), D9 (novo sempre; legado só nos grupos), trava e assincronia (seção 7).

## 2. As flags e quem as lê

Colunas de `ProdutoConfig` (`database/models.py`).

| Flag | Linha | Quem lê (efeito) |
|---|---|---|
| `lote_liquidacao` (default True) | 1327 | `framework/liquidacao/estados_liquidacao.py:344` (`fechar_lote`): liga o fechamento automático. Nenhum outro leitor. **[C]** |
| `fechar_lote_por_proc_id` (default False) | 1332 | `models.py:5533` (`lote_automatico`: portão Redis x legado); `tasks/liquidacao_lote.py:268` (19h: backstop por proc_id x varredura por chave); `api/liquidacao/repository.py:605` (chave da listagem legada `/lotes/fake`: `proc:` x `origem:`) e `:821` (listagem `/lotes/reais`). **[C]** |
| `acumula_liquidacoes` (default False) | 1430 | `estados_liquidacao.py:350` (insere no vigente); `api/liquidacao/viewer.py:429` (`POST /liquidacao/` fecha vigentes); `tasks/liquidacao_lote.py:254` (19h fecha vigentes). **[C]** |
| `baixa_por_agendamento` (default do modelo True; coluna nullable, sem server_default) | 1493 | só `tasks/liquidacao_lote.py:244`: produto entra na varredura das 19h. **[C]** |
| `liquidacao_automatico` (default False) | 1342 | só `estados_liquidacao.py:336` (`enviar_para_baixa`): manda à esteira os lotes que o `fechar_lote` acabou de criar. Não afeta acumulado, 19h, POST nem tela. **[C]** |
| `modalidade_fechamento_lote` (default `manual`) | 1498 | só o fluxo novo: `refact.py:689` (chave `proc:` x `origem:` da listagem), `:1003` (consulta da linha), `:1723` (valida a chave contra a modalidade), `:2343` (ramo `acumulado`). **[C]** |
| `lote_cessao`, `cessao_automatico` | 1322, 1340 | fechamento de **cessão** (`estados_cessao.py:590`). Fora deste mapa. |

Escrita: `api/produto/closing_modality.py` `apply_closing_modality`, chamada na criação (`api/cadastro/service.py:107`) e no update (`api/produto/sevice.py:43`).
- Com modalidade no payload: grava as 4 flags coerentes (`database/enum.py:842-852` `legacy_flags`) e **não toca em `liquidacao_automatico`**.
- Só com flags: a modalidade é derivada (`enum.py:826-840`; precedência LL+PID > ACU > BAG > LL > manual); as flags ficam como vieram.
- Recusa ACU+PID (`_refuse_accumulation_with_proc_id`).
- `baixa_por_agendamento` está em `cadastro/schema.py:269` e **não** em `produto/schema.py` (grep) **[C]**; se o PUT de produto a aceita é **[H]**: testar em sandbox.

## 3. Gatilhos de fechamento (quem dispara)

### G1. Tempo de execução: pagamento chega em `cadastrado` (legado)
`framework/liquidacao/estados_liquidacao.py:333-358` (`EstadoCadastrado`), nesta ordem **[C]**:
1. `acumula_liquidacao` (`ACU` e não renegociação) -> `RepositoryLiquidacao.insert_pagamento_into_lote` (`repository.py:460`).
2. `fechar_lote` (`LL`) -> `ProcessoLiquidacao.lote_automatico(produto, proc_id)` (`models.py:5530`).
3. `enviar_para_baixa` (`liquidacao_automatico`) -> esteira dos lotes devolvidos em (2).

O estado é comum a liquidação, cancelamento, estorno e recompra. Quem dispara é a esteira Celery, alimentada por `POST /operacao/liquidacao` e `/upload` (`api/operacao/viewer.py:733,801`), consumer RabbitMQ (`consumer/callbacks/liquidacao.py:46`), cancelamento/estorno e `POST /liquidacao/manual` (`viewer.py:898`).

**G1a, acumula (`insert_pagamento_into_lote`)**: chave do vigente = (produto, fundo, originador, origem). Fundo = `contrato.processo.fundo`, o da cessão (`repository.py:463-464`). Origem = `processo.origem_pagamento` = `identificador_extrato` do **1º pagamento** da liquidação (`models.py:5394-5395`); todos os pagamentos da liquidação vão para o mesmo lote. Não confere D9 e não manda à esteira. **[C]**

**G1b, `lote_automatico`** (`models.py:5530-5536`), duas pernas **[C]**:
- `PID` desligada -> `_fechar_lote_legado` (`:5539`): se nenhuma liquidação do proc_id está fora de {cadastrado, rejeitado, errado}, chama `create_by_originador(produto, originador_id)` **sem proc_id**: pega todo pagamento apto do originador, de qualquer remessa. Roda a cada pagamento; a disputa entre workers é resolvida pelo UPDATE com guarda `liquidacao_lote_id is null` (`models.py:6420-6431`).
- `PID` ligada -> `_fechar_lote_por_portao` (`:5559`): exige o total esperado no Redis; fecha quando terminais >= total; um só worker vence `claim_fechamento` (Lua atômico); `_materializar_lotes_por_proc_id` (`:5447`) chama `create_by_originador(..., proc_id)`, um por originador. **Sem registro de controle, não fecha** (log `lote_ctrl_sem_registro`). TTL do registro 24h (`utils/lote_controle.py:10`).
- O total é registrado em `api/operacao/viewer.py:773,844` e `tasks/liquidacao.py:194` (`publicar_pagamentos_liquidacao`: consumer, cancelamento, estorno). **`POST /liquidacao/manual` (`viewer.py:898-945`) não registra**: com PID ligada, remessa por essa rota nunca fecha sozinha.

### G2. Beat 19:00 UTC: `fechar_lote_liquidacao_por_agendamento`
`tasks/liquidacao_lote.py:240-310`; agenda em `schedule/registro.py:49-53` (`crontab(hour=19, minute=0)`). Para cada `ProdutoConfig` com `BAG == True` **[C]**:
1. Se `ACU`: fecha **todos** os vigentes abertos do produto, de qualquer dia e chave (`:254-266`).
2. Se `PID`: para cada proc_id com pagamento sem lote (`models.py:5460` `proc_ids_pendentes`, sem limite de data) chama `backstop_por_proc_id` (`models.py:5601`): status `fechando` re-materializa; `processando` com tudo terminal força; **sem registro (TTL 24h vencido) não fecha**, só alerta.
3. Senão (PID desligada): varre pagamentos sem lote por (originador, `identificador_extrato`, fundo da cessão), sem filtrar D9 nem data (`:272-293`), e chama `create_by_originador` para cada.
4. Todo lote vindo de (1), (2) ou (3) vai à `esteira_baixar` (`:300-309`), **sem olhar `liquidacao_automatico` nem `LL`**.

(2) e (3) são exclusivos: com PID ligada, pagamento de remessa sem registro Redis nunca é varrido por chave.

### G3. `POST /liquidacao/` (varredura do Rafael, 1x/dia; `consolidate` do BFF; `closeLiquidation` do Atlas)
`api/liquidacao/viewer.py:416-443`. Body (`api/liquidacao/schema.py:134-142`): `produto_id` e `originador_id` obrigatórios; `fundo_id` e `origem_pagamento` opcionais. **[C]**
1. Se `ACU`: `ServiceLiquidacao.get_lote_vigente_and_fecha_lote` (`service.py:1165-1185`) fecha vigentes de (produto, originador[, fundo][, origem]).
2. `create_by_originador(prod, originador_id, origem_pagamento, fundo_id)` para pagamentos sem lote.
3. 400 se nada; senão `_enviar_para_esteira` (`service.py:365`) de tudo, **sem olhar `liquidacao_automatico`**. `@max_calls(release_time=600)`.

Não lê `LL`, `PID` nem `BAG`: funciona em qualquer produto, não escopa por proc_id, responde síncrono. Vigente sem pagamentos também conta como lote (a esteira descarta lote sem pagamento, `liquidacao_lote.py:93-100`).

Quem chama **[C]** nos chamadores:
- BFF (`apl-credit-whitelabel-api`, HEAD local 07276dc, branch fix/TS-5377, não master): `POST /fake-batches/consolidate` -> `POST /liquidacao/` (`src/services/platform_cessao/__init__.py:118-122`; `src/modules/operations/liquidation_batches/business.py:335-363`).
- Atlas (`~/repos/atlas/api-zeus`, HEAD aab763dc de 27/11/2024): mutation `closeLiquidation` (`atlas/cessao/resolvers/mut_close_liquidation.py:10-25`) -> fetch-api `post_create_liquidation_batch` (`fetch_api/cessao/cessao.py:225-227`; `~/repos/fetch-api` HEAD 0bbe261 de 29/06/2026), que traduz `fund_id, file_source, originator_id, product_id` em `fundo_id, origem_pagamento, originador_id, produto_id` (`fetch_api/cessao/models/post/liquidacao.py:7-11`). **O Atlas e o fetch-api não têm lógica própria de fechamento**; só chamam esta rota. O fetch-api também só envia `lote_liquidacao`/`liquidacao_automatico` na criação de produto (`fetch_api/cessao/models/post/product.py:116-117`, default False).
- Varredura do Rafael: **[H]** confirmar nos logs da cessão (`"Criar lote de liquidacoes - payload"`, `viewer.py:422`) que é este endpoint e com quais campos.

### G4. Tela nova: `POST /liquidacao/fake-batches/close` (fluxo novo, assíncrono)
Rotas **[C]** em `api/liquidacao/viewer.py`: `POST /fake-batches/close` (996), `POST /fake-batches/close/status` (1018), `GET /fake-batches` (1029, listagem), `DELETE /fake-batches` (exclusão), `GET /fake-batches/payments` (1081). Legadas no ar: `GET /lotes/fake` (1107, chave por flag PID), `GET /lotes/reais` (1146). BFF: `/fake-batches/close` (`platform_cessao/__init__.py:125-128`).

Fluxo (`api/liquidacao/refact.py`):
- `request_fake_batch_closing` (1659): valida a chave contra a modalidade (`_produto_da_linha_do_lote_fake`, 1702: `proc:` só em `automatico_por_remessa`, `origem:` nas outras, senão 400); remessa em andamento (D23) -> 400; **sem pagamento apto (D9) -> 400**; trava Redis por linha (`acquire_fake_batch_closing`, 1330) -> 409; enfileira `close_fake_batch` (`tasks/fake_batch_closing.py:13`); 202.
- `run_fake_batch_closing` (2193) -> `_close_fake_batch` (2321), com heartbeat da trava e limite de tentativas.
- `_close_fake_batch`: modalidade `acumulado` e chave com origem e fundo -> `close_open_accumulating_batches` (1281: UPDATE do vigente `fechado=false`->true com RETURNING, filtra produto+originador[+fundo+origem]); commit; esteira. Depois, **em qualquer modalidade**, cria um lote real e `assign_fake_batch_payments` (972) com os pagamentos aptos da chave; commit; limpa o cache fake; esteira (`_send_real_batches_to_pipeline`, 2483).
- Chave `proc:` -> `_close_remittance_fake_batch` (2390): `assign_proc_id_payments_to_new_batches` (911), um lote por (fundo da parcela, originador), todos no mesmo commit; não há vigente.
- Não lê `LL`, `PID`, `BAG` nem `liquidacao_automatico`: sempre envia à esteira. **[C]**

**Consequência [C] na leitura, [H] na tela:** o pedido exige ao menos um pagamento **sem lote** apto na chave, e a listagem (`listar_lotes_fake`, 629) só traz `liquidacao_lote_id IS NULL`. Vigente acumulado com todos os pagamentos já no lote não aparece como linha fake e o pedido daquela chave devolveria "nada a fechar". Para fechar vigente puro hoje só valem o 19h e o `POST /liquidacao/`. Validar na tela com produto acumulado em sandbox.

### G5. Caminhos que movem ou reenviam lote (não fecham pendentes)
- `POST /liquidacao/liquidar` (`viewer.py:520`, `service.py:274`, `liquidacao_lote.py:30`): envia lote **já existente** à administradora. Destrava o lote criado por `LL` com `liquidacao_automatico` desligado. **[C]**
- `POST /liquidacao/reenviar` (`viewer.py:540`; `liquidacao_lote.py:51`): reexecuta etapas com erro.
- `POST /liquidacao/pagamentos/reenviar` (`viewer.py:947`; `service.py:1131`): cria lote vazio (`repository.py:361`) e move pagamentos por `mover_lote` (`liquidacao_lote.py:70`). Sem flag.
- Retomadas da esteira (`callback/service.py:663`, `consumer/callbacks/liquidacao.py:75,163`, aprovação em tela `service.py:461-489`, `tasks/conciliacao_liquidacao.py:164`): disparam `esteira_baixar` de lote formado.
- Depois da esteira, `_rotear_conciliacao` (`framework/liquidacao/baixar.py:75-120`) decide por par produto+fundo (`automatica`, `manual`, `nao_aplica`) se o lote sai ou espera. Configuração separada, **fora do fechamento**.

## 4. Lote vigente (`LiquidacaoLoteVigente`)

- Tabela em `models.py:6845`. Unicidade `uq_produto_fundo_originador_origem_pagamento` = (produto, fundo, originador, origem_pagamento); `liquidacao_lote_id` único; `fechado` bool. **Uma linha por chave, permanente**: ao fechar, a linha fica; o próximo pagamento (`update_liquidacao_lote_vigente`, `repository.py:385`) põe um lote novo nela e volta `fechado=False`. **[C]**
- Nasce no primeiro pagamento da chave em produto com `ACU` (`get_create_or_update_liquidacao_lote_vigente`, `repository.py:429`; criação trata `IntegrityError`, `:403`).
- **Atravessa dias: sim.** Não há data na tabela nem corte diário; fica aberto até alguém fechar. Quem fecha **[C]**: (a) 19h, todos do produto; (b) `POST /liquidacao/`; (c) tela nova, só com pagamento sem lote na chave. Não há outro caminho (greps de `fechado = True`: `service.py:1183`, `liquidacao_lote.py:263`, `refact.py:1298`).
- Fundo e origem: legado usa fundo da cessão e extrato do 1º pagamento; a tela nova casa por fundo da parcela (`refact.py:1281-1316`). Se divergirem, olham vigentes diferentes. **[H]** consulta: contratos com `processo_estado.fundo_id <> parcela.fundo_id`.

## 5. Como cada gatilho agrupa e o que entra

| Gatilho | Chave do lote | Pagamentos | D9 | Renegociação | Esteira |
|---|---|---|---|---|---|
| G1a acumula | (produto, fundo cessão, originador, extrato do 1º pgto) | todos da liquidação recém `cadastrada` | **não** | pula | não (espera fechamento) |
| G1b PID=0 | (extrato, originador, fundo cessão), **originador inteiro** | sem lote, `create_by_originador` sem proc_id | grupos sim; seleção final não (nota) | entra | só com `liquidacao_automatico` |
| G1b PID=1 | idem, **escopado ao proc_id**, 1 lote por (extrato, originador, fundo) | idem com `proc_id` | idem | entra | só com `liquidacao_automatico` |
| G2 19h | vigentes do produto + (backstop por proc_id OU varredura por chave) | sem lote, qualquer data | grupos sim | entra | sempre |
| G3 POST | vigentes (se `ACU`) + chave pedida | sem lote | grupos sim | entra | sempre |
| G4 `origem:` | (extrato, produto, originador, fundo parcela) | `_eligible_payments_query` (`refact.py:530`) | **sempre** | entra | sempre |
| G4 `proc:` | (fundo parcela, originador); **ignora extrato** | idem, só do proc_id | **sempre** | entra | sempre |

Nota D9 no legado **[C]**: `groups_pagamentos_aptos` (`models.py:6134`) exige liquidação `cadastrado` **e** `ProcessoEstado.estado_atual=='cadastrado'`; a seleção dentro de `create_by_originador` (`models.py:6080-6098`) repete só o filtro da liquidação, não o da cessão. Pagamento da mesma chave com cessão ainda não `cadastrado` pode entrar se houver outro apto na chave. **[H]** validar com teste de 2 pagamentos, ou na réplica: lotes reais com pagamento cujo `processo_estado.estado_atual <> 'cadastrado'`. O acumulado (G1a) também não confere D9. **[C]**

## 6. Tabela final: modalidade -> flags -> comportamento

Flags gravadas pela modalidade (`enum.py:842-852`). LL=`lote_liquidacao`, PID=`fechar_lote_por_proc_id`, ACU=`acumula_liquidacoes`, BAG=`baixa_por_agendamento`.

| Modalidade | LL | PID | ACU | BAG | Tempo de execução (G1) | Beat 19h (G2) | `POST /liquidacao/` (G3) | Tela nova (G4) |
|---|---|---|---|---|---|---|---|---|
| `manual` | 0 | 0 | 0 | 0 | nada fecha | produto fora | fecha pendentes da chave | fecha a chave `origem:` |
| `automatico_por_chave` | 1 | 0 | 0 | 0 | legado por proc_id, abrangendo o originador; esteira só com `liquidacao_automatico` | fora | idem manual | idem manual |
| `automatico_por_remessa` | 1 | 1 | 0 | 0 | portão Redis por proc_id (exige total registrado) | fora (backstop só com BAG) | fecha por chave, ignora proc_id | linha `proc:`: um lote por (fundo, originador) |
| `acumulado` | 0 | 0 | 1 | 0 | insere no vigente; não fecha nem envia | **fora: vigente só fecha às 19h com BAG=1** | fecha vigentes + pendentes | só com pagamento sem lote na chave |
| `agendado` | 0 | 0 | 0 | 1 | nada fecha | varre por chave e envia tudo | idem manual | idem manual |

Atenção ao `acumulado` **[C]**: com BAG=0 (flags coerentes da modalidade) ninguém fecha o vigente sozinho; só o `POST /liquidacao/`. Fechar às 19h exige ACU=1 e BAG=1, que `from_legacy_flags` chama de `acumulado`; mas se uma tela de configuração enviar a modalidade `acumulado`, `legacy_flags()` regrava BAG=0 e desliga o 19h. **[H]** se a config envia a modalidade, e quais produtos acumulados usam ACU+BAG: `SELECT modalidade_fechamento_lote, lote_liquidacao, fechar_lote_por_proc_id, acumula_liquidacoes, baixa_por_agendamento, liquidacao_automatico, count(*) FROM produto_config GROUP BY 1,2,3,4,5,6;`.

### Combinações em que modalidade e flags divergem (o legado obedece às flags) **[C]** no código

| Flags reais | Modalidade derivada | Comportamento legado real |
|---|---|---|
| ACU=1, BAG=1 | `acumulado` | acumula **e** 19h fecha vigentes (e varre pendentes por chave se PID=0) |
| LL=1, BAG=1 | `agendado` | fecha em tempo de execução **e** varre às 19h |
| ACU=1, LL=1 | `acumulado` | acumula e ainda roda `lote_automatico` (pendentes/renegociação); vigente já atribuído não reaparece **[H]** |
| LL=0, PID=1, BAG=1 | `agendado` | nada em tempo de execução; 19h roda **backstop por proc_id**, não a varredura por chave |
| LL=0, PID=1, BAG=0 | `manual` | PID sem efeito |
| LL=1, PID=1, ACU=1 | `automatico_por_remessa` | cadastro recusa ACU+PID; direto no banco, acumula e o portão também roda |
| LL=1, `liquidacao_automatico`=0 | qualquer | lote criado e **parado** (pagamentos já têm lote; 19h e POST só pegam pagamento sem lote) até `POST /liquidacao/liquidar` |
| BAG nulo (linhas antigas) | conta como falso | 19h ignora (`== True`) |
| PID=1, LL=0 | `manual`/`agendado` | listagem legada `/lotes/fake` usa chave `proc:` (flag PID); a nova usa `origem:` (modalidade) |

Produto novo sem flags no payload: o ORM aplica LL=1 e BAG=1 (`models.py:1327,1493`) e `apply_closing_modality` deriva `agendado` com esses mesmos defaults (`_stored_flag`). Resultado: modalidade `agendado`, comportamento LL+BAG. **[C]** no código; **[H]** quantos produtos assim existem (consulta acima).

## 7. Legado x fluxo novo para a mesma chave

| Aspecto | Legado (G1/G2/G3) | Novo (G4) |
|---|---|---|
| Quem lê | 4 flags (+`liquidacao_automatico`) | só a modalidade |
| Fundo | cessão: `ProcessoEstado.fundo_id` (`models.py:6068-6098`; `repository.py:463`) | parcela: `Parcela.fundo_id` (`refact.py:799-812`) |
| Extrato/origem | agrupa por `identificador_extrato` do pagamento; acumulado usa o do **1º** pagamento da liquidação; proc_id mantém o extrato como dimensão | `coalesce(identificador_extrato,'')` por pagamento; `proc:` **ignora** origem, um lote por fundo+originador (`refact.py:863-943`) |
| D9 | só nos grupos | sempre, em toda consulta |
| Trava | UPDATE com guarda `liquidacao_lote_id is null` e rollback em "corrida" (`models.py:6112-6121`); portão Redis por proc_id | trava Redis por linha com heartbeat + UPDATE com guarda + `fechado=false` com RETURNING |
| Síncrono | G1 na task da esteira; G3 responde após criar e enfileirar | 202 + task `close_fake_batch`; status em `/close/status` |
| Esteira | G1 só com `liquidacao_automatico`; G2/G3 sempre | sempre |
| Escopo por remessa | G1 PID=0: não (originador inteiro); PID=1: sim; G3: não | `proc:` sim; `origem:` junta todas as remessas da origem |
| Tempo | `max_calls` 600s no POST | limites de tempo no banco (`refact.py:1319`) |
| Vigente puro | fecha (19h, POST) | não alcança sem pagamento sem lote na chave **[H]** |
| Cache fake | `fechar_liquidacao_lote_fake_cache` (`models.py:6124`) | mesma limpeza depois do commit |

## 8. A confirmar

1. Distribuição real das flags e quantos produtos têm modalidade diferente do que o runtime faz (consulta da seção 6).
2. Se acumulado em produção usa ACU+BAG (19h) ou só o POST do Rafael.
3. Se há lotes legados com pagamento de cessão não `cadastrado` (nota D9).
4. Se a tela nova lista/fecha vigente acumulado (sandbox).
5. Quantos proc_ids ficam pendentes sem registro Redis: logs `event=backstop_sem_registro` e `lote_ctrl_sem_registro` no Datadog.
6. Qual rota do BFF a tela usa em produção (`/fake-batches/consolidate` -> POST legado, ou `/fake-batches/close`): ler o front; só li o BFF local, que não é master.
7. Fuso do beat: assumi 19:00 UTC como informado; conferir `timezone` do Celery.
