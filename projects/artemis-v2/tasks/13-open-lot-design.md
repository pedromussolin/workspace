# Lote aberto como padrão: proposta de desenho (D34, replanejamento da TS-5567)

Rascunho de 10/11/2026, para aprovação do Pietro antes de reescrever qualquer plano. Linhas de
código valem para `platform-cessao` `origin/master` **c041122eb**; a TS-5582 é citada pela branch
remota `feature/TS-5582-lotes-vazios-liquidacao`. **[C]** = visto no código, na réplica ou no
Datadog (com a fonte); **[H]** = hipótese, com o caminho para validar. Caminhos relativos a `cessao/`.

## 0. Conclusão

1. **Dá para manter o lote aberto e torná-lo padrão, com uma migration pequena só para a remessa.**
   A tabela `liquidacao_lote_vigente` já tem o que precisa para as chaves de origem: chave única por
   produto, fundo, originador e origem (`database/models.py:6984-7021`), e a origem aceita a
   sentinela `*` da chave sem origem. A D36 (10/11) leva o lote aberto também à remessa: o vigente
   ganha a coluna `proc_id` (migration nova, nada existente é alterado; seção 3.3).
2. **A premissa "a trava por chave já existe hoje" não se confirma [C].** A chegada comum lê o
   vigente sem trava (`api/liquidacao/repository.py:444-446`); só a reabertura usa `FOR UPDATE`
   (`:389-390`). O produto 80 funciona hoje porque nada serializa as chegadas. O desenho novo
   serializa, por chave, um passo curto (um comando e o commit); a folga contra o pico do 80
   precisa ser medida (consulta 1).
3. **Uma regra fecha B14, B25, o lote vazio e a D9:** o pagamento só entra no lote aberto da chave
   com a linha do vigente travada, o lote em `pendente`, a D9 conferida e o `UPDATE` guardado
   (`liquidacao_lote_id IS NULL`); o lote nasce na mesma transação do primeiro pagamento; e todo
   caminho que envia lote à administradora fecha antes o vigente que aponta para ele.
4. **Fechar fica barato em qualquer tamanho:** marca o vigente `fechado` e junta no mesmo lote só
   os pagamentos que ficaram sem lote (D9 tardia, falha na entrada, recompra). O custo do `UPDATE`
   passa a ser o desses avulsos, não o do lote.
5. **O lote aberto vale em qualquer caso (D36, 10/11):** todo gatilho (manual, agendado, automático)
   e todo agrupamento (`por_chave`, `por_chave_sem_origem`, `por_remessa`), sem configuração por
   produto. A remessa ganha lote aberto pela chave `proc:<proc_id>`; o automático entra junto, e o
   fim da remessa (TS-5572) fecha o lote aberto pelo núcleo.
6. **Recomendo duas fases:** primeiro as guardas nos 13 produtos que já acumulam (destrava a
   TS-5570 sem drenagem e sem fechar em blocos), depois todos os produtos, com a exclusão na tela.

## 1. Termos

| Termo | O que é |
|---|---|
| Lote aberto (vigente) | linha de `liquidacao_lote_vigente` com `fechado = false`, que aponta para um lote real `pendente` que ainda recebe pagamentos |
| Avulso | pagamento `cadastrado` sem lote (`liquidacao_lote_id` nulo) de uma chave que usa lote aberto |
| Chave | identidade da linha da tela: `origem:<origem>:<produto>:<originador>:<fundo>`, `origem:*:...` (sem origem, TS-5583 D1) ou `proc:<proc_id>` |
| D9 | só entra em lote pagamento com liquidação `cadastrado`, cessão do contrato `cadastrado` e processo não apagado (`_eligible_payments_query`, `api/liquidacao/refact.py:530-548`) |
| Trava de linha | `SELECT ... FOR UPDATE`: segura a linha até o commit; quem pede a mesma linha espera |
| `lock_timeout` | tempo máximo que um comando espera por uma trava antes de falhar |
| Esteira de baixa | task `esteira_baixar` (`tasks/liquidacao_lote.py:81-104`), que gera e envia o arquivo à administradora |
| Savepoint | ponto dentro da transação para desfazer só um trecho |

## 2. Como funciona hoje [C]

### 2.1 Chegada

- A esteira de liquidação roda **um processo por task**: cada pagamento do upload vira
  `persistir_payload_liquidacao | esteira_liquidacao` (`api/operacao/viewer.py:780-786`;
  `tasks/liquidacao.py:44-79`).
- `EstadoSalvo` grava `cadastrado` **com commit** (`framework/liquidacao/estados_liquidacao.py:319-329`,
  via `_chama_estado` `:82-83`). Depois, `EstadoCadastrado` (`:332-358`) chama
  `acumula_liquidacao` (`:349-351`) só com `acumula_liquidacoes` e fora de renegociação.
- `insert_pagamento_into_lote` (`api/liquidacao/repository.py:459-475`) monta a chave com o **fundo
  da cessão** (`contrato.processo.fundo`, `:464`) e a **origem do 1º pagamento do processo**
  (`:465`; `database/models.py:5533-5534`), acha ou cria o vigente e põe o lote em cada pagamento
  **em memória** (`:471-472`). O vínculo só é gravado no commit do fim da esteira
  (`framework/base.py:33`).
- Uma exceção nesse trecho leva a liquidação a `errado` (`estados_liquidacao.py:30-34`, `:184-189`).

### 2.2 Criação e reabertura

