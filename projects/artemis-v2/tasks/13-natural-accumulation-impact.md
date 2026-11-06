# D1. Acúmulo como comportamento natural: impacto na platform-cessao

Base: `579ad13e3` (produção), lido por SHA. O `git fetch` moveu `origin/master` para `6c152445d` (release/20261005); o diff de `enum.py` e `models.py` é de imóveis/orquestrador, sem relação com liquidação. Marcas: **[C]** visto no código; **[H]** hipótese, com como validar. Paths relativos a `cessao/`.

Termos: **vigente** = linha de `liquidacao_lote_vigente` que aponta para um lote real aberto da chave (produto, fundo, originador, origem). **D9** = só entra em lote pagamento com liquidação `cadastrado` e cessão do contrato `cadastrado`. **Esteira** = fila Celery que baixa o lote na administradora. **Beat** = agendador Celery (19h). **Janela** = filtro de datas da listagem.

## 1. Conclusão

1. **Viável, e o impacto no caminho do pagamento é pequeno.** `acumulado` é a única modalidade em que o pagamento ganha lote ao chegar; nos outros quatro ele já chega sem lote **[C]** (`framework/liquidacao/estados_liquidacao.py:349-351` é o único ponto que atribui lote na chegada). A proposta é remover essa exceção.
2. **Cancelamento, estorno, recompra, reenviar, `contrato_transacao`, conciliação, callbacks: ficam iguais** (seção 3). Renegociação nunca esteve em lote.
3. **O que muda de verdade, em ordem de risco:** (a) a transição, porque os três fechadores de vigente só olham o vigente se a flag/modalidade `acumulado` ainda estiver ligada; (b) a D9, que passa a valer para quem hoje não a confere; (c) a listagem da tela nova usa janela de data e o fechamento não, o que importa quando o pagamento espera dias; (d) o "horário agendado" do fechamento novo **não existe**: o beat é o legado.
4. O que o vigente dá hoje é quase só aparência (lote visível o dia todo, `data_criacao` antiga). Regra de negócio perdida: nenhuma encontrada. Ganhos: some a corrida de chegada × fechamento e a tela nova passa a poder excluir pagamento acumulado.

## 2. Leitores e escritores

### `LiquidacaoLoteVigente` / `liquidacao_lote_vigente`

| Onde | O que faz | Na proposta |
|---|---|---|
| `framework/liquidacao/estados_liquidacao.py:349-351` | na chegada em `cadastrado` (liquidação, cancelamento, estorno), se ACU e não renegociação, chama `insert_pagamento_into_lote` | **removido** (é a mudança) |
| `api/liquidacao/repository.py:460-474` `insert_pagamento_into_lote` | acha/cria o vigente e atribui `pagamento.liquidacao_lote` a cada pagamento do processo (só em memória, commit depois) | removido |
| `repository.py:429-457` `get_create_or_update_...` | lê sem trava; se `fechado`, chama update; se não existe, cria | removido |
| `repository.py:403-426` `create_...` | INSERT de lote `pendente` + vigente; trata `IntegrityError` | removido |
| `repository.py:385-398` `update_...` | com `FOR UPDATE`, reabre: novo lote, `fechado=False`; tem `finally: db.session.rollback()` | removido |
| `repository.py:371-382` get por chave | leitura | removido |
| `repository.py:477-495` `get_lote_liquidacao_from_liquidacao_lote_vigente` | lotes de vigente `fechado=False` por produto+originador[+fundo+origem] | só na transição (drenar) |
| `api/liquidacao/service.py:1165-1185` | fecha (`fechado=True`) os vigentes achados acima | só na transição |
| `api/liquidacao/viewer.py:429-438` `POST /liquidacao/` | só `if produto_config.acumula_liquidacoes` chama o item acima, e junta ao resultado | gate precisa sair antes de desligar a flag (seção 5) |
| `tasks/liquidacao_lote.py:254-266` beat 19h | fecha todos os vigentes abertos do produto, **só se BAG=1 e ACU=1** (laço por `baixa_por_agendamento == True`, :243-246) | idem |
| `api/liquidacao/refact.py:1281-1316` `close_open_accumulating_batches` | UPDATE `fechado` falso para verdadeiro com RETURNING, filtra produto+originador[+fundo+origem] | só na transição |
| `refact.py:2340-2366` em `_close_fake_batch` | só se `modalidade_fechamento_lote == acumulado` **e** chave com origem e fundo, fecha o vigente antes de montar o lote novo | idem; sem esse gate, vigente aberto fica órfão |
| `database/models.py:6845` (modelo), `:800,:1119,:1720,:5932` | relationships `back_populates`, sem consulta | ficam como legado |
| `migrations/versions/2022-01-07T18:43:43_88d4c53321ed_.py` | cria a tabela (única migration; não mexer) | tabela fica; apagar depois, em migration nova |
| `test/api/liquidacao/test_repository_liquidacao.py:385-777`, `test_refact_liquidacao.py:1695-1703`, `test_service_liquidacao.py:732-753`, `test_viewer_liquidacao.py:697-816` | testes do vigente | saem junto com o código |

