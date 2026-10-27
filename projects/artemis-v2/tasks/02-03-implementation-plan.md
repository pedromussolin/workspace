# Plano de implementação: fase 2 do fechamento novo (03) e fechamento por proc_id (02)

> **Para agentes:** executar com superpowers:subagent-driven-development (um agente por
> repositório, revisão do orquestrador antes de juntar) ou superpowers:executing-plans. Passos em
> checkbox (`- [ ]`).

- **Data:** 27/10/2026. Status: **aguardando validação do Pietro**.
- **Código conferido:** `origin/master` de 27/10:
  - cessão `b15aa94`;
  - BFF `bb877db`;
  - front `f7bb2d84`;
  - argocd `1bb76de`.

  As linhas citadas valem para esses commits.
- **Objetivo:** o plano tem três partes:
  - fechar a fase 2 do fechamento novo (o que o usuário vê);
  - levar a linha `proc:` da tela e o automático por proc_id para o mesmo fechamento;
  - deixar a fase 3 mapeada para quando a D18 e a D20 saírem.
- **Arquitetura:**
  - o fechamento por proc_id vira uma função de repositório em `refact.py`, usada pela rota
    nova (tela) e pelo portão do automático;
  - gera um lote por (proc_id, fundo, originador), com a guarda `liquidacao_lote_id IS NULL`;
  - front e BFF passam a mandar toda linha pela rota assíncrona.
- **Stack:**
  - cessão: Flask, SQLAlchemy, Celery, Redis e Postgres;
  - BFF: FastAPI;
  - front: Angular, com testes em Karma/Jasmine.
- **Spec:** fases 2 e 3 de [03-post-production-cases.md](03-post-production-cases.md),
  [02-close-batch-by-proc-id.md](02-close-batch-by-proc-id.md) e
  [decisions.md](../decisions.md).

## Decisões para responder antes de começar

| # | Pergunta | Recomendação | Por quê |
|---|---|---|---|
| IDs | TS da fase 2 e da tarefa 02 | fase 2 segue na TS-5377, como a fase 1; a 02 ganha TS nova | a fase 2 fecha casos da TS-5377 |
| D22 | Originador no modo por proc_id | (a) um lote por (proc_id, fundo, originador) | cabeçalho do CNAB da Genius sai do 1º pagamento (abaixo); o 1637 tem remessas com 2 originadores |
| D23 | Fechar pela tela uma remessa ainda em processamento | recusar, com 400 e motivo claro | senão a remessa vira lotes picados: a tela fecha o que terminou e o portão fecha o resto depois |
| D7 | Acúmulo com fechamento por proc_id | (a) recusar na config do produto | nenhum produto tem os dois ligados hoje |
| D19 | Fechar a linha leva os pendentes de todas as datas | (a) manter e avisar, mostrando a contagem | já recomendada em 20/10 |
| D18, D20 | Registro durável e grupo grande | só para a fase 3 | a D20 depende da SQL dos grupos |

**D22, detalhe:**
- O "exatamente o proc_id" continua valendo: o lote não leva pagamento de outra remessa e não
  deixa pagamento da remessa de fora. A remessa só se divide onde o arquivo da ADM obriga.
- O CNAB 500 da Genius tem um cabeçalho por arquivo, e o cabeçalho tira o código do originador e
  o nome do cedente do primeiro pagamento do lote
  (`cessao/geradores/cnab_500_liquidacao_genius.py:341-349`) **[C]**.
- Mudar o gerador (opção b) acabaria em um arquivo por originador do mesmo jeito.
- Os geradores de outras quatro ADMs também assumem um originador por lote **[C]**.
- A origem não divide: o gerador da Genius não a usa **[C]**, e nenhuma remessa misturou origens
  em 7 dias.

## Dados de 27/10/2026

Réplica, somente leitura, com a SQL em
[attachments/sql/proc_id_batches_profile.sql](../attachments/sql/proc_id_batches_profile.sql). **[C]**

