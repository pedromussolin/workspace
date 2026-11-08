# Fechamento de lotes de liquidação: desenho da tarefa 13 (épico TS-5278)

Rascunho de 08/11/2026, para revisão do Pietro antes de qualquer código. Linhas de código valem
para `platform-cessao` `origin/master` **6c152445d** (05/11/2026), salvo quando indicado.
[C] = conferido no código, na réplica ou no Datadog; [H] = hipótese, com o caminho para validar.

## 1. Objetivo e prazo

- **Objetivo:** os lotes de liquidação do Mercato Libero e da Voltis fecham sozinhos, dentro da
  cessão, por horário definido por produto, sem a varredura que o Rafael Frankl roda na VM de
  automações. No caminho, o fechamento fica num modelo único e genérico (qualquer produto), com
  agendamentos no banco, avisos por e-mail e um resumo diário.
- **Prazo de conhecimento: 13/11/2026**, saída do Rafael. Até lá precisa estar com o Pietro tudo o
  que só o Rafael sabe (agenda real, credenciais, exceções: TS-5565).
- **Prazo do sistema:** a meta é o mais perto possível de 13/11; os cards têm prazos até 04/12.
  A VM **só é desligada depois de tudo estar no sistema** (decisão de 05/11); até lá ela segue
  rodando sob a responsabilidade do Pietro (D25: sem ponte no legado).
- **Fora do recorte:** a chegada dos dados (receber os arquivos do Mercato Libero, transformar,
  subir). O contrato entre as partes é "dados do dia no sistema até o horário de corte do produto".

## 2. Princípios

1. **Blindagem contra o parceiro.** Quando fechar (horário) e como agrupar (chave) são definidos
   por produto do nosso lado. A Voltis manda pagamento a pagamento, inclusive os do mesmo lote, e no
   1043 cada pagamento traz uma origem própria (um UUID); o sistema absorve isso em vez de exigir
   mudança do parceiro.
2. **Tudo no `refact.py`.** Código novo de liquidação vai em `cessao/api/liquidacao/refact.py`
   (`RefactLiquidacaoService`, `RefactLiquidacaoRepository`). O legado não ganha correção: é
   substituído e apagado (decisão de 03/11).
3. **Agendamento só pelo banco.** Nenhum horário fixo no beat (o agendador do Celery) nem no
   Parameter Store. Um scheduler genérico, com jobs em tabela e filtro por módulo.
4. **Features genéricas desacopladas.** E-mail, scheduler e anexos não conhecem liquidação; quem
   integra é o módulo da liquidação (ex.: a regra "horário depois do corte" mora na liquidação, não
   no scheduler).
5. **Nomes explícitos de liquidação.** Colunas, enums e jobs dizem que são da liquidação (haverá
   análogos para a cessão). Código da cessão em PT-BR.
6. **Sem mão no banco para operar.** Os lotes vazios (B26) são sobras de correções feitas direto no
   banco. Configuração e correção passam a ter caminho no sistema, com log (a área administrativa
   fecha esse ciclo no fim).

## 3. Vocabulário

| Termo | O que é |
|---|---|
| Pagamento | linha de `liquidacao_pagamento`; vai para um lote quando `liquidacao_lote_id` é preenchido |
| Lote (real) | linha de `liquidacao_lote_processo`; é o que vai para a administradora (ADM) |
| Linha / lote fake | agrupamento, na tela, dos pagamentos ainda sem lote, pela chave do produto |
| Chave | o que define a linha: `origem:<origem>:<produto>:<originador>:<fundo>` ou `proc:<proc_id>` (`_chave_do_lote_fake_por_modalidade`, `refact.py:587`; `FakeBatchKey`, `refact.py:446`, `parse` em `:472`) |
| Remessa | conjunto de pagamentos de um `proc_id` |
| Lote vigente | lote aberto que recebe pagamentos ao chegarem, na modalidade `acumulado` (`liquidacao_lote_vigente`) |
| D9 | regra para entrar em lote: a cessão do contrato precisa estar `cadastrado` |
| Gatilho | quando o lote fecha: `manual`, `agendado` ou `automatico` |
| Agrupamento | como os pagamentos se juntam: `por_chave`, `por_chave_sem_origem` ou `por_remessa` |
| Corte da conciliação | horário (padrão 14h de Brasília) em que a conciliação automática roda; lote fechado depois vai para a fila manual |
| Fila manual | lotes em `conciliacao_manual`, que dependem de aprovação pela tela |
| Scheduler | agendador com jobs em tabela, no molde da `apl-shared-service` (`scheduled_jobs`, `job_executions`) |