FK: `liquidacao_lote_vigente.liquidacao_lote_id` tem `ondelete=CASCADE` (`models.py:6859`); `liquidacao_pagamento.liquidacao_lote_id` tem `SET NULL` (`models.py:6359`). Outros repos (BFF, data-lake, shared, docs, atlas, fetch-api): nenhum uso do nome da tabela **[C]** (grep local).

### `acumula_liquidacoes`

Coluna `models.py:1430`; campos de API `api/cadastro/schema.py:256`, `api/produto/schema.py:84` (escrita); `api/produto/closing_modality.py:59-61` (recusa ACU+PID) e `:21-37` (deriva modalidade); `database/enum.py:803-852` (`acumulado` grava ACU=1, BAG=0); leitores de comportamento: `estados_liquidacao.py:350`, `viewer.py:429`, `tasks/liquidacao_lote.py:254`. Na tela nova o gate é a **modalidade**, não a flag (`refact.py:2343`).

### "Lote aberto" (lote real com `data_envio_liquidacao` nula ou `pendente`)

Ninguém lê isso como predicado **[C]**; "aberto" só existe como `vigente.fechado=False`. Lote de vigente nasce `pendente` sem `data_envio` (`repository.py:393,408`); os fechamentos reais gravam `data_envio=now()` na criação (`refact.py:928,2364`; `models.py:6107`); o vigente só ganha `data_envio` quando o emissor envia (`emissores/liquidacao.py:123`). `create_lote_pagamentos` (`repository.py:361-368`, usado no reenviar) também cria `pendente` sem `data_envio`: falso positivo se alguém usar esse predicado na migração.

## 3. Fluxos que supõem lote na chegada (ou tratam diferente)