**Quais produtos fecham por proc_id:**
- só dois, o 1505 e o 1637, ambos da Genius (CNAB);
- os dois têm lote automático e liquidação automática;
- nenhum acumula;
- `baixa_por_agendamento` vazio ou falso, então o backstop do agendado não roda para eles.

**Lotes reais de 21 a 27/10 (7 dias):**

| Produto | Lotes | Remessas | Pagamentos | Maior lote | Remessas em 2+ lotes |
|---|---|---|---|---|---|
| 1505 | 30 | 28 | 35.893 | 7.085 | 0 (mais 2 lotes sem pagamento, B21) |
| 1637 | 18 | 13 | 13.533 | 5.109 | 5, todas por originador (2 originadores, 1 fundo, 1 origem) |

**Revisão da premissa da tarefa 02:**
- Os 88 h em 7 dias do `_processos_agrupados_por_proc_id` foram medidos em 05/10.
- Essa consulta pesa no **modo por chave** (`_fechar_lote_legado`, `models.py:5529-5546`).
- O hotfix de 06/10 (`56abdbfe7`) pôs o `_existe_processo_nao_terminal` antes dela.
- No modo por proc_id ela só roda depois do claim.
- **[H]** O ganho de banco da 02 é pequeno; o ganho é de regra (fechamento manual e B19). A
  fase 0 mede de novo.

## Regras gerais

- **git, nos repos da empresa:**
  - antes de criar a branch: `git pull`;
  - criar com `git switch -c <branch> --no-track origin/master`;
  - a branch `-sdbx` recebe só merge da original;
  - commits atômicos em PT-BR, até 72 caracteres, sem coautoria;
  - **commit só depois da revisão do Pietro**;
  - fluxo de deploy: tarefa → `release/<data>` → master (o merge é do Pietro).
- **Idioma e logs:**
  - código e nome de teste em inglês;
  - log da cessão em PT-BR, do BFF e do front em inglês;
  - log como evento: mensagem fixa e dimensões no `extra`;
  - nomes com o processo (`fake_batch_closing`, `proc_id_closing`).
- **Migration:** nunca alterar uma existente.
- **Imports em `models.py`:** o import de `refact` em `cessao/database/models.py` é local
  (dentro da função), como o `lote_controle` já é, porque há import circular no módulo.
- **Validação local antes do ambiente:**
  - suíte da cessão na imagem do devcontainer;
  - SQL e concorrência no estresse local (`~/repos/.artemis_v2/estresse`, Postgres e Redis
    reais);
  - sandbox só no fim.
- **Varredura do Mercato Libero:** não toca o 1505 nem o 1637, nem a rota nova. Nada a combinar
  com o Rafael Frankl nos blocos 1 e 2. Na fase 3, C1 e C2 mexem no vigente de produtos da
  varredura (4, 80, 81 e 1406 acumulam): combinar antes.

## Pontos de revisão

Casos que nenhum fluxo da tela exercita sozinho. Cada um ganhou teste na tarefa dona.

1. Remessa do 1637 com dois originadores fechada pela tela: vira dois lotes, um por
   originador, e não pega nada de outra remessa (B1).
2. Tela e portão fechando a mesma remessa ao mesmo tempo: nenhum pagamento em dois lotes e
   nenhum lote vazio (B1, estresse).
3. Último processo da remessa termina rejeitado: o lote fecha sozinho (B2).
4. Remessa com mais de 24 h, sem registro no Redis: a tela fecha; o automático só alerta (B1
   e B2).
5. Status falhando, ou a chave sumindo do status: "Fechando…" não fica para sempre, aparece um
   aviso e a lista recarrega (A3).

## Ordem e execução

