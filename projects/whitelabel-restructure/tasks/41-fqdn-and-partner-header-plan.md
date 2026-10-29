# Serviços internos pelo FQDN e cabeçalho do parceiro — plano de implementação

> **Para os agentes:** use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** a cessão passa a respeitar o `X-Identificador-Interno` nas 18 rotas que o BFF chama, e o BFF passa a
mandar esse cabeçalho em toda chamada a serviço interno e a chamar esses serviços pelo nome interno do cluster.

**Arquitetura:** na cessão, um módulo único decide o escopo do parceiro a partir do cabeçalho e cada rota só aplica o
próprio recorte; um modo por configuração (`observar` ou `aplicar`) deixa medir antes de mudar resposta. No BFF, o
middleware de sessão guarda num `ContextVar` os `internal_id` do parceiro da sessão, e um transporte do `httpx`,
instalado só nos clientes de serviço interno, põe o cabeçalho. A troca para o FQDN é só configuração.

**Stack:** cessão Flask-RESTX, SQLAlchemy, Python 3.8, pytest na imagem do devcontainer; BFF FastAPI, httpx, pytest.

**Spec:** [41-fqdn-and-partner-header.md](41-fqdn-and-partner-header.md) (D138). Leia antes. O levantamento de 20/10
(pasta privada, `agentes/seguranca/cessao-padrao.md`, seção 4.2) tem o recorte de cada rota.

## Restrições globais

- Duas partes que sobem separadas: A (cessão) e B (BFF), cada uma com o seu card. Os cards são criados antes de
  começar, com prévia; o ID entra no nome da branch e nos commits.
- Worktrees saídas de `origin/master` com `--no-track`: cessão em `~/repos/platform-cessao-wt/41`, branch
  `feature/TS-<id>-escopo-do-parceiro`; BFF em `~/repos/apl-credit-whitelabel-api-wt/41`, branch
  `feature/TS-<id>-cabecalho-do-parceiro`.
- **Sem commit pelos agentes.** O relatório traz arquivos, testes e a mensagem sugerida `tipo(TS-id): …` (PT-BR, até
  72 caracteres, sem `Co-Authored-By`). O Pietro revisa antes dos commits.
- **Cessão em Python 3.8:** nada de `set[int]`, `list[str]` ou `X | None` em anotação avaliada em tempo de execução;
  use `typing` ou `from __future__ import annotations`. Testes: comando da nota "Testes da cessão no Docker" (imagem
  do devcontainer, westworld da versão do `requirements.txt`).
- **Logs:** mensagem fixa e as dimensões no `extra`. Na cessão em PT-BR, no BFF em inglês. Nunca o `internal_id`, o
  token ou o e-mail no log.
- **Textos fixos da cessão (respostas):**
  - cabeçalho inválido (item que não é UUID ou que não existe em `produto_acesso`): 403 "Identificador do parceiro
    inválido.";
  - produto pedido fora do escopo: 403 "Produto fora do escopo do parceiro.";
  - saldo e extrato da conciliação com escopo: 403 "Consulta indisponível para parceiro.";
  - item fora do escopo: 404 com o mesmo corpo que a rota já devolve para "não encontrado".
- **Log da cessão:** um INFO por chamada com escopo avaliado, "Escopo de parceiro avaliado", `extra` com `rota`,
  `tem_cabecalho`, `org_type`, `qtd_produtos` e `decisao` (`sem_escopo`, `filtraria`, `403` ou `404`).
- **Configuração da cessão:** `CESSAO_ESCOPO_PARCEIRO` = `observar` (padrão, também para valor desconhecido, com um
  WARNING) ou `aplicar`; `CESSAO_ESCOPO_PARCEIRO_SO_OBSERVAR` = lista de ids de rota separados por vírgula que ficam em
  `observar` mesmo com `aplicar` (para `GET /titulo/contratos` e `POST /liquidacao/` até a validação com o time).
- **Textos fixos do BFF:** parceiro sem produto numa chamada interna: 403 com o `NO_PARTNER_SCOPE_MESSAGE` que já
  existe (`src/shared/business/partner_scope.py:28`); produtos do parceiro indisponíveis (Redis ou product-manager
  fora): 503 "Não foi possível conferir os produtos do seu usuário agora. Tente novamente em instantes.", com
  `Retry-After: 1`.