## 4. Desenho por peça

### 4.1 Lotes vazios — TS-5582 (prazo 10/11)

- **Situação [C, réplica, 07/11, lotes criados em 60 dias]:** 15,3 mil lotes sem nenhum pagamento:
  `errado` 10.293, `conciliacao_manual` 3.222, `pendente` 1.319, `liquidando` 433, `concluido` 96.
  Na fila manual, só 7 lotes do 1637 têm pagamentos (226, R$ 47.341,20).
- **Causa [C]:** não é o fechamento atual. Todos os pontos que criam lote descartam lote sem
  pagamento: `LiquidacaoLoteProcesso.create_by_originador` (`cessao/database/models.py:6201`,
  com checagem de `rowcount`), `assign_proc_id_payments_to_new_batches` (`refact.py:911`, savepoint
  por grupo) e `_close_fake_batch` (`refact.py:2321`, rollback com zero pagamentos). Os vazios vêm de:
  - **1901, 12/09 23h03 a 13/09 8h34:** 10.247 lotes, um por pagamento; o envio à ADM falhou ("nome
    do arquivo de liquidação não está no padrão") e os pagamentos foram apagados (não existe mais
    pagamento criado nesse intervalo). O produto foi criado em 10/09.
  - **Voltis (713, 1043, 449), madrugadas de 22 e 23/09:** 3.640 lotes, um por pagamento, criados
    ~3 s depois de cada pagamento virar `cadastrado` (fechamento na chegada). No mesmo dia os
    pagamentos foram movidos para lotes por chave: os 3.189 pagamentos do 713 criados na rajada
    estão no lote concluído das 13h de 22/09; 1043 (13) e 449 (8) batem com os vazios da fila.
  - **Produtos com acúmulo (1109, 1373, 81...):** vigente `pendente` que nasce vazio ao reabrir
    (`cessao/api/liquidacao/repository.py:393` e `:406`); some com a TS-5567.
  - **Por que "direto no banco":** o log do lote só tem criação e roteamento; o código não tem
    caminho que desvincule pagamento de lote; a configuração atual desses produtos é `manual`, com
    `produto_config.data_atualizacao` anterior (713: jul/2026). Prova de que o lote nasceu com
    pagamento: o roteamento gravou `fundo_id` 120 ms depois da criação, e
    `LiquidacaoLoteProcesso.fundo` (`models.py:5975`) vem do primeiro pagamento.
- **O que muda:**
  1. Limpeza por script revisado pela DBA, com registro no log de cada lote (não `UPDATE` solto).
     Destino do lote vazio: **D26** (estado final novo `descartado` ou exclusão).
  2. Guarda (avaliar): lote sem pagamento não entra na baixa nem na conciliação. [C] Hoje o lote
     vazio quebra ao achar o fundo (`LiquidacaoLoteProcesso.fundo`, `models.py:5975`, faz `.first()`
     do primeiro pagamento e acessa `.parcela` de `None`). Na rotina de conciliação o erro é capturado
     em `_agrupar_por_conta` (`cessao/tasks/conciliacao_liquidacao.py:70-97`) e o lote vai para a fila
     manual com `conta_vinculada_nao_resolvida`, que é o motivo dos vazios do 713. O "aprovar" da
     fila (`cessao/api/liquidacao/service.py:501`) e a esteira (`cessao/tasks/liquidacao_lote.py:101`)
     montam o lote do mesmo jeito e também quebram: a operação não consegue tirá-los da fila.
  3. Os 7 lotes do 1637 com pagamentos: decisão da operação.
- **Dependências:** D26 antes de rodar a limpeza. Precisa estar feita antes de ligar o resumo
  diário (4.8). Não bloqueia a TS-5570.

### 4.2 Acúmulo como comportamento padrão — TS-5567 (prazo 18/11)

- **O que muda:** nenhum pagamento ganha lote ao chegar; ele espera sem lote até um fechamento
  (manual, horário ou fim da remessa). O fechamento novo junta por chave, de qualquer data, com a D9.
  - `EstadoCadastrado` (`cessao/framework/liquidacao/estados_liquidacao.py:332-358`) deixa de chamar
    `acumula_liquidacao` (`:349`); `fechar_lote` (`:342`) e `enviar_para_baixa` (`:335`) seguem no
    legado até a TS-5572.
  - A modalidade perde o `acumulado` e vira as duas colunas (4.3).