| Fluxo | Hoje | Na proposta |
|---|---|---|
| **Cancelamento e estorno** | passam pelo mesmo `EstadoCadastrado` e entram no vigente. O conciliador de estorno procura o pagamento anterior por processo `cadastrado`, valor e pmt, **sem filtrar lote** (`conciliacao/conciliador_estorno.py:15-32`) | **igual** |
| **`DELETE /liquidacao/pagamentos`** (legado) | lote `pendente` pode apagar; sem lote também (`api/liquidacao/validator.py:47-71,108-136`). Vigente aberto é `pendente`, então apaga | **igual** (o campo `lote` da resposta vira `None`) |
| **Exclusão da tela nova** | só apaga liquidação **sem lote**; pagamento com lote é pulado, motivo `COM_LOTE` (`refact.py:2166`). Hoje não alcança pagamento acumulado | **passa a alcançar**: ganho |
| **Renegociação** (`is_renegociacao` pula o vigente) | **não vai para lugar nenhum**: gera `PagamentoRenegociacao`, não `LiquidacaoPagamento` (`dataclass.py:194-204`); o commit `8484dbd79` (VEGA-2352) diz que renegociação não tem `liquidacao_pagamento` e que só as liquidações do contrato original vão ao lote. O pulo existe porque o vigente falhava ao achar contrato **[C]** | **igual**. O `_pular_lote_de_renegociacao` do callback (`callbacks/baixa_convoy.py:59-65`) olha proc_ids do lote, pós-baixa, não muda |
| **Recompra/aditamento** | a liquidação nasce no fluxo de cessão com `processo.to_cadastrado()` direto, com log "não passa pelo fechamento automático de lote" (`framework/regras/cessao/aditamento_recompra.py:132-153`). **Já fica sem lote** hoje, em produto acumulado também | **igual**; só `POST`, beat ou tela fecham |
| **`POST /liquidacao/pagamentos/reenviar`** | cria lote vazio e `mover_lote` move os pagamentos (`api/liquidacao/service.py:1131-1150`; `tasks/liquidacao_lote.py:70-77`); não olha vigente | **igual** |
| **`contrato_transacao`** | só insere se **toda** parcela tem pagamento em lote `concluido` e `liquidacao_lote_id` não nulo (`tasks/liquidacao_lote.py:197-216`). Pagamento em vigente `pendente` e pagamento sem lote bloqueiam do mesmo jeito | **igual** |
| **Conciliação e saldo** | a prioridade é `(tem_baixa_parcial, lote.data_criacao, id)` por lote (`tasks/conciliacao_liquidacao.py:61-68`); a fila é `estado_atual='aguarda_conciliacao'` (`repository.py:175-191`); o lote entra nela ao sair de `pendente` na esteira, e o corte (`passou_do_corte`, `shared/saldo_liquidacao/corte.py:81`) é avaliado nesse momento (`framework/liquidacao/baixar.py:53-120`), não na criação | **igual na regra**. O desempate por `data_criacao` muda de "1º pagamento da chave" para "fechamento": só ordem entre lotes sem parcial |
| **Callbacks ao parceiro** | `liquidacao_concluida` sai por pagamento em `EstadoCallback` antes de `EstadoCadastrado` (`estados_liquidacao.py:~455-480`); o da baixa do lote sai pós-baixa (`baixa_convoy.py`, `batch_id`) | **igual** |
| **`GET /liquidacao/lotes/reais`** | filtra `LiquidacaoLoteProcesso.data_criacao` (`repository.py:689`); sem filtro de vigente, então o **lote aberto aparece como lote real `pendente`** com soma viva, e com a data do 1º pagamento | o lote real só aparece no fechamento, com data do fechamento; o aberto vira linha fake |
| **`GET /liquidacao/lotes/fake` e `GET /liquidacao/`** | fake de **hoje** vem do Redis (`api/v2/liquidacao/service.py:109-115`), de outros dias, do banco por `ProcessoLiquidacao.data_criacao` (`:117-143`); chave do Redis é por dia (`:55-61`) com TTL de 1 dia (`database/listeners.py:~130`) | pagamento que espera 2+ dias **some do cache** e só aparece consultando o dia de chegada. A lista legada é de um dia; pagamento acumulado fica invisível se ninguém consultar a data certa |
| **`GET /liquidacao/fake-batches`** (nova) | janela por data do processo (`refact.py:570-585,629-700`); `qtd_aptos` conta D9 (`:700-720`); o **fechamento não tem janela** (`:787-797,1003-1030`) | `qtd_registros` e `valor_pago` da linha refletem só a janela, enquanto o fechamento leva tudo da chave: com espera de dias a tela subestima. Precisa janela larga ou "tudo sem lote" |
| **Cache fake e listeners** | `after_insert` soma no cache de hoje para todo produto (`listeners.py:110-155`); não há `after_update`, então a atribuição ao vigente **não subtrai** **[C]** na leitura; `fechar_liquidacao_lote_fake_cache` (`:203-222`) limpa só a chave de hoje | **[H]** hoje o cache superconta produto acumulado (pagamento já em lote conta como fake); na proposta fica correto. Validar: para um produto acumulado, comparar `GET /lotes/fake` de hoje (cache) com o de ontem (banco) |
| **`esteira_baixar`** | descarta lote sem pagamento (`tasks/liquidacao_lote.py:82-105`) | igual (vigente vazio some junto) |

## 4. O que o vigente dá hoje e "sem lote" não daria