- **Criação** (`repository.py:402-426`): lote `pendente` + vigente num savepoint; a unicidade
  (`models.py:6989-6995`) resolve duas chegadas simultâneas (`IntegrityError` → relê, `:421-424`).
- **Reabertura** (`repository.py:384-400`): com `FOR UPDATE`, troca o lote do vigente por um novo e
  **commita** (`:393-397`) antes de o pagamento ser vinculado; `rollback` no `finally` (`:400`).
- O vigente exige origem e fundo (`models.py:7010-7018`, `NOT NULL`).

### 2.3 Quem fecha e quem envia

| Caminho | Fecha o vigente? | Como | Avulsos |
|---|---|---|---|
| Tela, fluxo novo (`_close_fake_batch`, `refact.py:2321-2388`) | só com modalidade `acumulado` e chave com origem e fundo (`:2342-2347`) | `UPDATE ... fechado = false → true RETURNING` (`close_open_accumulating_batches`, `:1281-1316`), commit e esteira | lote **novo** com D9 (`:2363-2380`) |
| `POST /liquidacao/` (`api/liquidacao/viewer.py:418-447`) | só com `acumula_liquidacoes` (`:429`) | SELECT sem trava e `save()` (`api/liquidacao/service.py:1165-1185`) | `create_by_originador` (`models.py:6207`), sem a cessão na seleção final |
| Beat das 19h UTC (`tasks/liquidacao_lote.py:239-310`) | só com `baixa_por_agendamento` (`:243-246`) **e** `acumula_liquidacoes` (`:254`) | SELECT sem trava e `save()` por vigente (`:255-266`) | `create_by_originador` |
| `POST /liquidacao/liquidar` → `liquidar_task` (`tasks/liquidacao_lote.py:29-47`) | **não** | envia o arquivo pelo emissor (`:37-38`) e manda à esteira; a rota só confere se o lote existe (`api/liquidacao/validator.py:39-41`) | — |
| `reenviar` (`tasks/liquidacao_lote.py:50-66`) e `esteira_baixar` (`:81-104`) | **não** | põem o lote na esteira sem olhar vigente | — |

### 2.4 Onde estão as corridas

- **B14:** entre o commit de `cadastrado` e o vínculo, o pagamento é um avulso; o fechamento novo
  pode levá-lo, e o vínculo seguinte (UPDATE por id, sem `IS NULL`) o tira do lote fechado.
- **B15/B25, corrida:** a chegada lê `fechado = false` sem trava; o fechador marca `fechado` e
  envia; a chegada grava depois. Os 59 pagamentos 6 s depois do envio (B25) são esse caso.
- **B25, estado:** `/liquidar` e `reenviar` enviam sem fechar o vigente, e a chegada reaproveita o
  vigente enquanto `fechado = false`, sem olhar o estado do lote (`repository.py:447-452`).
  Réplica, 06/11: 10.562 pagamentos em 14 lotes já concluídos (`bugs-found.md`, B25).
- **Lote vazio:** a reabertura commita o lote antes do pagamento; se a esteira falha depois, ou o
  pagamento é apagado ou movido, o lote aberto fica vazio. Fechado assim, a esteira de hoje só o
  pula (`tasks/liquidacao_lote.py:91-97`) e ele fica `pendente` para sempre. **[H]** qual dessas
  causas gerou os 27.399 vigentes vazios do 1109 (retrato de 08/11, `13-plan-ts-5567.md`); não muda
  o desenho.
- **D9:** a chegada não confere a cessão (B12).
- **Chave divergente:** o vigente usa fundo da cessão e origem do processo; a tela e o fechamento
  novo usam **fundo da parcela** e **origem do pagamento** (`refact.py:687-694`, `:799-812`). Se
  divergem, o fechamento pela tela não acha o vigente (`refact.py:1300-1308`). **[H]** frequência:
  consulta 3.

## 3. Desenho novo

### 3.1 Regras (invariantes)

1. **Um lote aberto por chave**, e ele só recebe pagamento sob a trava da linha do vigente.
2. **O lote aberto nasce com o primeiro pagamento**, na mesma transação: nunca é commitado vazio.
3. **Pagamento entra uma vez e não muda de lote:** todo vínculo é `UPDATE ... WHERE
   liquidacao_lote_id IS NULL` com a D9 do `_eligible_payments_query` (fonte única da regra).
4. **Lote só sai para a administradora fechado:** todo caminho que envia fecha antes o vigente que
   aponta para o lote, pelo mesmo `UPDATE` guardado (que espera a chegada em andamento).
5. **O lote aberto é atalho, não verdade:** quem falha em entrar fica avulso, e todo fechamento varre
   os avulsos da chave. Por isso a entrada nunca leva a liquidação a `errado`.
6. **Ordem das travas:** sempre a linha do vigente antes das linhas de pagamento (sem deadlock).

### 3.2 Chegada, passo a passo

Código novo em `refact.py` (`RefactLiquidacaoService.entrar_no_lote_aberto_da_liquidacao`,
repositório no `RefactLiquidacaoRepository`), chamado por `EstadoCadastrado` no lugar de
`acumula_liquidacao`. As funções de chegada de `repository.py:370-475` saem.

1. **Quem não entra:** renegociação (como hoje); pagamento com parcela sem fundo (o vigente exige
   fundo, `models.py:7010-7012`); em `por_remessa`, pagamento de processo sem `proc_id`. Esses
   ficam avulsos. Nenhum agrupamento nem gatilho fica de fora (D36).