- **Transição por produto (armadilha conhecida):** os três fechadores de vigente só o enxergam com a
  modalidade/flag `acumulado`; trocar antes de drenar deixa lote órfão. Ordem: (1) parar o acúmulo na
  chegada e tirar a dependência da flag no mesmo deploy; (2) drenar os vigentes (no Mercato Libero, a
  varredura fecha no mesmo dia os vigentes abertos e os pagamentos sem lote); (3) trocar a
  modalidade; (4) ligar o agendado (TS-5570). Primeiro o Mercato Libero (4, 80, 81, 1406).
- **Fora do Mercato Libero:** 1109 (omnis) e 1373 (lemans_2) só depois da TS-5573 e das respostas do
  negócio ao B25 (10.562 pagamentos que entraram em lotes já enviados, R$ 10,9 mi). Os outros
  acumulados com vigentes abertos são drenados produto a produto, com o negócio.
- **A fazer:** medir na réplica pagamentos dentro de vigentes fora da D9 (LATERAL por lote); a
  listagem da tela esconde, pela janela de data, pagamento que espera vários dias.
- **Impacto externo:** só o ETL (4.12).

### 4.3 Duas colunas: gatilho × agrupamento — TS-5583 (prazo 18/11)

- **O que muda:** `produto_config.modalidade_fechamento_lote` (`models.py:1498`;
  `EnumBatchClosingModality` em `cessao/database/enum.py:804`) vira duas colunas independentes:
  - `gatilho_fechamento_lote_liquidacao`: `manual`, `agendado`, `automatico` (quem dispara);
  - `agrupamento_lote_liquidacao`: `por_chave`, `por_chave_sem_origem`, `por_remessa` (como junta).
  - A chave do lote sai **só** do agrupamento; o gatilho só define quem fecha. Listagem, fechamento e
    exclusão continuam usando a mesma chave (`_chave_do_lote_fake_por_modalidade`, `refact.py:587`;
    `FakeBatchKey.parse`, `:472`), que ganha o formato sem origem (ex.:
    `chave:<produto>:<originador>:<fundo>`; o prefixo sai no desenho).
- **Mapeamento da modalidade atual (backfill):**

  | Modalidade de hoje | Gatilho | Agrupamento |
  |---|---|---|
  | `manual` | manual | por_chave |
  | `acumulado` | manual | por_chave (até a TS-5567; Mercato Libero vai para `agendado` na TS-5570) |
  | `automatico_por_chave` | automatico | por_chave |
  | `automatico_por_remessa` | automatico | por_remessa |
  | `agendado` | agendado | por_chave |

  Contagem atual [C, réplica, 05/11]: 131 `manual`, 13 `acumulado`, 9 `automatico_por_chave`, 2
  `automatico_por_remessa`, 1 `agendado`.
- **Migração:** migration nova em `cessao/migrations/versions/` (nunca alterar uma existente), com
  backfill pelo mapeamento. A coluna antiga e as flags legadas (`lote_liquidacao`,
  `fechar_lote_por_proc_id`, `acumula_liquidacoes`, `baixa_por_agendamento`) seguem gravadas em
  sincronia até o BFF e o front trocarem; depois a coluna antiga sai em outra migration. A gravação
  do produto passa a derivar as duas colunas (como hoje deriva a modalidade, decisão de 27/10).