| Bloco | Tarefa | Repo | Branch | Depende de | Agente |
|---|---|---|---|---|---|
| 0 | Medir de novo no Datadog | — | — | — | orquestrador |
| 1 | A1: pedido sem pagamento, contagem e vigente com limite | cessão | `fix/TS-5377-fechamento-lote-fase2` | — | sonnet, high |
| 1 | A2: contagem no status e escopo na exclusão | BFF | idem | — | haiku, medium |
| 1 | A3: estado do fechamento confiável | front | idem | contrato da A2 | sonnet, high |
| 2 | B1: linha `proc:` no fluxo novo, D7 e log do legado | cessão | `feature/TS-XXXX-fechamento-por-proc-id` | A1 | sonnet, high |
| 2 | B2: automático por proc_id e B19 | cessão | idem | B1 | sonnet, high |
| 2 | B3: chave `proc:` na rota nova | BFF | idem | contrato da B1 | haiku, medium |
| 2 | B4: toda linha pela rota assíncrona | front | idem | A3, B3 | sonnet, medium |
| 3 | C1 a C6 | cessão, argocd | TS a definir | D18, D20 | definir |

- **Bloco 1:** três agentes em paralelo, em repos disjuntos.
- **Bloco 2:**
  - B1 e B3 rodam em paralelo; a B2 vem depois da B1 (mesmo repo, usa a função dela), e a B4
    por último;
  - a branch da 02 nasce da branch da fase 2, porque mexe nos mesmos arquivos (`refact.py`,
    `close-batches.ts`);
  - se a fase 2 chegar à master antes, entra um merge da master na 02.
- **Revisão:**
  - por tarefa, pelo orquestrador: suíte, lint e diff;
  - no fim do bloco 2, uma revisão final com Opus, porque a mudança cruza três repos e mexe em
    concorrência.

## Fase 0: medir antes (sem deploy)

- [ ] Datadog, 7 dias, `service:platform-cessao`, spans `postgres`. Medir execuções, tempo total
  e p95 de duas consultas:
  - `resource_hash:23ea4ea711b38532` (`_processos_agrupados_por_proc_id`);
  - o COUNT do portão (`models.py:5567-5572`).

  Registrar em `evidence/`.
- [ ] Logs `event=lote_ctrl_sem_registro` e `event=backstop_sem_registro` do 1505 e do 1637, em
  7 dias.

## Bloco 1: fase 2 do fechamento novo (TS-5377)

### A1. Cessão: pedido sem pagamento, contagem no resultado e vigente com limite

**Arquivos:**
- Modificar em `cessao/api/liquidacao/refact.py`:
  - `:489-520` (pedido);
  - `:361-392` (resultado);
  - `:587-646` (execução);
  - `:395-440` (status);
  - `:682-700` (vigente).
- Testes:
  - `test/api/liquidacao/test_refact_liquidacao.py`;
  - `test/api/liquidacao/test_viewer_fake_batch_closing.py`.

**Interfaces que produz:**
- `RefactLiquidacaoRepository.has_fake_batch_payments(key: FakeBatchKey) -> bool`.
- Resultado e status ganham `payments_count: int | None`. Fica `None` enquanto o status é
  `closing` e em resultado gravado antes da mudança.
- `RefactLiquidacaoRepository.close_open_vigentes(key: FakeBatchKey) -> list[int]`: devolve os
  ids dos vigentes que **esta** transação fechou.

**Passos:**
- [ ] **R7, teste:** `test_request_fake_batch_closing_without_eligible_payments_is_refused`.
  - Com `has_fake_batch_payments` falso, levanta `ParametrosInvalidos` com
    `FAKE_BATCH_NOTHING_TO_CLOSE_REASON`.
  - Não chama nem o `acquire` da trava nem o `apply_async`.
  - Na rota, devolve 400 com esse motivo.
- [ ] **R7, implementação:** `exists()` sobre o `fake_batch_payments_query(key)`, entre a
  recusa de modo (`:498`) e o `acquire`.
- [ ] **R26, testes:**
  - `test_run_fake_batch_closing_saves_payments_count`: o resultado `closed` traz
    `payments_count` igual ao rowcount;
  - `test_fake_batch_closing_status_exposes_payments_count`;
  - resultado sem o campo devolve `None`.