- A defesa em profundidade do spec já está na `master` do BFF: para parceiro, o `partner_id` de `/titulo/contratos`
  precisa ser um dos produtos dele (`src/modules/operations/assignment_batches/viewer.py:131` e o mesmo na
  liquidação), e os produtos do fundo saem só os do parceiro (`PartnerScope.own_cessao_funds`). Nada a fazer além de
  manter os testes passando.
- A TS-5435 (Artemis) mexe em `cessao/api/liquidacao/viewer.py`, e a TS-5458 mexe em `tests/test_arch.py` do BFF:
  antes de abrir as PRs, merge da `master` atualizada e conferência dos conflitos.

## Foco da revisão

1. Cabeçalho com espaço, maiúscula ou item repetido (`"A1…, a1…"`): o escopo é o mesmo de um item só, sem 403. Teste
   na A1.
2. "Ver como" um parceiro, feito por alguém da organização interna: as chamadas internas levam os produtos do
   parceiro visto, não nada. Teste na B3.
3. Duas requisições ao mesmo tempo no mesmo processo, uma interna e uma de parceiro: o cabeçalho de uma não vaza para
   a outra. Teste na B1.
4. Exclusão de pagamentos com itens misturados (alguns do parceiro, outros não): 404 e nada vai para a fila. Teste na
   A4.
5. Product-manager fora do ar numa sessão de parceiro: 503, nunca a chamada interna sem cabeçalho (que veria tudo).
   Teste na B3.

---

## Parte A — cessão (`platform-cessao`)

### Tarefa A1: módulo do escopo do parceiro

**Arquivos:**
- Criar: `cessao/escopo_parceiro.py`
- Teste: `test/test_escopo_parceiro.py`

**Interfaces:**
- Consome: o modelo `Acesso` (`cessao/database/models.py:929`, tabela `produto_acesso`: `uuid` e `produto_id`), o
  `request` do Flask.
- Produz, para as tarefas A2 a A4:
  - `ROTA_*`: constantes de texto com o id de cada uma das 18 rotas (por exemplo `ROTA_TITULO_CONTRATOS =
    "titulo_contratos"`, `ROTA_LIQUIDACAO_CONSOLIDAR = "liquidacao_consolidar"`); os ids entram no log e na
    `CESSAO_ESCOPO_PARCEIRO_SO_OBSERVAR`;
  - `escopo_do_parceiro() -> Optional[FrozenSet[int]]`: `None` sem cabeçalho ou com `X-Org-Type: plgn`; senão o
    conjunto de `produto_id`;
  - `produtos_da_listagem(rota: str, pedidos: Optional[Sequence[int]]) -> Optional[List[int]]`: o que a listagem deve
    usar como filtro de produto;
  - `garantir_produto(rota: str, produto_id: int) -> None`: 403 se o produto pedido estiver fora;
  - `garantir_item(rota: str, produto_id_do_item: int, nao_encontrado: Callable[[], NoReturn]) -> None`: chama
    `nao_encontrado()` (o 404 da rota) se o item estiver fora;
  - `negar_para_parceiro(rota: str) -> None`: 403 com o texto de saldo e extrato quando houver escopo.
- Em `observar`, as quatro funções de rota só registram a decisão e devolvem como se não houvesse escopo; em
  `aplicar`, registram e aplicam. Uma rota em `CESSAO_ESCOPO_PARCEIRO_SO_OBSERVAR` fica em `observar`.

- [ ] **Passo 1: testes que falham**, com um `produto_acesso` de teste para dois produtos:
  - `test_sem_cabecalho_nao_tem_escopo` e `test_org_type_plgn_nao_tem_escopo` (também com valor que não é UUID);
  - `test_um_identificador_vira_um_produto`, `test_lista_vira_os_dois_produtos`;
  - `test_espaco_maiuscula_e_repetido_viram_o_mesmo_escopo` (Foco 1);
  - `test_identificador_inexistente_responde_403`, `test_valor_que_nao_e_uuid_responde_403`,
    `test_lista_com_um_item_invalido_responde_403`, todos com "Identificador do parceiro inválido.";
  - `test_listagem_sem_pedido_usa_o_escopo_inteiro`, `test_listagem_com_pedido_dentro_mantem_o_pedido`,
    `test_listagem_com_pedido_fora_responde_403`;
  - `test_item_fora_chama_o_nao_encontrado_da_rota`;
  - `test_observar_nao_muda_a_resposta_e_registra_a_decisao` (confere o INFO e o `extra`, sem `internal_id`);
  - `test_rota_so_observar_nao_aplica_com_modo_aplicar`; `test_modo_desconhecido_vira_observar_com_aviso`.