- **Onde muda [C, mapa em `~/repos/.artemis_v2/agentes/ts13-duas-colunas/mapa.md`]:**
  - Escrita: um caminho só, `apply_closing_modality` (`cessao/api/produto/closing_modality.py:8`),
    chamado em `cessao/api/cadastro/service.py:107` e `cessao/api/produto/sevice.py:43`; schemas em
    `cadastro/schema.py:223-269` e `produto/schema.py:54-84`.
  - Leitura da modalidade só em `refact.py` (chave em `:587-612`; usos em `:689`, `:1003`, `:1723`,
    `:2343`). O gatilho real hoje está nas flags (`estados_liquidacao.py:344`, `tasks/liquidacao_lote.py:244`)
    e o agrupamento por remessa em `fechar_lote_por_proc_id` (`models.py:5666`, `tasks/liquidacao_lote.py:268`).
  - Rotas legadas (`repository.py:605`, `:821`; `viewer.py:1134`, `:1297`) leem `fechar_lote_por_proc_id`:
    a flag fica coerente até o legado sair. `liquidacao_automatico` é a esteira de baixa, fora daqui.
  - BFF e front não têm tela nem schema de configuração do produto; dependem só dos prefixos da chave
    (`origem:` e `proc:`, contrato em `tests/contract/test_cessao.py:201-224` do BFF e
    `close-batches.ts:78` do front). O formato da chave sem origem precisa manter esses contratos.
  - Migration de referência: `c3f81d7a5e24` (coluna, enum e backfill); head atual `410aaaf27d06`.
    Proposta: colunas nulas, backfill por `CASE` sobre a modalidade, depois `NOT NULL`.
  - Código novo: `por_chave_sem_origem` em qualquer gatilho (chave, criação de lote e task agrupam por
    origem hoje). Validações: acúmulo × `por_remessa` segue recusado; acúmulo só com gatilho manual
    até a TS-5567.
  - Testes: 18 arquivos a ajustar (maiores: `test_closing_modality`, `test_batch_closing_modality`,
    `test_refact_liquidacao`).
- **Recurso genérico:** vale para qualquer produto. Absorve o item de renomear a coluna do
  `after-v2.md`.
- **Dependências:** entra junto ou logo antes da troca de modalidade da TS-5567 (ela já previa
  renomear o campo). Pré-requisito da TS-5570 para a Voltis 1043 (`por_chave_sem_origem`).

### 4.4 Scheduler da cessão em tabela — TS-5569 (prazo 18/11)

- **O que muda:** o modelo da shared vem para a cessão: tabela de jobs, tabela de execuções, beat
  que lê o banco a cada tique e dispara o que venceu com `FOR UPDATE SKIP LOCKED` (trava de linha
  que deixa um só disparador pegar cada job), atraso tolerado, resultado gravado, disparo manual e
  rotas genéricas filtradas por módulo. A lógica é copiável; modelos, rotas (flask-restx) e a
  ligação com Celery 5.2 e SQLAlchemy 1.3 se reescrevem.
- **Jobs que migram** (as 6 entradas fixas de `cessao/schedule/registro.py`, em UTC):
  `contrato_registro_baixa` (12h), renegociação BGT (11h), taxa de operação (20h), fechamento por
  agendamento legado (`fechar_lote_liquidacao_por_agendamento`, `cessao/tasks/liquidacao_lote.py:240`,
  19h UTC = 16h Brasília; substituído pela TS-5570), corte da conciliação
  (`conciliar_lotes_por_agendamento`, `cessao/tasks/conciliacao_liquidacao.py:190`) e verificação D0.
- **Conciliação lendo o mesmo registro (decisão de 08/11):** hoje o corte vem do Parameter Store
  (`horario_corte`, `cessao/shared/saldo_liquidacao/corte.py:58`; padrão 14h em `:26`) e só muda
  reiniciando o beat. O horário de corte **também** decide o destino do lote (`passou_do_corte`,
  `corte.py:81`, usado por `_destino_automatica`, `baixar.py:53`: fila do dia ou fila manual). Os dois
  passam a ler o mesmo job da tabela, para a rotina e o roteamento não divergirem. Padrões: corte 14h,
  verificação D0 20h (Brasília).
- **Horários em Brasília** no banco; a conversão para UTC fica no scheduler.
- **A decidir na aprovação da arquitetura:** onde fica o dia útil e o feriado (task ou scheduler);
  proteção contra disparo duplo (Redis ou só trava no banco; B24: o Redis cheio já descartou chaves).
- **Depois (fora do caminho crítico):** o registro de contagem por remessa (`cessao/utils/lote_controle.py`,
  Redis com TTL de 24h) pode ir para o banco.

### 4.5 Fechamento por horário por produto — TS-5570 (prazo 20/11)

- **O que muda:** um job do scheduler por produto (módulo `liquidacao`, `produto_id` no payload,
  horário no job; resolve a D8 sem coluna nova). A task lista todas as chaves do produto com
  pagamento apto (D9) e fecha cada uma pelo fluxo novo (`_close_fake_batch`, `refact.py:2321`, pela
  task `close_fake_batch` de `cessao/tasks/fake_batch_closing.py:13`, com a trava por linha), sem
  lista de combinações (a falha de 14/10 da varredura não se repete). Não roda em dia não útil.