- [ ] **R26, implementação:** o campo entra no JSON do resultado (`:373`), na execução (`:587`,
  `:594`, `:644-646`) e no status (`:410`, `:424`).
- [ ] **R29 (achado em 27/10), teste:**
  `test_close_fake_batch_closes_vigentes_with_single_guarded_update`. Usar o SQL compilado com
  `_CapturingSession`, como em `:139`.
  - O WHERE tem `fechado = false` e há `RETURNING`.
  - O vigente que outro processo já fechou não é despachado.
  - Nenhum commit entre o `SET LOCAL` e o fim do fechamento.
- [ ] **R29, implementação:**
  - Hoje o fluxo novo fecha os vigentes por `get_lote_vigente_and_fecha_lote`, com um commit
    por lote (`service.py:1174-1184`). Do segundo lote em diante, a transação perde o
    `statement_timeout` e o `lock_timeout`.
  - Trocar por um UPDATE único dentro da transação que já tem
    `limit_fake_batch_closing_db_time` (`refact.py:293-301`), e despachar só os ids devolvidos.
  - O legado (`service.py`) não muda aqui: fica para a C2.
- [ ] **Suíte da cessão no Docker:** `python -m pytest -q test/api/liquidacao test/tasks`, depois
  a suíte inteira (~30 s). Tudo passa.
- [ ] **Estresse local:**
  - dois fechamentos simultâneos da mesma chave com vigente: um lote, despachado uma vez;
  - medir a espera por trava. **[H]** Os 44 s de 21/10 vêm do `lock_timeout` valer por espera
    (uma espera por linha), não por transação.
- [ ] **Mostrar o diff ao Pietro.** Depois da revisão, commits:
  - `fix(TS-5377): recusa fechamento de lote fake sem pagamento apto`
  - `feat(TS-5377): grava a quantidade de pagamentos no resultado`
  - `fix(TS-5377): fecha vigentes numa transação só, com limite`

### A2. BFF: contagem no status e escopo na exclusão

**Arquivos:**
- Modificar em `src/modules/operations/liquidation_batches/`:
  - `schemas.py:308-345`;
  - `viewer.py:258-300`.
- Testes, em `tests/unit/modules/operations/liquidation_batches/`:
  - `test_viewer_close.py`;
  - `test_business_consolidate.py`.

**Interfaces que produz:** `CloseStatusRecord.payments_count: Optional[int]`.

**Passos:**
- [ ] Teste `test_close_status_forwards_payments_count`.
- [ ] Teste `test_delete_batch_outside_partner_products_returns_403`. Achado de 27/10: o
  `DELETE /batches` checa só o papel, não os produtos do parceiro. A cessão não pode ser
  chamada.
- [ ] Implementação:
  - o campo opcional no schema;
  - `await scope.ensure_assignment_product(product_id)` no `delete_batch`, como já faz o
    `consolidate_fake_batch` (`viewer.py:323-325`).
- [ ] Validar:
  - `pytest -q tests/unit/modules/operations/liquidation_batches tests/unit/shared/business`;
  - `ruff check`.
- [ ] Commits, depois da revisão:
  - `feat(TS-5377): repassa a quantidade de pagamentos do fechamento`
  - `fix(TS-5377): exclusão de lote fake respeita os produtos do parceiro`

### A3. Front: estado do fechamento confiável

**Arquivos:**
- Modificar em `src/app/features/liquidation-batches/`:
  - `close-batches/close-batches.ts`, `.html` e `.spec.ts`;
  - `data-access/liquidation-batches/liquidation-batches.interface.ts:86-92`.

**Interfaces que consome:** `payments_count` (A2).

**Constantes:**
- `STATUS_RETRY_DELAYS_MS = [4000, 8000, 16000, 32000, 60000]`
- `STATUS_FAILURES_BEFORE_WARNING = 3`
- `CLOSING_SLOW_AFTER_MS = 15 * 60 * 1000`