2. **Chave por pagamento:** produto, originador do contrato, **fundo da parcela** e origem do
   pagamento (`''` quando nula, como a tela faz com `coalesce`); `*` no lugar da origem em
   `por_chave_sem_origem`; em `por_remessa`, o `proc_id` do processo no lugar da origem (3.3). Uma consulta pequena pelos pagamentos do processo. Várias chaves no
   mesmo processo: tratar em ordem fixa.
3. **Transação curta, só para isso** (a sessão chega limpa: `cadastrado` já foi commitado):
   `SET LOCAL lock_timeout` curto (ex.: 2 s).
   - **Caminho comum, um comando:** CTE (consulta nomeada dentro do mesmo comando) que trava o
     vigente com `FOR UPDATE` exigindo `fechado = false` e lote `pendente`, e o `UPDATE` guardado
     com a D9 dos pagamentos do processo para esse lote; em seguida o `COMMIT`. A trava dura um
     comando e um commit.
   - **Sem lote utilizável** (vigente inexistente, fechado, ou lote fora de `pendente`): num
     savepoint, cria o lote `pendente`; aponta o vigente para ele (`UPDATE ... fechado = false`)
     ou insere o vigente (`ON CONFLICT DO NOTHING`; se outra chegada criou antes, desfaz o
     savepoint e volta ao caminho comum); faz o `UPDATE` guardado. **Zero linhas** (D9 falhou ou um
     fechamento levou o pagamento antes, B14) → desfaz o savepoint: nenhum lote vazio.
4. **Falha** (trava ocupada além do `lock_timeout`, erro de banco): `rollback`, evento WARNING
   "Pagamento de liquidação ficou sem lote aberto" com produto, chave e motivo; a esteira segue e a
   liquidação termina `cadastrado` (avulso).
5. **B25 resolvido na chegada:** vigente `fechado = false` com lote já fora de `pendente` (os
   `concluido` de hoje) é tratado como fechado e ganha lote novo. Não uso `data_envio_liquidacao`
   como guarda: quem grava esse campo fora do envio não está mapeado (rota `PATCH /liquidacao/`,
   `viewer.py:458-477`) **[H]**.

### 3.3 Chave do lote aberto por agrupamento

| Agrupamento | Lote aberto | Chave da linha |
|---|---|---|
| `por_chave` | um por (produto, originador, fundo, origem) | `origem:<origem>:<p>:<o>:<f>` |
| `por_chave_sem_origem` | um por (produto, originador, fundo), origem gravada `*` | `origem:*:<p>:<o>:<f>` |
| `por_remessa` (D36) | um por (produto, remessa, originador, fundo da parcela) | `proc:<proc_id>` (uma linha para a remessa inteira) |

- **Como o vigente guarda a remessa (D36, substitui a decisão 3):** migration nova, só `add_column`
  e índice, sem tocar nas existentes: coluna `proc_id` (UUID, nula) em `liquidacao_lote_vigente`,
  índice parcial `ix_liquidacao_lote_vigente_proc_id` `WHERE proc_id IS NOT NULL`, usado para achar
  os vigentes abertos da remessa. A restrição única existente (produto, fundo, originador,
  `origem_pagamento`) **fica como está**: na remessa, `origem_pagamento` recebe o texto
  `proc:<proc_id>` (cabe em `String(100)`, e a origem é `NOT NULL`), o que dá a unicidade por
  (produto, fundo, originador, remessa) sem restrição nova. Nenhum vigente existente muda
  (`proc_id` nulo).
- **Uma linha na tela, vários lotes:** a remessa pode ter vários (originador, fundo), cada um com seu
  lote aberto (um lote real por (fundo, originador), como a D22 já exige); o fechamento da linha
  `proc:` fecha todos de uma vez (3.4).
- **Volume:** os pagamentos de uma remessa chegam em rajada para o mesmo vigente (até 18 mil no 1637):
  a trava por chave concentra mais que em `por_chave`. O recuo para avulso cobre (3.1, regra 5) e o
  fechamento da remessa leva os avulsos; medir antes de ligar (consulta 6, seção 9, e R9).
- **Troca de agrupamento com lote aberto:** a linha do lote aberto é a do **próprio** vigente
  (campos gravados), não a do agrupamento atual. Lote aberto antigo aparece como linha própria até
  ser fechado (tela ou horário); a chegada já usa a chave nova. A validação de
  `_produto_da_linha_do_lote_fake` (TS-5583) passa a aceitar também a chave de um vigente aberto
  existente. A linha sem origem fecha todos os vigentes abertos de (produto, originador, fundo),
  como já aprovado na revisão de 08/11 da TS-5567 (item 1a).

### 3.4 Fechamento

**Núcleo comum**, novo `_close_fake_batch` para chaves `origem:`, sem olhar modalidade nem flag:

1. `SET LOCAL` de `statement_timeout` e `lock_timeout` (como hoje, `refact.py:1319-1327`).
2. `UPDATE liquidacao_lote_vigente SET fechado = true WHERE <chave> AND fechado = false RETURNING
   liquidacao_lote_id`: espera no máximo a chegada em andamento; depois dele, toda chegada vê
   `fechado` e abre outro lote.
3. Lote de destino = o lote aberto devolvido; sem lote aberto, um lote novo (como hoje).
4. `UPDATE` guardado dos avulsos da chave (D9, qualquer data) **para o mesmo lote** (D2: uma linha,
   um lote, como a D22). Lote novo com zero linhas → `rollback`, "nada a fechar" (como hoje).
5. Commit; limpa o cache legado; manda à esteira (`_send_real_batches_to_pipeline`,
   `refact.py:2483`). O evento INFO "Fechamento de lote fake concluído" ganha `open_batch_id` e a
   contagem de avulsos.