- [ ] **Passo 2:** rodar `python -m pytest -q test/test_escopo_parceiro.py` (comando da nota) e ver falhar por falta do
  módulo.
- [ ] **Passo 3:** implementar o módulo com as assinaturas acima. O `Acesso` vem numa consulta só (`uuid IN (...)`),
  depois de validar cada item como UUID.
- [ ] **Passo 4:** rodar de novo e ver passar.
- [ ] **Passo 5:** relatório com a mensagem `feat(TS-<id>): escopo do parceiro pelo X-Identificador-Interno`.

### Tarefa A2: contratos, cessão e fundos

**Arquivos:**
- Modificar: `cessao/api/titulo/viewer.py:253` (`GET /titulo/contratos`), `cessao/api/cessao/viewers/cessao.py:306`
  (`GET /cessao/query`) e `:589` (`GET /cessao/contratos/query`), `cessao/api/fundo/viewer.py:51`
  (`GET /fundo/produtos`)
- Teste: os arquivos de `test/api/titulo/`, `test/api/cessao/` e `test/api/fundo/` dessas rotas

**Interfaces:**
- Consome: A1.

- [ ] **Passo 1: testes que falham**, quatro casos por rota (sem cabeçalho igual a hoje; com escopo filtrado; produto
  de fora 403; item de fora 404), e mais:
  - `/titulo/contratos`: com escopo, o cabeçalho vence o `identificador_parceiro`; `identificador_parceiro` de outro
    produto responde 403; com dois produtos e sem `produto_id` nem `identificador_parceiro`, 400 pedindo `produto_id`;
  - `/cessao/contratos/query`: `proc_id` de outro produto devolve página vazia (é listagem, não 404);
  - `/fundo/produtos`: `identificador_parceiro` fora da lista do cabeçalho responde 403; os `produtos` de cada fundo
    só trazem os do escopo.
- [ ] **Passo 2:** rodar os testes dessas rotas e ver falhar.
- [ ] **Passo 3:** chamar A1 em cada rota com a constante `ROTA_*` dela, antes da consulta.
- [ ] **Passo 4:** rodar os testes dessas rotas e a suíte inteira; os testes que já existiam passam sem mudar.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): escopo do parceiro em contratos, cessão e fundos`.

### Tarefa A3: listagens da liquidação

**Arquivos:**
- Modificar: `cessao/api/liquidacao/viewer.py:990` (lotes fake), `:1029` (lotes reais), `:1147` (pagamentos),
  `:1199` (rejeitados)
- Teste: `test/api/liquidacao/test_viewer_liquidacao.py`

**Interfaces:**
- Consome: A1.

- [ ] **Passo 1: testes que falham**, os quatro casos por rota, e mais: nos lotes, `produto_id[]` fora do escopo
  responde 403 e, sem pedido, vale o escopo; em pagamentos, `proc_id`, `chave` (produto da chave) e `lote_id` de outro
  produto respondem 404 e o filtro de produto entra também na consulta; em rejeitados, qualquer `proc_id` de fora
  responde 404.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** aplicar A1 em cada rota; o produto de `proc_id`, `lote_id` e chave vem do mesmo modelo que a rota já
  consulta.
- [ ] **Passo 4:** rodar o arquivo e a suíte inteira.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): escopo do parceiro nas listagens da liquidação`.

### Tarefa A4: ações e escritas da liquidação

**Arquivos:**
- Modificar: `cessao/api/liquidacao/viewer.py:349` (consolidar), `:957` (fechar lote fake), `:979` (status do
  fechamento), `:828` (excluir pagamentos), `:465` (CNAB), `:501` (reenviar), `:750` e `:766` (aprovar e rejeitar
  conciliação), `:689` e `:704` (saldo e extrato)
- Teste: `test/api/liquidacao/test_viewer_liquidacao.py`

**Interfaces:**
- Consome: A1.