| Item | Natureza | Observação |
|---|---|---|
| Valor do lote visível durante o dia (lista de lotes reais) | **aparência** | na proposta a mesma informação está na linha fake, com a ressalva da janela. **[H]** a tela de operações pode depender de ver o lote `pendente`: perguntar |
| `data_criacao` do lote = 1º pagamento | **aparência**, com 3 leitores: filtro de `/lotes/reais` (`:689`), desempate da conciliação, e `_validate_by_data_and_fundo` (`validator.py:108-125`: lote criado antes de hoje em fundo Capitalis/BGT exige estado permitido; `pendente` passa) | com data do fechamento, o lote sempre é "de hoje": a restrição de exclusão de lote velho deixa de pegar |
| Um lote por chave que atravessa dias | **aparência/identidade**: o `identificador` do lote (num_termo, nome de arquivo, `batch_id`) só é usado pós-envio | igual: a chave do fechamento novo também junta todos os dias |
| Renegociação separada | **não existe** (ver seção 3) | |
| Ordem de chegada | nada garante hoje; o `id` do pagamento dá a ordem nos dois | |
| Desempenho do fechamento | **custo real, a favor do vigente** | vigente: UPDATE de 1 linha por chave. Proposta: 1 UPDATE...FROM por chave sobre todos os pagamentos da espera, com `statement_timeout` 480 s (`refact.py:91-92`) e task `soft_time_limit=540` (`tasks/fake_batch_closing.py:11`). O filtro `liquidacao_lote_id IS NULL` usa o btree comum de `liquidacao_pagamento.liquidacao_lote_id` (`models.py:6359`). **[H]** volume: medir pagamentos por chave por dia nos 13 produtos (consulta na seção 5) |
| Custo na chegada | **ganho da proposta** | some o SELECT do vigente por processo, a trava de linha quente por chave e o `rollback()` da sessão em `update_liquidacao_lote_vigente` (`repository.py:385-398`) |
| Corrida chegada × fechamento | **ganho da proposta** | hoje: o estado `cadastrado` é gravado com commit antes de `EstadoCadastrado.aplica_transicao_estado` atribuir o vigente (`estados_liquidacao.py:68-88,90-130`), e `get_create_or_update` lê o vigente sem trava (`repository.py:429-457`). **[H]** um fechador pode levar o pagamento ou um pagamento entrar em lote já enviado. Validar: lotes de vigente com pagamento cuja `data_atualizacao` é posterior à 1ª mudança de estado do lote em `liquidacao_lote_log` |

## 5. Os outros modos

- **`manual` já é "esperar sem lote"** **[C]**: LL=0, PID=0, ACU=0, BAG=0; `EstadoCadastrado` não atribui nem fecha nada (`estados_liquidacao.py:333-358`); fecha por `POST /liquidacao/` ou tela nova.
- **`agendado` já é "esperar sem lote e fechar no horário"** **[C]**: o beat varre pagamentos sem lote por (originador, extrato, fundo da cessão) e chama `create_by_originador` (`tasks/liquidacao_lote.py:272-293`), manda sempre à esteira (`:300-309`).
- **`automatico_por_chave` e `automatico_por_remessa` não esperam**: o fechamento roda por pagamento (`lote_automatico`) ou pelo portão Redis por proc_id. Já chegam sem lote e ganham lote no fechamento automático. **Não mudam**.
- Então `acumulado` passa a ser equivalente a `manual` (BAG=0) ou `agendado` (BAG=1). A ressalva de comportamento: `acumulado` hoje agrupa **por processo** (o extrato do 1º pagamento vale para todos, `models.py:5394-5395`), enquanto o fechamento agrupa **por pagamento** (`identificador_extrato`, `refact.py:799-810`). **[H]** só difere se uma liquidação tiver extratos distintos entre pagamentos; consulta: `SELECT liquidacao_processo_uuid FROM liquidacao_pagamento GROUP BY 1 HAVING count(DISTINCT origem_pagamento) > 1` restrita aos produtos acumulados.
- Fundo: vigente usa o da cessão (`contrato.processo.fundo`, `repository.py:463-464`), o fechamento novo usa o da parcela (`refact.py:799-812`). Mesma ressalva do mapa (seção 4): **[H]** `processo_estado.fundo_id <> parcela.fundo_id`.
- O beat **não usa o fechamento novo**: ele chama `create_by_originador`, que confere D9 só no agrupamento, não na seleção final (`models.py:6080-6098` vs `groups_pagamentos_aptos` `:6134`). Para "horário agendado" com D9 estrita é preciso religar o beat ao `_close_fake_batch` (ou fechar o furo do legado).

## 6. Transição

**Armadilha [C]:** os três fechadores de vigente dependem de ACU/modalidade `acumulado` (`viewer.py:429`, `tasks/liquidacao_lote.py:254` com BAG, `refact.py:2343`). Se a flag for desligada **antes** de drenar, o vigente aberto fica órfão: o lote tem pagamentos, então o fechamento novo (que só pega `liquidacao_lote_id IS NULL`) também não o vê.

Ordem proposta:

1. **Medir** (réplica, somente leitura):
   ```sql
   SELECT v.produto_id, v.fundo_id, v.originador_id, v.origem_pagamento, l.id AS lote, l.estado_atual, l.data_criacao,
          count(p.id) AS pagamentos,
          count(*) FILTER (WHERE pe.estado_atual <> 'cadastrado') AS cessao_fora_d9,
          count(*) FILTER (WHERE lp.estado_atual <> 'cadastrado') AS liquidacao_fora
   FROM liquidacao_lote_vigente v
   JOIN liquidacao_lote_processo l ON l.id = v.liquidacao_lote_id
   LEFT JOIN liquidacao_pagamento p ON p.liquidacao_lote_id = l.id
   LEFT JOIN liquidacao_processo lp ON lp.uuid = p.liquidacao_processo_uuid
   LEFT JOIN contrato_parcela cp ON cp.id = p.parcela_id
   LEFT JOIN contrato c ON c.id = cp.contrato_id
   LEFT JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
   WHERE v.fechado = false GROUP BY 1,2,3,4,5,6,7;
   ```
   E a distribuição de flags (consulta do mapa, seção 6) para saber quais dos 13 têm ACU+BAG.
2. **Deploy 1 (código):** `EstadoCadastrado` deixa de chamar `insert_pagamento_into_lote` e, no mesmo deploy, os fechadores de vigente deixam de depender da flag (fecham vigente aberto se existir). Pagamento novo passa a chegar sem lote em todos os produtos, mesmo com ACU ainda ligada.
3. **Drenar:** fechar todos os vigentes abertos uma última vez, por chave (`POST /liquidacao/` com a chave, ou o beat, ou a tela). O fechamento de vigente já manda à esteira e já ignora D9 (leva o lote inteiro, `refact.py:2340-2366`). Conferir `count(*)` de vigentes `fechado=false` igual a zero e que nenhum vigente reabriu.
4. **Configuração:** trocar modalidade/flags do produto (`acumulado` para `manual` ou `agendado`) só depois do zero. Se o produto fechava às 19h (ACU+BAG), vira `agendado` (BAG=1); se só o `POST` do Rafael fechava, vira `manual`. Atenção: salvar a modalidade `acumulado` regrava BAG=0 (`enum.py:842-852`), então produto que hoje depende do 19h pode já estar sem ele **[H]**.
5. **Religar o agendado** ao fechamento novo (se for o caminho), antes de contar com ele.
6. **Depois:** a tabela vira legado; apagar código e tabela em migration nova.

**Pagamentos no vigente que não passariam na D9** (cessão ou liquidação fora de `cadastrado`). Opções, em ordem de preferência: (a) a medição do passo 1 mostra se existem; se zero, não há decisão; (b) se existirem e o lote ainda é `pendente` (não enviado), desvincular antes da drenagem (`UPDATE liquidacao_pagamento SET liquidacao_lote_id = NULL ... WHERE ...`), e eles passam a esperar a D9; (c) fechar com o lote inteiro, como hoje, e registrar a exceção. Não há caminho que corrija sozinho: o fechamento de vigente não confere D9.

## 7. Riscos e perguntas ao Pietro

Riscos
- **R1.** Desligar ACU antes de drenar deixa lote órfão (seção 6).
- **R2.** Pagamento que espera cessão que **nunca** chega a `cadastrado` fica para sempre sem lote. Hoje iria ao ADM mesmo assim. Precisa de alerta de "sem lote há mais de N dias".
- **R3.** Tela nova com janela de data: linha de espera antiga subestimada ou invisível; legado `/lotes/fake` de hoje só vê o cache do dia.
- **R4.** Volume do UPDATE de fechamento com vários dias acumulados (limites de 480/540 s).
- **R5.** Beat legado não usa o fechamento novo: "horário agendado" com D9 exige mexer nele.
- **R6.** Quem consome o lote `pendente` vivo (tela de operações, Atlas, BFF, Rafael) pode contar com ele. Fora do escopo desta leitura (D2 cobre consumidores externos).

Perguntas
1. Quais dos 13 produtos fecham hoje às 19h (ACU+BAG) e quais só pelo `POST` do Rafael? (consulta de flags do mapa, seção 6)
2. A tela de operações usa o lote `pendente` aberto para algo (conferir valor do dia, liquidar manualmente)? Hoje `POST /liquidacao/liquidar` aceita um lote vigente aberto sem guarda (`validator.py:39-45` só confere existência), então o lote pode seguir e continuar recebendo pagamento.
3. Pagamento fora da D9 dentro de vigente: fechar mesmo assim, ou segurar (seção 6)?
4. O fechamento agendado vai usar o fechamento novo (D9 estrita, sempre esteira) ou manter o beat legado?
5. A tela passa a listar "tudo sem lote" (sem janela) para produtos de espera?