**Por caminho:**

| Caminho | O que muda |
|---|---|
| Tela (`/fake-batches/close`) | usa o núcleo |
| Horário (TS-5570) | a lista de chaves do produto passa a ser **vigentes abertos do produto ∪ chaves com avulso apto**; cada uma pelo núcleo |
| Fim da remessa (TS-5572), qualquer produto `automatico` | `por_chave`: fecha pelo núcleo o lote aberto das chaves que a remessa tocou (a chave inteira, D4 da TS-5572); `por_remessa`: fecha o lote aberto da própria remessa, pelo núcleo da remessa (abaixo) |
| Linha `proc:` (tela, horário, fim da remessa) | núcleo da remessa (novo `_close_remittance_fake_batch`): `UPDATE ... SET fechado = true WHERE proc_id = <remessa> AND fechado = false RETURNING` (usa o índice parcial); por (originador, fundo) com avulso da remessa, o destino é o lote aberto devolvido do mesmo par, senão lote novo; vigente aberto sem avulso fecha igual; tudo num commit, depois o envio à esteira |
| `lote_automatico` legado (até a TS-5572) | **não muda** (o legado não se corrige, é substituído): não enxerga o lote aberto. Por isso o produto `automatico` só entra no lote aberto quando a TS-5572 estiver em produção (recomendação da D36 no plano da TS-5567; alternativa na seção 7) |
| `POST /liquidacao/` legado (até a TS-5568) | fecha vigente sem olhar a flag (Tarefa 4 do plano atual, mantida); avulsos seguem no `create_by_originador` |
| Beat legado (só o 1604) | fecha vigente sem olhar a flag (Tarefa 5 do plano atual, mantida) |
| `esteira_baixar` e `liquidar_task` | **guarda nova:** antes de qualquer coisa, `UPDATE ... SET fechado = true WHERE liquidacao_lote_id IN (...) AND fechado = false` e commit. Cobre `/liquidar` (D5), `reenviar` e qualquer envio futuro. Sem efeito nos lotes que já chegam fechados |

### 3.5 Pagamentos que ficam sem lote

- **D9 tardia:** a cessão termina depois da liquidação. Fica avulso e entra no próximo fechamento
  da chave. **[H]** volume no Mercato Libero (consulta 2): é o que define o custo do passo 4.
- **Recompra/aditamento:** nascem `cadastrado` sem passar por `EstadoCadastrado`
  (`framework/regras/cessao/aditamento_recompra.py:140-153`); seguem avulsos. Podem chamar a
  mesma entrada depois, se o volume pedir.
- **Avulsos do dia do deploy** (produtos que hoje não acumulam): nada a fazer; o primeiro
  fechamento de cada chave os junta ao lote. Em 27/10 os 15 maiores grupos sem lote tinham até
  1.514 pagamentos (`evidence/closing-group-sizes-2026-10-27.md`); repetir no dia (consulta 5).
- **`por_remessa` e `automatico` (D36):** entram no lote aberto como os demais; o que ficar avulso
  (parcela sem fundo, falha de entrada) o fechamento da remessa leva.

### 3.6 Tela e listagens

- **"Fechar lotes" (`listar_lotes_fake`, `refact.py:629-785`):** a linha da chave junta o lote
  aberto (sempre listado, sem janela de data: é o que o fechamento leva) e os avulsos da janela.
  `qtd_registros`, `valor_pago` e `qtd_aptos` somam os dois. Soma e contagem do lote aberto por
  LATERAL (subconsulta por linha) no índice de `liquidacao_lote_id`: 211 mil pagamentos em 0,12 s;
  com o `proc_id` de cada pagamento, 11,8 s [C, `evidence/real-batches-replica-2026-10-20.md`].
  Por isso a linha não monta `proc_ids` do lote aberto (só dos avulsos). **[H]** se o front usa
  `proc_ids` nessa linha.
- **Linha `proc:` (D36):** soma os lotes abertos de todos os vigentes da remessa (índice parcial por
  `proc_id`) com os avulsos da remessa. O `proc_id` da linha é a chave e **nunca fica vazio**; `proc_ids`
  traz só o `proc_id` da remessa (sem consulta por pagamento). A linha com lote aberto aparece sempre,
  sem janela de data, como a de origem.
- **Pagamentos da linha** (`/fake-batches/payments`): os do lote aberto mais os avulsos.
- **Exclusão na tela:** hoje pula pagamento com lote (`COM_LOTE`, `refact.py:2167`). Passa a
  apagar também pagamento do lote aberto da linha, travando antes o vigente e conferindo
  `fechado = false` e lote `pendente`, por blocos (o orçamento por tarefa já existe). A decisão 2 da
  revisão de 08/11 (sem "Excluir" em "todas as datas") continua. Na linha `proc:`, a trava é a dos
  vigentes abertos da remessa (índice parcial), sempre antes das linhas de pagamento. Hoje a linha
  de remessa não exclui por data (a remessa inteira), e isso continua.
- **"Lotes reais"** (`/lotes/reais`): hoje o lote aberto aparece como `pendente` com soma viva
  (`repository.py:727-755`). Proposta: some de lá até fechar (D6), o que também tira dele os botões
  de reenviar e liquidar.
- **Contrato do BFF e do front:** formatos de chave iguais aos de hoje e da TS-5583; campos novos
  só opcionais.

### 3.7 TS-5582 e esteira de baixa