**Passos.** Em cada um: spec falhando, implementação, spec passando. As descrições do `it(...)`
ficam em PT-BR, como pede o `.ai/rules/testing.md`.
- [ ] **R11:** "desabilita Excluir enquanto a linha fecha". O `[disabled]` do Excluir
  (`close-batches.html:115`) e o `deleteActionLabel` (`.ts:233`) passam a considerar
  `isClosing(row)`.
- [ ] **R24:** "recarrega a lista quando o status traz `closed` de uma linha visível".
  - Deixa de depender da transição local `closing→closed` (`applyCloseStates`, `.ts:507-536`).
  - Vale também para o `closed` da primeira carga.
  - O Fechar fica desabilitado até a recarga.
- [ ] **R8:** "avisa e recarrega quando a chave some do status". Hoje o `states.delete(key)`
  acontece sem aviso (`.ts:523-527`).
- [ ] **R25:** "espaça as consultas de status que falham e avisa depois de três".
  - Espera crescente pelos `STATUS_RETRY_DELAYS_MS`, com um aviso só.
  - Volta a 4 s no primeiro sucesso.
  - Mostra "demorando, confira depois" quando o `closing` passa de `CLOSING_SLOW_AFTER_MS`.
- [ ] **R27/R26:** "mostra quantos pagamentos e quais lotes fecharam".
  - O toast de sucesso traz `payments_count` e `batches`.
  - Um `failed` com `batches` preenchido diz que fechou os lotes X e falhou depois.
  - A confirmação mostra o `records_count` e avisa que fecha os pendentes de todas as datas da
    linha (D19 (a)).
- [ ] **502/504 no fechamento:** "confere o status depois de 502 ou 504". Em vez de mostrar erro
  (`.ts:450-458`), chama `refreshCloseStates()` e mostra "não deu para confirmar; conferindo".
- [ ] Validar:
  - `ws slot -- npm test -- --watch=false --include='src/app/features/liquidation-batches/**'`;
  - `npm run lint`;
  - `ws slot -- npm run build`.
- [ ] Commits, depois da revisão, um por item acima, no padrão `fix(TS-5377): …`.

O R7 na listagem (linha que aparece fechável e não fecha) fica com a tarefa 04, junto com a
DBA, porque muda a consulta da listagem.

## Bloco 2: fechamento por proc_id (tarefa 02)

### B1. Cessão: linha `proc:` no fluxo novo, D7 e log do legado

**Arquivos:**
- Modificar em `cessao/api/liquidacao/refact.py`:
  - `:51` (prefixo);
  - `:188-225` (`FakeBatchKey`);
  - `:249-276` (consulta);
  - `:304-330` (pedido no Redis);
  - `:395-440` (status);
  - `:489-520` (pedido);
  - `:665-743` (`_close_fake_batch`).
- Modificar também:
  - `cessao/api/liquidacao/schema.py:145-160` (descrição e exemplo da chave);
  - `cessao/api/liquidacao/viewer.py:349-398` (log no `POST /liquidacao/`);
  - para a D7: `cessao/api/produto/sevice.py:37-44` e `cessao/api/cadastro/service.py:105`.
- Testes:
  - `test_refact_liquidacao.py`, inclusive o `:461`, que hoje espera a recusa;
  - `test_viewer_fake_batch_closing.py`;
  - `test_viewer_liquidacao.py`;
  - os testes de produto e de cadastro.

**Interfaces que produz:**
- `FAKE_BATCH_PROC_KEY_PREFIX = "proc:"`. O `FakeBatchKey.parse` devolve, para `proc:`, a chave
  com `proc_id` e `is_proc_id = True`, sem os campos de origem.
- `RefactLiquidacaoRepository.proc_id_closing_groups(proc_id: str, product_id: int) -> list[tuple[int | None, int]]`:
  - devolve os pares (fundo_id, originador_id) distintos dos pagamentos aptos da remessa;
  - a regra de apto é a da D9, a mesma do `fake_batch_payments_query`, trocando originador,
    origem e fundo por `ProcessoLiquidacao.proc_id`.