- **Produtos e padrões (decisão de 08/11; o negócio confirma depois, D28):**

  | Parceiro | Produtos | Gatilho / agrupamento | Horários padrão (dia útil, Brasília) |
  |---|---|---|---|
  | Mercato Libero | 4, 80, 81, 1406, 15, 581 | agendado / por_chave | 16h, 17h, 18h e 20h45 (agenda da varredura hoje) |
  | Voltis | 449, 713, 1044 | agendado / por_chave | 13h30 (antes do corte das 14h) |
  | Voltis | 746 (`nao_aplica`) | agendado / por_chave | 13h30 (sem corte; D28) |
  | Voltis | 1043 | agendado / por_chave_sem_origem | 13h30 |

  - Mercato Libero está em `nao_aplica` na conciliação: sem preocupação com o corte.
  - Voltis (449, 713, 1043, 1044) está em `automatica`: lote fechado até 14h vai para
    `aguarda_conciliacao` e concilia no corte; depois disso, fila manual (`pos_horario_corte`).
    Pagamento que chega depois das 13h30 espera o fechamento do dia útil seguinte.
- **Transição com a varredura:** a varredura continua no `POST /liquidacao/` legado. Com o horário
  ligado, a rodada das 16h é desativada e as das 17h, 18h e 20h45 viram auditoria (se só recebem
  "nenhum pagamento apto", o horário cobriu tudo). Depois a varredura é desativada e nunca chama a
  rota nova. Rodar os dois juntos é seguro: os dois caminhos só pegam pagamento sem lote
  (`WHERE liquidacao_lote_id IS NULL` e checagem de `rowcount`).
- **Ordem no Mercato Libero:** 4, 80, 81 e 1406 só depois de drenados e com o acúmulo parado (4.2).
- **Antes de ligar no 15:** decidir com o time os 10 contratos presos da TS-5537.
- **Volume:** ~370 mil pagamentos por dia útil no Mercato Libero (80: ~263 mil). Grupo grande fecha
  num UPDATE só com `statement_timeout` (D20). Medir o maior grupo das 16h antes de ligar.
- **Dependências:** TS-5569, TS-5567 (Mercato Libero acumulado), duas colunas (1043).
- **Chegada da Voltis [C, réplica, 08/11, lotes de 14 dias, hora de criação do pagamento]:** 713:
  36.996 pagamentos até 13h30 (35.848 entre 0h e 6h) e 1.875 depois (R$ 230 mil, ~5%); 449: 133 e 5;
  1043: 129 e 7; 746 e 1044 sem lotes no período. O padrão de 13h30 pega ~95%; o resto espera o dia
  útil seguinte (hoje a operação fecha esses à tarde e eles já caem na fila manual). Uma segunda
  rodada à tarde, indo para a fila manual, fica para a D28.
- **746 (`voltis_antecipacao`):** também é da Voltis, `manual` e conciliação `nao_aplica`; entra no
  agendado sem preocupação com o corte (horário a definir na D28).

### 4.6 Aviso de horário depois do corte (opção C)

- **O que muda:** ao gravar ou alterar o horário de fechamento de um produto que tem par
  produto+fundo em `automatica` (`produto_fundo.conciliacao_liquidacao`; `ProdutoFundo.get_conciliacao_liquidacao`,
  `models.py:1237`), se o horário ficar no corte ou depois, **salva e avisa**: a resposta traz o aviso
  e sai um e-mail pela shared.
- **Onde:** no módulo da liquidação (serviço/rota que grava os horários de fechamento por cima do
  scheduler genérico), não no scheduler, que continua sem conhecer conciliação. O corte comparado é
  o da tabela (4.4).
- **Até a área administrativa:** a validação fica no backend. A tela que altera horários de corte e
  mais entra no fim da tarefa 13 (`after-v2.md`).
- **Dependências:** TS-5569, integração com o envio de e-mails (4.7/4.8), D27 (destinatários).

### 4.7 Anexo no envio de e-mails da shared — TS-5584 (prazo 20/11, apl-shared-service)