- A TS-5582 já recusa descartar lote de vigente aberto (`api/liquidacao/lote_vazio.py:60-79` na
  branch) e descarta lote vazio na esteira (`descartado`). Com o nascimento junto do primeiro
  pagamento, o vazio só aparece por exclusão ou movimentação depois; ao fechar, a esteira o
  descarta. A guarda nova da esteira (3.4) roda **antes** de `separar_lotes_sem_pagamento`, senão o
  vazio de vigente aberto vira "não descartável". Conflito de merge previsível em `esteira_baixar`.
- O resto da esteira não muda: o lote aberto fechado é um lote `pendente` comum.

## 4. Concorrência e custo

- **Chegada:** hoje não há serialização por chave [C, 2.1]. A proposta serializa um comando e um
  commit por pagamento. Estimativa **[H]**: 2 a 5 ms de trava → 200 a 500 chegadas por segundo por
  chave. O que medir: pico de pagamentos por segundo por chave no 80 (consulta 1) e, no Datadog,
  tasks `esteira_liquidacao` por segundo. O 80 tinha 7 vigentes abertos em 08/11, então a carga se
  divide em ~7 chaves. Proteções: `lock_timeout` curto com recuo para avulso (nunca prende o worker
  nem erra a liquidação) e o desligamento de emergência (D8). Plano B se o pico chegar perto:
  trava compartilhada para chegadas e exclusiva para abrir e fechar (D1 b), com o risco de o
  fechador esperar indefinidamente atrás de chegadas contínuas **[H]**, limitado pelo
  `lock_timeout` de 30 s do fechamento (`refact.py:92`).
- **Fechamento:** um `UPDATE` de uma linha no vigente mais os avulsos. O tamanho do lote não entra.
  As 7 linhas do 80 com 967 mil pagamentos (08/11) fecham em segundos, contra ~1 h no plano
  anterior (967 mil ÷ 170 a 290 por segundo). O arquivo de 621 mil continua sendo gerado pela
  esteira, fora do limite de 480 s, como hoje.
- **Avulsos:** custo ≈ avulsos ÷ (170 a 290 por segundo) [C, ritmo do 1901 em
  `03-post-production-cases.md`]: 1.500 → até 9 s; 80 mil → 4,6 a 7,8 min, perto dos 480 s. Enquanto
  o passo 4 roda, as chegadas da chave esperam até o `lock_timeout` e viram avulsos (autocorrige
  no fechamento seguinte). Precisa ficar bem abaixo de 80 mil por chave: consulta 2 e o evento de
  recuo (3.2, passo 4) dizem se fica.
- **Listagem:** soma e contagem do lote aberto, ~0,1 s por 200 mil [C, acima]; sem `proc_ids`.

## 5. Transição de produção

1. **Antes do deploy (réplica, somente leitura):** consulta 4 (retrato dos vigentes abertos com lote
   fora de `pendente`, guardado para a TS-5573: a primeira chegada depois do deploy substitui esses
   ponteiros e apaga a marca do B25); consultas 1, 2 e 3.
2. **TS-5582** (enviada) e **TS-5583** (sem mudança de escopo) entram antes.
3. **Fase 1 (TS-5567 reescrita), um deploy:** chegada nova com todas as guardas, ainda só nos
   produtos com `acumula_liquidacoes` (os 13 de hoje: 4, 80, 81, 911, 944, 977, 1076, 1109, 1211,
   1212, 1213, 1373, 1406); fechadores sem flag e com a chave nova; guarda na esteira e na
   `liquidar_task`; listagem com lote aberto. Para a operação nada muda por fora; somem B14, B25,
   o lote vazio e a falta da D9. **Sem drenagem:** os vigentes abertos `pendente` seguem recebendo.
   Se a consulta 3 mostrar fundo divergente nesses produtos, fechar uma vez, depois do deploy, os
   vigentes antigos dessas chaves (tela ou `POST`).
4. **TS-5596:** limpeza dos vazios e `fechado = true` nos vigentes dos vazios e nos `concluido`
   abertos (depois do retrato do passo 1).
5. **TS-5570:** liga o horário no Mercato Libero sem drenar e sem fechar em blocos (D20); só os
   avulsos contam para o tamanho.
6. **Fase 2:** tira o portão da flag: todos os produtos, exceto `por_remessa` e `automatico` (até
   a TS-5572); exclusão na tela; lote aberto fora de `/lotes/reais`. Para os 131 `manual` e o 1604:
   a linha da tela passa a ter lote aberto, o gesto (fechar a linha) é o mesmo. Avulsos do dia
   entram no primeiro fechamento de cada chave (consulta 5 no dia).
7. **Depois:** TS-5568 e TS-5572 (esta liga o lote aberto no `automatico + por_chave`). Por fim,
   card para apagar `acumula_liquidacoes`, o valor `acumulado` e o código legado do vigente que
   restar (`repository.py:476-495`, `service.py:1165-1185`). **A tabela fica:** ela é o lote aberto.

## 6. Impacto em cada plano