- `RefactLiquidacaoRepository.assign_proc_id_payments_to_new_batches(proc_id: str, product: Produto) -> list[LiquidacaoLoteProcesso]`:
  - para cada par, cria o lote e roda o UPDATE com `proc_id`, fundo, originador e
    `liquidacao_lote_id IS NULL`;
  - lote com rowcount 0 é descartado;
  - faz flush e **não** commita. Quem chama é que commita, limpa o cache do lote fake (como
    `create_by_originador`, `models.py:6115-6119`) e despacha a esteira. A B2 usa esta função.
- O pedido e o status no Redis ganham `product_id`, para o BFF filtrar (B3).
- Motivos novos, ambos 400:
  - `FAKE_BATCH_REMITTANCE_IN_PROGRESS_REASON` (D23);
  - `FAKE_BATCH_KEY_MODE_MISMATCH_MESSAGE`.

**Passos:**
- [ ] **Testes da chave:**
  - `test_fake_batch_key_parses_proc_id_key`;
  - `test_fake_batch_key_rejects_empty_proc_id`.
- [ ] **Testes do pedido:**
  - `test_request_proc_key_for_key_mode_product_is_refused` (400);
  - `test_request_origin_key_for_proc_id_product_is_refused` (400);
  - `test_request_proc_key_of_other_product_is_refused` (400: o proc_id não tem processo do
    produto);
  - `test_request_proc_key_with_remittance_in_progress_is_refused` (400: há processo fora de
    `cadastrado`, `rejeitado` e `errado`);
  - `test_request_proc_key_enqueues_closing` (substitui o `:461`).
- [ ] **Testes do repositório:**
  - `test_proc_id_closing_creates_one_batch_per_fund_and_originator`: 2 pares viram 2 lotes, e
    o UPDATE compilado filtra proc_id, fundo, originador e `liquidacao_lote_id IS NULL`;
  - `test_proc_id_closing_discards_batch_with_no_rows`;
  - `test_proc_id_closing_does_not_filter_origin`.
- [ ] **Teste do status:** `test_fake_batch_closing_status_includes_product_id`.
- [ ] Rodar e confirmar que falham.
- [ ] **Implementação:** no `_close_fake_batch`, o ramo `proc:` chama
  `assign_proc_id_payments_to_new_batches`. Não há ramo de vigente: a D7 garante que produto por
  proc_id não acumula.
- [ ] **D7:**
  - testes `test_update_produto_config_rejects_accumulation_with_proc_id_closing` e o
    equivalente no cadastro;
  - ambos esperam 400 "acumula_liquidacoes não combina com fechar_lote_por_proc_id";
  - depois, a implementação.
- [ ] **Legado:**
  - teste `test_post_liquidacao_for_proc_id_product_logs_key_closing`;
  - log INFO "Fechamento por chave em produto que fecha por proc_id", com `produto_id`,
    `originador_id`, `fundo_id` e `origem` no `extra`;
  - o comportamento não muda (o Atlas segue chamando sem proc_id);
  - depois, a implementação.
- [ ] **Suíte da cessão no Docker.**
- [ ] **Estresse local.** Massa: uma remessa com 2 originadores e outra remessa com a mesma
  chave.
  - A tela fecha a primeira em 2 lotes e não toca a segunda.
  - Tela e portão na mesma remessa ao mesmo tempo: nenhum pagamento em dois lotes e nenhum lote
    vazio.
- [ ] Commits, depois da revisão:
  - `feat(TS-XXXX): fecha lote fake por proc_id na rota nova`
  - `feat(TS-XXXX): recusa acúmulo em produto que fecha por proc_id`
  - `feat(TS-XXXX): loga fechamento por chave em produto por proc_id`

### B2. Cessão: automático por proc_id e B19

**Arquivos:**
- Modificar em `cessao/database/models.py`:
  - `:5549-5588` (portão);
  - `:5591-5640` (backstop);
  - `:5437-5447` (`_materializar_lotes_por_proc_id`, que sai).