- [ ] **Passo 1: testes que falham**, os quatro casos por rota, e mais:
  - consolidar e fechar lote fake: produto do corpo fora do escopo responde 403 antes do `max_calls` e de qualquer
    escrita;
  - status do fechamento: chave de outro produto some da resposta, sem 404;
  - excluir pagamentos: produto fora 403; `liquidacao_id`, `proc_id` ou `pagamentos` de outro produto, mesmo
    misturados com itens do parceiro, respondem 404 e nada vai para a fila (Foco 4); sem cabeçalho, o autor gravado é
    o `Acesso` do produto (como `cessao/tasks/liquidacao.py:133`) e nunca o `Authorization`;
  - CNAB, reenviar, aprovar e rejeitar: item de outro produto responde 404 antes de assinar a URL ou de mexer no lote;
  - saldo e extrato: com escopo, 403 "Consulta indisponível para parceiro."; sem cabeçalho, igual a hoje.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** aplicar A1 em cada rota e trocar, na exclusão de pagamentos, a origem do autor.
- [ ] **Passo 4:** rodar o arquivo e a suíte inteira.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): escopo do parceiro nas ações da liquidação` e
  `fix(TS-<id>): autor da exclusão de pagamentos sem o Authorization`.

---

## Parte B — BFF (`apl-credit-whitelabel-api`)

### Tarefa B1: transporte que põe o cabeçalho

**Arquivos:**
- Criar: `src/shared/utils/partner_header.py`
- Modificar: `src/shared/utils/http_observability.py:103` (`create_outbound_client`),
  `src/shared/business/partner_scope.py:26` (passa a importar `PARTNER_HEADER` do módulo novo e o reexporta)
- Teste: `tests/unit/shared/utils/test_partner_header.py`

**Interfaces:**
- Produz:
  - `PARTNER_HEADER = "X-Identificador-Interno"`;
  - `PARTNER_SCOPE_UNRESOLVED`: sentinela de "parceiro sem produto";
  - `bind_partner_internal_ids(value: tuple[str, ...] | None | object) -> Token` e
    `reset_partner_internal_ids(binding: Token) -> None`, sobre um `ContextVar` com padrão `None`;
  - `class PartnerScopeUnavailable(RuntimeError)` e `class PartnerHeaderMismatch(RuntimeError)`;
  - `class PartnerHeaderTransport(httpx.AsyncBaseTransport)`, que embrulha outro transporte;
  - `create_outbound_client(..., internal_service: bool = False)`: com `True`, o transporte é
    `PartnerHeaderTransport(ObservedTransport(...))`.
- Regras do transporte: com `None`, a requisição passa intacta; com a tupla, põe o cabeçalho com os ids separados por
  vírgula, a não ser que a requisição já traga o cabeçalho só com ids da tupla (estreitamento, comparação sem caixa),
  que é mantido; cabeçalho com id de fora levanta `PartnerHeaderMismatch`; com a sentinela, levanta
  `PartnerScopeUnavailable` sem chamar o transporte de dentro.

- [ ] **Passo 1: testes que falham:** `test_partner_session_gets_all_internal_ids_in_the_header`,
  `test_internal_session_sends_no_header`, `test_narrowed_header_inside_the_scope_is_kept`,
  `test_header_outside_the_scope_raises`, `test_unresolved_partner_raises_without_calling_the_service`,
  `test_concurrent_tasks_keep_their_own_partner_header` (Foco 3),
  `test_outbound_client_without_internal_service_never_adds_the_header`.
- [ ] **Passo 2:** `pytest -q tests/unit/shared/utils/test_partner_header.py` e ver falhar.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar o arquivo e a suíte inteira.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): transporte com o X-Identificador-Interno`.

### Tarefa B2: os clientes internos usam o transporte

**Arquivos:**
- Modificar: as chamadas a `create_outbound_client` em `src/services/{ai_service,data_lake_api,orchestrator,
  platform_cessao,product_manager,shared_service,tse}/__init__.py` e em `src/shared/utils/http_client.py` (base do
  `user_service`), todas com `internal_service=True`
- Teste: `tests/test_arch.py`

**Interfaces:**
- Consome: `create_outbound_client(..., internal_service=True)` da B1.

- [ ] **Passo 1: teste que falha:** `test_internal_service_clients_send_the_partner_header`, que lê os
  `src/services/*/__init__.py` e o `http_client.py`: nos oito serviços internos toda chamada a
  `create_outbound_client` tem `internal_service=True`; em `azure`, `bluedeck`, `cerc_api` e `zitadel`, nunca; serviço
  novo em `src/services/` sem estar numa das duas listas faz o teste falhar.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** passar `internal_service=True` nos oito; a Formalização continua mandando o cabeçalho estreitado
  (`get_partner_headers`), que o transporte mantém.