| Plano | Sai | Entra | Prazo |
|---|---|---|---|
| TS-5567 | Tarefas 1 e 2 (parar o acúmulo); Tarefa 8 (drenagem) vira retrato do B25 | chegada nova (3.2), guarda na esteira e no `/liquidar`, núcleo do fechamento (3.4), listagem e exclusão com lote aberto, `/lotes/reais`; **D36:** na Fase 2, migration do `proc_id` no vigente, chegada pela chave `proc:`, fechamento da remessa pelo núcleo, listagem e exclusão da linha `proc:`, e o automático no portão (depois da TS-5572); Tarefas 3, 4 e 5 (fechadores sem flag) **ficam**, com a chave nova; Tarefas 6 e 7 (datas opcionais na cessão) ficam | maior que o plano anterior; 18/11 só para a Fase 1 [H]; Fase 2 a seguir |
| TS-5583 | nada a refazer | D3 (recusar acúmulo com sem origem) e as recusas de acúmulo ficam inofensivas e somem com a flag; a validação da chave aceita também vigente aberto (3.3) | igual |
| TS-5570 | drenagem antes de ligar; fechar em blocos (decisão 6) | lista de chaves = vigentes abertos ∪ avulsos aptos; medir avulsos, não o grupo da rodada | pode antecipar: depende só da Fase 1 |
| TS-5568 | — | `POST /liquidacao/` usa o núcleo; o `fundo_id` do corpo é o da parcela (conferir com a consulta 3 e com o Atlas, Tarefa 1) | igual |
| TS-5572 | — | **D36:** o gatilho `automatico` passa a usar lote aberto (`por_chave` e `por_remessa`); o fim da remessa fecha o lote aberto das chaves tocadas (`por_chave`) e o da própria remessa (`por_remessa`) pelo núcleo da TS-5567, e a consulta das chaves da remessa passa a enxergar pagamento já dentro do lote aberto | igual; a TS-5572 entra antes de o automático ligar o lote aberto |
| TS-5582 / TS-5596 | — | 5582 sem mudança (ordem da guarda na esteira, 3.7); 5596 fecha também os vigentes `concluido` abertos | igual |
| TS-5573 | — | parte do retrato da consulta 4; a correção dos afetados segue com `reenviar` | igual |
| Front e BFF | Tarefas 9 e 10 do plano atual ("todas as datas") perdem urgência (D10) | nada obrigatório: chaves iguais; campos novos opcionais | — |
| E1 (ETL) | o motivo principal (pagamento sem lote some do ETL) quase some: o pagamento tem lote ao chegar | `left join` segue certo para os avulsos; manter o aviso do `descartado` | prioridade menor |

## 7. Decisões para o Pietro

**D36 (10/11, depois das respostas abaixo):** o lote aberto vale em qualquer caso, sem exceção. As decisões 3 (`por_remessa` fora) e 4 (`automatico` fora até a TS-5572) estão **substituídas**: a remessa ganha lote aberto pela chave `proc:` (3.3) e o automático também usa lote aberto (3.4). O que muda de plano está nas TS-5567 e TS-5572.

**Respostas de 10/11 (Pietro):** todas aprovadas como recomendado (a 10 em 10/11, à
tarde). Na 3, a remessa continua fora do lote aberto, mas vem para o fluxo novo: o fechamento manual
pela linha `proc:` já é do fluxo novo (`_close_remittance_fake_batch`), e o automático no fim da
remessa vem com a TS-5572. Na 8, o interruptor entra na lista de limpeza pós-deploy. Na 10, com
**feedback ao usuário**: a listagem devolve, por linha, quantos pagamentos sem lote de fora do período
filtrado o fechamento vai levar, e o diálogo de confirmação do front mostra esse número (campo
opcional no BFF e no front, na TS-5567). Entra um item novo, vindo da revisão da TS-5585 e aprovado: o núcleo de fechamento
grava no lote o instante em que ele foi fechado, e o resumo diário conta os lotes por esse instante.

1. **Trava da chegada.** (a) exclusiva por chave, comando único, `lock_timeout` curto com recuo
   para avulso; (b) compartilhada nas chegadas e exclusiva para abrir e fechar. **Recomendação:
   (a)**; (b) só se a consulta 1 mostrar pico perto da capacidade.
2. **Avulsos no fechamento.** (a) entram no próprio lote aberto, na mesma transação (uma linha, um
   lote); (b) lote separado, como o `_close_fake_batch` de hoje (até dois arquivos por linha).
   **Recomendação: (a).**
3. ~~**`por_remessa` usa lote aberto?**~~ **Substituída pela D36 (10/11):** sim, com `proc_id` no
   vigente, migration nova e índice novo (alternativa (b) original). Texto original: (a) não, espera
   avulso e fecha pela remessa (até 18 mil por remessa no 1637); (b) sim. Era **(a)**.
4. ~~**`automatico` antes da TS-5572.**~~ **Substituída pela D36 (10/11):** o automático usa lote
   aberto. Texto original: (a) fora até a TS-5572 (o `lote_automatico` legado só vê avulso); (b) entra
   já e o legado passa a fechar vigente. Era **(a)**. Como ligar sem corrigir o legado: decisão 11.
5. **`POST /liquidacao/liquidar` em lote aberto.** (a) a task fecha o vigente antes de enviar
   (mantém a rota para quem chama hoje, **[H]** Atlas); (b) a rota recusa com 400.
   **Recomendação: (a).**
6. **Lote aberto em "Lotes reais".** (a) some até fechar; (b) aparece nas duas telas, marcado.
   **Recomendação: (a)**: um lugar só e sem botão de envio nele.
7. **Fases.** (a) Fase 1 nos 13 que acumulam, Fase 2 para todos; (b) tudo num deploy.
   **Recomendação: (a)**: a Fase 1 destrava a TS-5570 e testa a trava no 80 antes de espalhar.
8. **Desligamento de emergência.** (a) variável no Parameter Store que desliga a entrada no lote
   aberto (os fechamentos seguem varrendo avulsos, então desligar é seguro); (b) só rollback por
   deploy. **Recomendação: (a)**. Não é configuração de produto.