- **Hoje [C, `apl-shared-service` `origin/master` 8e4a1ab]:** `POST /email-dispatches`
  (`src/delivery/api/__init__.py:22`, corpo `EmailDispatchBody` em
  `src/modules/email_dispatch/schemas.py`) aceita template versionado (Jinja2) ou assunto+HTML,
  `variables`, `targets` (`EMAIL` ou `GROUP` do Entra ID), `idempotency_key` global e `created_by`;
  responde 202 e envia numa task do Celery pelo Microsoft Graph, das caixas compartilhadas. Com
  template, o remetente padrão é o do template. **Não aceita anexo** (anexo existe só nos workflows).
  A API não tem autenticação na aplicação: a chamada é interna ao cluster.
- **O que muda (decisão de 08/11):** a shared gera o Excel a partir de dados. Campo genérico
  `attachments[{type: "xlsx", filename, sheets[{name, columns[{key, title, type}], rows}]}]`, com
  tipos de coluna `text`, `integer`, `decimal`, `currency`, `date`, `datetime` (decimal em texto). A
  task de envio monta o `.xlsx` em memória, uma vez por disparo, e anexa a cada e-mail (`fileAttachment`
  do Graph, < 3 MB). **Nada é gravado:** nem S3 nem banco; o registro do envio guarda só nome e tamanho.
  Os dados viajam em JSON na mensagem da task (broker SQS, `src/config/__init__.py:496`; teto da
  mensagem de 256 KiB a 1 MiB conforme a fila), então há limite de linhas configurável e 413 acima
  dele. Biblioteca de Excel nova na shared (Python 3.12; hoje não tem nenhuma).
- **Detalhes e alternativas:** `~/repos/.artemis_v2/agentes/ts13-anexo-shared/proposta.md` (a parte
  de S3 dessa proposta foi descartada pela decisão de não salvar).
- **Genérico:** qualquer serviço usa; nada de liquidação na shared.
- **Dependências:** nenhuma; pode começar já. Bloqueia o resumo com Excel (4.8).

### 4.8 Resumo diário com Excel e aviso de horário — TS-5585 (prazo 27/11, platform-cessao)

- **O que muda:** um job do scheduler (módulo `liquidacao`) monta o resumo **do dia** e envia por
  e-mail pela shared:
  - **Excel (decisões de 07 e 08/11):** os lotes daquele dia, em todos os status. Aba "Resumo": uma
    linha por fundo, produto, data e status, com quantidade de lotes, de pagamentos e valor. Aba
    "Lotes" (proposta): uma linha por lote com identificador, fundo, produto, data, status, motivo da
    conciliação, pagamentos e valor.
  - **Corpo do e-mail:** os totais. Proposta da D29: também o total da fila manual de qualquer data,
    para o lote parado não sumir do aviso no dia seguinte. Proposta: lote vazio aparece como alerta
    (detecta mão no banco).
- **Como:** consulta na réplica por intervalo UTC do dia (`[dia 03:00, dia+1 03:00)`), com o fundo
  pela parcela (`contrato_parcela.fundo_id`, indexado, dois saltos a partir do pagamento) e o valor
  em `liquidacao_pagamento.valor_pago` [C]; sem tocar em `liquidacao_processo`. A cessão **não gera
  Excel**: manda abas, colunas e linhas no `POST /email-dispatches` e a shared monta o arquivo (4.7).
  Cliente genérico da shared na cessão, URL base no Parameter Store; template cadastrado na shared;
  destinatários (D27) em tabela genérica de configuração; `idempotency_key`
  `cessao:resumo-liquidacao:<data>`; job só na tabela do scheduler, nunca no beat. Detalhes:
  `~/repos/.artemis_v2/agentes/ts13-resumo-diario/proposta.md`.
- **Mesmo cliente** serve o aviso da opção C (4.6).
- **Antes de ligar:** TS-5582 (sem lotes vazios), D27, D29. **Depende de:** TS-5569 e 4.7.

### 4.9 Aprovação antes do corte — TS-5571 (prazo 27/11)

- **O que muda:** o "aprovar" passa a aceitar lote em `aguarda_conciliacao` (hoje só
  `conciliacao_manual`, `cessao/api/liquidacao/service.py:383-384`), com transição nova para
  `pendente`, reaproveitando `aprovar_revisao_conta` (`service.py:461`): log com autor e observação,
  compromisso de saldo sob a trava da conta e envio para a esteira. Lote depois do corte continua na
  fila manual.