- Modificar também:
  - `cessao/framework/liquidacao/estados_liquidacao.py` (`EstadoRejeitado`, `EstadoErrado` e
    `:342-358`);
  - `cessao/tasks/liquidacao_lote.py:222-300` (filtro do agendado).
- Testes:
  - `test/database/test_models.py:458-540`;
  - `test/framework/liquidacao/test_estados_liquidacao.py:140-160`;
  - `test/tasks/test_liquidacao_lote.py:258-340`.

**Interfaces que consome:** `assign_proc_id_payments_to_new_batches` (B1), importada dentro da
função.

**Passos:**
- [ ] **Teste do portão:** `test_gate_closes_with_proc_id_closing_function`. O vencedor do claim
  chama `assign_proc_id_payments_to_new_batches(proc_id, produto)` e não chama
  `_processos_agrupados_por_proc_id`.
- [ ] **Testes do B19:**
  - `test_rejected_last_process_triggers_gate_for_proc_id_product`;
  - o mesmo para `errado`;
  - `test_rejected_does_not_trigger_gate_for_key_mode_product` (o modo por chave não muda).
- [ ] **Testes do backstop:**
  - `test_backstop_processing_closes_when_all_terminal`;
  - `test_backstop_closing_rematerializes`;
  - `test_backstop_runs_for_proc_id_products_without_schedule`;
  - sem registro no Redis, só alerta, e a mensagem aponta o fechamento pela tela.
- [ ] Rodar e confirmar que falham.
- [ ] **Implementação:**
  - **portão e backstop:**
    - chamam a função da B1;
    - no backstop, o "há processo fora dos terminais" passa a usar o
      `_existe_processo_nao_terminal` (`models.py:5508`);
    - `_materializar_lotes_por_proc_id` sai;
    - `_processos_agrupados_por_proc_id` fica, porque o modo por chave usa;
  - **rejeitado e errado:**
    - `EstadoRejeitado` e `EstadoErrado` chamam `fechar_lote` só quando
      `fechar_lote_por_proc_id` está ligado;
    - a chamada vem depois do commit da transição, como no `EstadoCadastrado`, que roda depois
      do commit do `EstadoSalvo` (`:322-329`);
    - a esteira segue como hoje (`enviar_para_baixa`);
  - **filtro do agendado:**
    - passa a ser `baixa_por_agendamento OR fechar_lote_por_proc_id`
      (`liquidacao_lote.py:~240`);
    - o ramo do vigente não pega esses produtos, por causa da D7.
- [ ] **Suíte da cessão no Docker.**
- [ ] **Estresse local:**
  - remessa cujo último processo é rejeitado fecha sozinha;
  - remessa com 2 originadores fecha em 2 lotes pelo portão.
- [ ] Commits, depois da revisão:
  - `refact(TS-XXXX): portão por proc_id usa o fechamento novo`
  - `fix(TS-XXXX): remessa por proc_id fecha quando o último é rejeitado`
  - `fix(TS-XXXX): agendado cobre todo produto que fecha por proc_id`

O COUNT do portão roda a cada pagamento (`models.py:5567-5572`) e continua.
- **[C]** Sem corrida: a contagem roda depois do commit da transição, e sob READ COMMITTED a
  última contagem vê todos os commits.
- Só vira contador no Redis se a fase 0 mostrar custo.

### B3. BFF: chave `proc:` na rota nova

**Arquivos:**
- Modificar em `src/modules/operations/liquidation_batches/`:
  - `business.py:352-405` e `:510-529`;
  - `schemas.py:308-345`.
- Testes: `test_business_close.py` e `test_viewer_close.py`.

**Interfaces que consome:** o contrato da B1:
- status com `product_id`;
- motivos 400.

**Passos:**
- [ ] **Testes:**
  - `test_close_fake_batch_accepts_proc_key_for_allowed_product`: repassa a chave e o produto
    do corpo; o escopo já é checado na rota (`viewer.py:365`);
  - `test_close_status_keeps_proc_keys_and_filters_by_returned_product`: a chave `proc:` vai à
    cessão, e registro de produto fora do escopo não volta.