9. **Fundo da chave.** (a) o da parcela (tela e fechamento novo); (b) o da cessão (vigente e legado
   hoje). **Recomendação: (a)**; se a consulta 3 der zero, não há decisão.
10. **"Todas as datas" no BFF e no front.** (a) manter as Tarefas 9 e 10 na mesma release; (b)
    adiar: o lote aberto aparece sempre, e avulso antigo vai para o resumo diário (TS-5585).
    **Recomendação: (b)**, com as datas opcionais só na cessão.
11. **(D36) Automático antes da TS-5572.** (a) o produto `automatico` só liga o lote aberto quando a
    TS-5572 estiver em produção (o legado não muda; até lá segue avulso, como hoje); (b) o
    `lote_automatico` legado passa a fechar também o vigente das chaves da remessa. **Recomendação:
    (a)**: o legado é apagado na TS-5572 (corrigi-lo é trabalho jogado fora, e a regra é substituir),
    e a D36 passa a valer para o automático no mesmo dia em que a TS-5572 sobe. (b) só se a TS-5572
    escorregar além da Fase 2 e a operação exigir.
12. **(D36) Como o vigente guarda a remessa.** (a) coluna `proc_id` (UUID) com índice parcial, mais
    `origem_pagamento = 'proc:<proc_id>'` para manter a restrição única existente; (b) sem coluna:
    só `origem_pagamento = 'proc:<proc_id>'` (sem migration; a busca usa o índice de
    `origem_pagamento`, mas junta por texto). **Recomendação: (a)**: junta direto com
    `liquidacao_processo.proc_id` e deixa a origem do vigente legível; custo: uma migration só com
    `add_column` e índice.

## 8. Riscos e o que não foi confirmado

- **R1 [H] Disputa da trava no pico do 80.** Validar: consulta 1 e, depois da Fase 1, a contagem do
  evento de recuo por hora no Datadog.
- **R2 [H] D9 tardia em massa no Mercato Libero** devolve o custo do `UPDATE` ao fechamento.
  Validar: consulta 2. Saída, se precisar: ao cadastrar a cessão, levar os avulsos dela ao lote
  aberto (gancho na esteira da cessão; acopla os dois fluxos).
- **R3 [H] Fundo ou origem divergentes** deixam vigente antigo sem fechador pela tela. Consulta 3.
- **R4 [C] Exclusão legada concorrente** (`DELETE /liquidacao/pagamentos` e a task de exclusão por
  `proc_id` aceitam lote `pendente` sem trava, B16) passa a valer para todos os produtos. Correção
  só quando o legado for substituído; até lá, raro.
- **R5 [C] Cache Redis do lote fake legado** soma todo pagamento inserido (`database/listeners.py:110-155`)
  e não desconta a entrada no lote aberto: `GET /liquidacao/lotes/fake` e `GET /liquidacao/` ficam
  errados para todos. **[H]** quem ainda lê: Datadog por rota.
- **R6 [C] Data do lote = primeira chegada** (como os 13 hoje): o lote fechado hoje e aberto na
  sexta aparece na sexta em "Lotes reais"; muda o desempate da conciliação
  (`tasks/conciliacao_liquidacao.py:61-68`) e a regra de exclusão por data
  (`api/liquidacao/validator.py:108-125`). Conferir com a operação na Fase 2.
- **R7 [C] Exceção na entrada hoje vira `errado`**; o código novo precisa capturar e recuar (3.2,
  passo 4), com teste.
- **R8 [H] Origem nula no acúmulo de hoje:** o vigente exige origem e a criação falharia; não deve
  ocorrer nos 13. Sem efeito no desenho (`''`).
- **R9 [H] (D36) Rajada de uma remessa na trava de um vigente.** Uma remessa com milhares de pagamentos
  chega em paralelo para o mesmo vigente (por originador e fundo): a trava por chave fica mais quente
  que em `por_chave`, e o recuo para avulso pode ficar frequente. Efeito: o custo do `UPDATE` do fechamento
  da remessa volta a depender dos avulsos (o limite é o de hoje, cerca de 170 a 290 pagamentos por
  segundo no `UPDATE`; o 1637 chega a 18 mil por remessa). Validar: consulta 6 e o evento de recuo por
  hora depois de ligar `por_remessa`; o interruptor desliga a entrada sem deploy.
- **R10 [C] (D36) Fechadores legados veem o vigente da remessa.** `POST /liquidacao/` legado e o beat
  filtram por produto e originador (`repository.py:476-495`), então fecham também os vigentes `proc:`
  do produto. É o comportamento aprovado ("fecha vigente sem olhar a flag"); só confirmar com a
  operação que um fechamento de originador no meio de uma remessa em andamento é aceitável.
- **Não confirmado:** se a cessão sai de `cadastrado` depois (o apagamento lógico só alcança
  `rejeitado` e `errado`, `models.py:4484`, `receptores/base.py:131-142` [C]; transições de saída
  não mapeadas [H]); se `commit()` dentro do savepoint de `repository.py:417-420` fecha a transação
  externa no SQLAlchemy 1.3 (o código novo usa o objeto do savepoint, como
  `refact.py:926-938`); quem grava `data_envio_liquidacao` pela rota `PATCH`.

## 9. Consultas para a réplica (somente leitura, uma por vez)

Conferir nomes de colunas antes de rodar; se passar de 120 s, reduzir o período.