- [ ] **Passo 4:** rodar `tests/test_arch.py`, os testes de `tests/unit/services/` e a suíte inteira.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): cabeçalho do parceiro em todo serviço interno`.

### Tarefa B3: a sessão diz quem é o parceiro

**Arquivos:**
- Modificar: o middleware de sessão em `src/shared/business/users.py:368` (onde `request.state.user` é definido) e
  `src/infra/fastapi/exceptions_handlers.py:236` (`add_exception_handlers`)
- Teste: um arquivo novo `tests/unit/shared/business/test_session_partner_header.py`

**Interfaces:**
- Consome: B1 (`bind_partner_internal_ids`, `reset_partner_internal_ids`, `PARTNER_SCOPE_UNRESOLVED`,
  `PartnerScopeUnavailable`) e `UserRepository.get_partner_internal_id_list(user)` (Redis por 5 min,
  `src/shared/repository/users.py:33`).
- Regras: depois de definir `request.state.user` (que já é a pessoa vista no "ver como"), a sessão interna liga
  `None`; a de parceiro busca os ids e liga a tupla; lista vazia liga a sentinela; erro na busca responde 503 com o
  texto fixo, antes da rota. O vínculo é desfeito no fim da requisição (`finally`). `PartnerScopeUnavailable` vira 403
  com o `NO_PARTNER_SCOPE_MESSAGE`.

- [ ] **Passo 1: testes que falham:** `test_partner_session_calls_internal_services_with_its_products`,
  `test_internal_session_calls_internal_services_without_header`,
  `test_view_as_partner_sends_the_viewed_partner_products` (Foco 2), `test_partner_without_product_gets_403_on_internal_call`,
  `test_product_lookup_failure_returns_503_and_calls_nothing` (Foco 5),
  `test_binding_is_reset_after_the_request`.
- [ ] **Passo 2:** rodar e ver falhar.
- [ ] **Passo 3:** implementar no middleware e registrar o handler.
- [ ] **Passo 4:** rodar o arquivo e a suíte inteira, com ruff e black.
- [ ] **Passo 5:** relatório com `feat(TS-<id>): sessão vincula os produtos do parceiro às chamadas`.

---

## Parte C — implantação (sem código; com o Pietro)

### Tarefa C1: cessão em `observar` e BFF com o cabeçalho

- [ ] A cessão sobe com `CESSAO_ESCOPO_PARCEIRO` ausente (vale `observar`). No Datadog, o INFO "Escopo de parceiro
  avaliado" aparece nas 18 rotas; enquanto o BFF passa pelo gateway, as chamadas dele trazem o cabeçalho do produto da
  conta de serviço (a decisão sai `filtraria`): é a prova do que o gateway faz hoje.
- [ ] O BFF sobe com B1 a B3. Nada muda nas respostas: pelo gateway, o Heimdall sobrescreve o cabeçalho.

### Tarefa C2: troca para o FQDN, um serviço por vez

- [ ] Para cada serviço interno, na sandbox e depois em produção: trocar a URL no Parameter Store (`ps.sh`) pelo nome
  interno (lista e sufixos no relatório de 28/10 da pasta privada, `agentes/fqdn-revisao/relatorio.md`; confirmar a
  pergunta 6 da infra antes), reiniciar o BFF e conferir no Datadog o `peer.hostname` novo, os 4xx, os 5xx e a
  latência. Volta: restaurar a URL.
- [ ] Na sandbox, o data lake fica no endereço público ou passa para o da sandbox, nunca o de staging pelo nome
  interno.
- [ ] Revisar os monitores e painéis do Datadog filtrados pelo host antigo.
- [ ] Depois da cessão: o log dela mostra cabeçalho só nas chamadas de parceiro (sessão interna sai `sem_escopo`).

### Tarefa C3: cessão em `aplicar`

- [ ] Uma semana de log sem `403` ou `404` para sessão interna, e o recorte da Dots igual aos dois produtos dela.
- [ ] `CESSAO_ESCOPO_PARCEIRO=aplicar` com `CESSAO_ESCOPO_PARCEIRO_SO_OBSERVAR=titulo_contratos,liquidacao_consolidar`,
  na sandbox, no staging e em produção, nessa ordem.
- [ ] As duas rotas saem da lista só depois da validação do Pietro com o time (spec, "Para validar com o time").