- [ ] **Implementação:**
  - `_product_from_key` (`:513-529`) segue só para `origem:`;
  - `close_fake_batch` pula a comparação de produto para `proc:`;
  - `get_close_status` manda as chaves `proc:` e filtra a resposta pelo `product_id` do
    registro.
- [ ] Commit, depois da revisão: `feat(TS-XXXX): fecha lote fake por proc_id na rota nova`.

### B4. Front: toda linha pela rota assíncrona

**Arquivos:**
- Modificar `close-batches.ts`: `:75`, `:410-464` e `:489`.
- Modificar o `.html` e o `.spec.ts` do componente.
- Modificar `data-access/liquidation-batches/batches.service.ts:55-73` (o consolidate sai).

**Passos:**
- [ ] **Specs:**
  - "fecha linha por remessa pela rota nova": chave `proc:` vai para o `closeAsync`, sem
    consolidate;
  - "a confirmação da linha por remessa diz que fecha a remessa inteira": título com o proc_id
    e o texto "um lote por fundo e originador";
  - "remessa em processamento mostra o motivo": 400 vira toast, sem marcar `closing`;
  - "consulta o status das linhas por remessa": `refreshCloseStates` inclui `proc:`.
- [ ] **Implementação:**
  - `closesAsync` aceita `origem:` e `proc:`;
  - saem o `consolidateByProcess` e o `consolidate` do service;
  - a rota de consolidate do BFF fica até o Datadog mostrar 7 dias sem chamada.
- [ ] Validar: testes, lint e build, como na A3.
- [ ] Commits, depois da revisão.

## Bloco 3: fase 3 (antes de virar o caminho padrão)

Plano detalhado depois da D18 e da D20. O que já está mapeado:

- **C1, B14:**
  - `insert_pagamento_into_lote` (`repository.py:460-475`) vira UPDATE com
    `liquidacao_lote_id IS NULL` e confere o rowcount;
  - o vigente passa a ser lido com `FOR UPDATE` (`:429-457`);
  - combinar com o Rafael Frankl.
- **C2, B15:**
  - o fechamento do vigente no legado (`service.py:1165-1184`) e no agendado
    (`liquidacao_lote.py:~250-262`) usa o mesmo UPDATE da A1;
  - trava por lote no início da `esteira_baixar` (`liquidacao_lote.py:82-104`).
- **C3, B16:** a exclusão (`tasks/liquidacao.py:137-155`) trava os pagamentos com `FOR UPDATE`.
  Pagamento que já tem lote não é apagado: o código loga e pula.
- **C4, D18:**
  - tabela de pedidos de fechamento, em migration nova;
  - job que reenvia lote `pendente` parado sem esteira há N minutos (o que sobra do R9).
- **C5, D20:**
  - UPDATE em blocos, se a medição pedir;
  - antes, rodar na réplica as consultas 1 e 2 de
    [new_closing_pending_groups.sql](../attachments/sql/new_closing_pending_groups.sql).
- **C6, worker:**
  - **R3:** `exec` no `celery_worker()` do `entrypoint.sh`. Afeta todos os workers, então vai
    numa PR própria;
  - **argocd** (`apps/platform-cessao/asgard-production/values.yaml:246-296`):
    - `terminationGracePeriodSeconds` acima do `time_limit` (600 s);
    - duas réplicas;
    - probes que testam o Celery (`celery inspect ping` do próprio nó) no lugar de `test date`.

## Fora do escopo, registrado

- [B20](../bugs-found.md): rotas do BFF sem o escopo do parceiro:
  - pagamentos, exportações, CNAB, saldo, extrato e conciliação.
  - É tarefa própria, de segurança. Recomendação: logo depois do bloco 1.
- [B21](../bugs-found.md): lotes reais sem pagamento no 1505.
- R7 na listagem: tarefa 04.