```sql
-- 1. Pico de chegadas por segundo e por chave, produto 80 (3 dias)
SET statement_timeout = '120s';
SELECT date_trunc('second', p.data_criacao) AS segundo, c.originador_id, pa.fundo_id,
       p.origem_pagamento, count(*) AS pagamentos
FROM liquidacao_processo lp
JOIN liquidacao_pagamento p ON p.liquidacao_processo_uuid = lp.uuid
JOIN contrato_parcela pa ON pa.id = p.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
WHERE lp.produto_id = 80 AND lp.data_criacao >= now() - interval '3 days'
GROUP BY 1, 2, 3, 4 ORDER BY pagamentos DESC LIMIT 20;

-- 2. Liquidações que chegam a `cadastrado` antes da cessão (produto 80, 2 h de pico; repetir)
SET statement_timeout = '120s';
WITH pag AS (
  SELECT p.id, lp.uuid AS liq, c.processo_uuid AS cessao
  FROM liquidacao_processo lp
  JOIN liquidacao_pagamento p ON p.liquidacao_processo_uuid = lp.uuid
  JOIN contrato_parcela pa ON pa.id = p.parcela_id
  JOIN contrato c ON c.id = pa.contrato_id
  WHERE lp.produto_id = 80
    AND lp.data_criacao BETWEEN '<inicio>' AND '<inicio>'::timestamp + interval '2 hours')
SELECT count(*) AS pagamentos,
       count(*) FILTER (WHERE cessao_cad IS NULL OR cessao_cad > liq_cad) AS cessao_depois
FROM (SELECT pag.id,
        (SELECT min(l.data_criacao) FROM liquidacao_processo_log l
          WHERE l.liquidacao_processo_uuid = pag.liq AND l.estado_atual = 'cadastrado') AS liq_cad,
        (SELECT min(l.data_criacao) FROM contrato_processo_log l
          WHERE l.processo_uuid = pag.cessao AND l.estado_atual = 'cadastrado') AS cessao_cad
      FROM pag) x;

-- 3. Fundo da parcela × fundo da cessão, parcela sem fundo e origem nula (1 dia)
SET statement_timeout = '120s';
SELECT lp.produto_id, count(*) AS pagamentos,
       count(*) FILTER (WHERE pa.fundo_id IS DISTINCT FROM cp.fundo_id) AS fundo_diferente,
       count(*) FILTER (WHERE pa.fundo_id IS NULL) AS parcela_sem_fundo,
       count(*) FILTER (WHERE p.origem_pagamento IS NULL) AS origem_nula
FROM liquidacao_processo lp
JOIN liquidacao_pagamento p ON p.liquidacao_processo_uuid = lp.uuid
JOIN contrato_parcela pa ON pa.id = p.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo cp ON cp.uuid = c.processo_uuid
WHERE lp.data_criacao >= now() - interval '1 day'
GROUP BY 1
HAVING count(*) FILTER (WHERE pa.fundo_id IS DISTINCT FROM cp.fundo_id
                          OR pa.fundo_id IS NULL OR p.origem_pagamento IS NULL) > 0
ORDER BY 2 DESC;

-- 4. Retrato para a TS-5573: vigentes abertos com lote fora de `pendente` ou já com envio
SET statement_timeout = '120s';
SELECT v.id, v.produto_id, v.fundo_id, v.originador_id, v.origem_pagamento, v.liquidacao_lote_id,
       l.estado_atual, l.data_envio_liquidacao, l.data_criacao, v.data_atualizacao
FROM liquidacao_lote_vigente v
JOIN liquidacao_lote_processo l ON l.id = v.liquidacao_lote_id
WHERE v.fechado = false
  AND (l.estado_atual <> 'pendente' OR l.data_envio_liquidacao IS NOT NULL);

-- 6. (D36) Tamanho e simultaneidade das remessas `por_remessa` e `automatico` (30 dias)
SET statement_timeout = '120s';
SELECT lp.produto_id, lp.proc_id, count(*) AS liquidacoes,
       min(lp.data_criacao) AS inicio, max(lp.data_criacao) AS fim,
       count(DISTINCT (c.originador_id, pa.fundo_id)) AS pares_originador_fundo
FROM liquidacao_processo lp
JOIN liquidacao_pagamento p ON p.liquidacao_processo_uuid = lp.uuid
JOIN contrato_parcela pa ON pa.id = p.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
WHERE lp.proc_id IS NOT NULL AND lp.data_criacao >= now() - interval '30 days'
  AND lp.produto_id IN (SELECT produto_id FROM produto_config
                         WHERE agrupamento_lote_liquidacao = 'por_remessa'
                            OR gatilho_fechamento_lote_liquidacao = 'automatico')
GROUP BY 1, 2 ORDER BY liquidacoes DESC LIMIT 30;
```

5. Avulsos por chave no dia do deploy: consulta 1 de `attachments/sql/new_closing_pending_groups.sql`,
   com `lp.data_criacao >= now() - interval '30 days'`.

### D36 aplicada (10/11)

- 0.1 e 0.5, 3.2 (passos 1 e 2), 3.3, 3.4 (linhas de remessa, fim da remessa e legado automático),
  3.5, 3.6 (linha `proc:`, exclusão) e 6 (TS-5567, TS-5572) ajustadas: o lote aberto vale em qualquer
  caso.
- Decisões 3 e 4 marcadas como substituídas; entram as decisões 11 (automático antes da TS-5572) e
  12 (como guardar a remessa no vigente).
- Riscos novos: R9 (rajada da remessa na trava) e R10 (fechadores legados veem o vigente da remessa).
- Consulta nova: 6 (tamanho e simultaneidade das remessas), na seção 9.