- **Avaliar:** a aprovação antecipada passa na frente da prioridade "parciais primeiro".
- **Dependências:** nenhuma das outras; separada do fechamento automático.

### 4.10 `POST /liquidacao/` no fechamento novo — TS-5568 (prazo 18/11, fora do caminho crítico)

- **O que muda:** com a varredura desativada, o handler legado (`cessao/api/liquidacao/viewer.py:418`,
  `create_by_originador` + `_enviar_para_esteira`) sai e a rota chama o fluxo novo; corpo com os
  campos de hoje (produto, originador, fundo, origem) ou o `proc_id`; resposta 202 com o job e status
  pela rota de status. Manter o 400 síncrono "nenhum pagamento apto para liquidar" e o 429. A tela
  passa a usar a rota; o `/fake-batches/consolidate` do BFF (sem uso) sai.
- **Antes:** identificar no Datadog os dois pods com python-requests (52 chamadas em 14 dias,
  provavelmente Atlas/fetch-api) e o acesso pelo navegador (20), e migrá-los.
- **Dependências:** TS-5570 (varredura desativada) e TS-5567.

### 4.11 Automático em tempo de execução no fluxo novo — TS-5572 (prazo 04/12)

- **O que muda:** o gatilho `automatico` (hoje `lote_automatico`, `models.py:5663`, portão no Redis
  por `proc_id` e backstop) migra para o fluxo novo, com a mesma chave, trava e D9. Parceiro que manda
  pagamento a pagamento vai para `agendado`; "fim da remessa" fica para quem manda a remessa inteira.
- **Evidência nova (B26):** com fechamento na chegada e parceiro pagamento a pagamento, nasce um lote
  por pagamento (1901 e Voltis em setembro).
- **Problemas conhecidos a resolver:** B19 (remessa não fecha quando o último pagamento é rejeitado),
  `POST /liquidacao/manual` sem registro de total, seleção final sem D9.
- **Antes:** levantar os 11 produtos automáticos (9 por chave, 2 por remessa) e o padrão de envio.

### 4.12 Proposta para o ETL da carteira (`platform-etl-credit-portfolio`)

- **Efeito da TS-5567 [C, `origin/master` bddbc2f]:** a consulta `pagamento()`
  (`portfolio/dwcaptalys/query.py:316-334`) faz `inner join` em `liquidacao_lote_processo`. Com o
  acúmulo padrão, o pagamento sem lote às 00h20 (cópia do DMS seguida do ETL) deixa de aparecer como
  pendente: os do fim de semana e feriado só entram depois do fechamento do dia útil seguinte. Já
  acontece hoje nos produtos sem acúmulo (15 e 581). As consultas de PDD (`left join`) não mudam.
- **Proposta:** `left join` no lote e, no filtro incremental, o pagamento sem lote pela própria
  `data_atualizacao`. Pergunta ao dev: a carga atualiza a linha quando ela volta com a data de
  liquidação?
- **Dono:** o dev que cuida do ETL (o time de dados cuida só do lake). Mensagem pronta (E1).

### 4.13 Itens de apoio

- **TS-5565 (13/11):** sessão de passagem com o Rafael; agenda real dos jobs (tabela
  `pldr_mv.mv_schedule_reports` no Redshift), credenciais fora da conta pessoal, alertas para uma
  caixa do time, exceções. Confirma os horários padrão do Mercato Libero.
- **TS-5566 (13/11):** documentação do fechamento em `docs/liquidacao/` da cessão.
- **TS-5573 (13/11):** vigentes abertos com lote já enviado (B25); pré-requisito do 1109 e 1373.
- **Área administrativa (fim da tarefa 13):** tela para alterar horários de corte e mais, depois da
  TS-5569.

## 5. Sequência e caminho crítico

**Caminho crítico:** TS-5567 (com as duas colunas) e TS-5569 em paralelo → TS-5570 → validação com a
varredura em auditoria → varredura desativada → VM desligada (quando a TS-5565 estiver resolvida).

| Fase | Até | O quê |
|---|---|---|
| 0 | 13/11 | TS-5565 (passagem; é o único prazo duro), TS-5566, TS-5573; enviar E1 (ETL) e E2 (B25, negócio); TS-5582 investigada (feito) e limpeza assim que a D26 sair; começar o anexo na shared (4.7), que não depende de nada |
| 1 | 18/11 | TS-5567 + duas colunas (migration, backfill, BFF/front); TS-5569 (aprovação da arquitetura primeiro) |
| 2 | 20/11 | TS-5570: Mercato Libero (depois da drenagem) e Voltis; auditoria pela varredura; desligar a varredura |
| 3 | 27/11 | resumo diário com Excel e aviso da opção C (depois de TS-5582, D27, D29); TS-5571 |
| 4 | 04/12 | TS-5568, TS-5572; área administrativa |

## 6. Pendências e antes de quê cada uma precisa estar resolvida

| Pendência | Dono | Precisa estar resolvida antes de |
|---|---|---|
| D26: destino do lote vazio (`descartado` ou excluir) | Pietro | rodar a limpeza da TS-5582 |
| D27: destinatários (grupo do Entra ID ou e-mails) | Pietro | ligar os e-mails (4.6, 4.8) |
| D28: horários definitivos por produto | Pietro com o negócio | nada: os padrões entram primeiro |
| D29: total da fila manual de qualquer data no e-mail | Pietro | ligar o resumo diário |
| B25 (E2): pagamentos em lotes já enviados no 1109/1373 | negócio | TS-5567 no 1109 e no 1373 (não bloqueia o Mercato Libero) |
| ETL (E1): `left join` e atualização da linha | dev do ETL | ideal antes da TS-5567 no Mercato Libero; não bloqueia (impacto pequeno e já existente nos produtos sem acúmulo) |
| Time de dados (lake) | — | nenhuma pergunta: só aviso do impacto |
| Agenda real da varredura (Redshift) | Rafael | 13/11 (confirma os padrões do Mercato Libero) |
| Dia útil e disparo duplo no scheduler | Pietro | aprovação da arquitetura da TS-5569 |
| 10 contratos presos do 15 (TS-5537) | time | ligar a TS-5570 no produto 15 |
| 7 lotes do 1637 na fila manual | operação | encerrar a TS-5582 |

## 7. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| Rafael sai antes da passagem completa | agenda, credenciais (registro do usuário Windows) e exceções se perdem; a VM para se a conta for desativada | TS-5565 no começo da semana; conta de serviço; alertas para caixa do time |
| Trocar a modalidade antes de drenar os vigentes | lote vigente órfão, pagamento parado | ordem da 4.2 no mesmo deploy; checagem de vigentes abertos antes da troca |
| Grupo grande no fechamento das 16h (produto 80) | `statement_timeout` estoura, lote não fecha | medir o maior grupo; rodadas das 17h/18h/20h45 pegam o resto; blocos em tarefa própria (D20) |
| Fechamento da Voltis passa das 14h | lotes vão para a fila manual | horário padrão 13h30; aviso da opção C; aprovação antecipada (TS-5571) |
| Corte da rotina e do roteamento divergirem | lote roteado com o corte errado | um registro só na tabela (4.4) |
| Disparo duplo ou em feriado | fechamento repetido ou fora de hora | trava no banco; checagem de dia útil (decisão da TS-5569) |
| Correções direto no banco | estados inconsistentes, lotes vazios (B26) | guarda de lote vazio; área administrativa com log; resumo mostra vazios como alerta |
| Três fontes da regra durante a migração (coluna antiga, duas novas, flags) | dessincronia | gravação derivada num lugar só; remover a coluna antiga e as flags ao fim |
| Dados do Excel grandes demais para a mensagem da fila | disparo recusado | limite de linhas validado na shared (413); conferir o tamanho máximo da fila SQS |
| Pagamento pendente fora do lake no fim de semana | leitura da carteira atrasa um dia útil | proposta do ETL (4.12) |

## 8. Não confirmado

- A agenda real da varredura: os horários 16h, 17h, 18h e 20h45 vêm de um comentário no código do
  Rafael; a agenda real está no Redshift.
- O horário do 746 e do 1044 (sem lotes nos últimos 14 dias): ficam no padrão até a D28.
- Como os fechamentos de setembro aconteceram com a configuração atual em `manual`: inferido que as
  flags foram trocadas e destrocadas direto no banco (o `data_atualizacao` não mudou).
- Onde vive o código de anexo dos workflows da shared, para reaproveitar.
- O limite de ~3 MB do Graph para anexo no envio simples (de memória, não conferido na documentação).
- Tamanho máximo de mensagem configurado na fila SQS da shared (define o limite de linhas).
