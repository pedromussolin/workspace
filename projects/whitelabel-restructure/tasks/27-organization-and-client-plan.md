# Organização e cliente da pessoa — plano de implementação

> **Para os agentes:** use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** o controle de acesso mostra e muda a organização e o cliente de cada pessoa (atributos
do usuário no Azure), e o BFF ganha o bloqueio de quem não tem escopo de parceiro, desligado.

**Arquitetura:** o BFF lê os dois atributos de extensão pelo Graph (nomes por variável) junto com os
dados que já lê das pessoas, calcula a situação do escopo de cada uma com uma função pura e grava
pela operação nova `set_person_scope` do `batch/preview` e `batch/apply`. O front estende a aba
Pessoas, o modal da pessoa e o Em lote, usando o diálogo de mudança direta da 26.

**Stack:** BFF FastAPI 0.117 / Pydantic 2.12 / pytest; front Angular 20 (signals, OnPush),
Karma/Jasmine, `shared/ui`.

**Spec:** [27-organization-and-client.md](27-organization-and-client.md) (D64–D68). Leia antes.

## Restrições globais

- Worktrees, com `--no-track`, saídas da 26:
  - BFF: `~/repos/apl-credit-whitelabel-api-wt/27`, branch `feature/TS-5407-organizacao-e-cliente`
    (da `0446d9b`); venv `~/.venvs/whitelabel-api`;
  - front: `~/repos/apl-credit-whitelabel-wt/27`, mesma branch (da `6303b2e5`); `node_modules` é
    link para o da 25.
- **Sem commit pelos agentes.** Relatório com arquivos e a mensagem sugerida `tipo(TS-5407): …`
  (PT-BR, até 72 caracteres, sem `Co-Authored-By`).
- **BFF sem banco de dados** (D63): cache só no `AccessControlCache` (Redis, 5 min).
- Nomes de empresa e de parceiro neste repo são mascarados; no código, use os que já existem (o
  `OrgType` do BFF e os nomes das marcas em `core/theme/themes.ts` do front).
- Textos fixos (PT-BR, exatos):
  - bloqueio (403): "Seu usuário não tem um cliente associado. Fale com o administrador do portal."
  - log (WARNING, evento): "Usuário sem escopo de parceiro", `extra={"organization", "reason"}`;
  - motivos da prévia: "Os atributos de organização e cliente não estão configurados no BFF.",
    "Só quem é da organização interna pode mudar a organização e o cliente.", "A organização interna
    não tem cliente.", "Organização de parceiro precisa de um cliente.", "Cliente {id} não existe no
    product-manager.", "Já está com essa organização e esse cliente.";
  - tela: KPI "Sem organização ou cliente"; visão do modal "Organização"; aviso do diálogo "Vale a
    partir do próximo login da pessoa."; aviso em vermelho para a interna "A organização interna vê
    os dados de todos os clientes."; só leitura sem ser da interna: "Só quem é da organização interna
    muda a organização e o cliente.".

## Foco da revisão

1. **Atributos sem nome configurado:** nenhuma chamada ao Graph com nome vazio no `$select`; a tela
   diz "não configurado" e a escrita fica bloqueada com o motivo.
2. **Pessoa sem o atributo no Azure:** o Graph simplesmente não devolve a chave; vira `None`, conta
   como sem escopo, nada quebra.
3. **Cliente gravado como texto** (vazio, com espaço, não numérico): situação `invalid-client`, no
   escopo e no bloqueio.
4. **Quem aplica sem organização** (`None`): não é a interna; a prévia bloqueia.
5. **Lote grande** (500 `set_person_scope`): a lista de clientes e as pessoas vêm uma vez só no
   `_prefetch`, não uma por operação.

---

### B1: atributos no Graph e na configuração (BFF)

**Arquivos:**
- Modificar: `src/config/__init__.py` (`AccessControlSettings`), `src/services/azure/graph.py`,
  `src/modules/access_control/schemas.py` (`DirectoryUser`), `src/modules/access_control/repository.py`
- Testes: `tests/unit/services/fake_graph.py`, `tests/unit/modules/access_control/test_partner_attributes.py`

**Interfaces:**
- Produz: `AccessControlSettings.organization_attribute: str = ""`, `client_attribute: str = ""`,
  `require_partner_scope: bool = False` (envs `CFG_ACCESS_CONTROL_ORGANIZATION_ATTRIBUTE`,
  `CFG_ACCESS_CONTROL_CLIENT_ATTRIBUTE`, `CFG_ACCESS_CONTROL_REQUIRE_PARTNER_SCOPE`).
- Produz: `PartnerAttributes(organization: str, client: str)` (dataclass congelada) e
  `partner_attributes(settings) -> PartnerAttributes | None` (`None` se algum nome estiver vazio).
- Produz no Graph: `get_user`, `list_group_members` e `search_users` aceitam
  `extra_fields: Sequence[str] = ()` (somados ao `USER_FIELDS` no `$select`);
  `update_user(user_id: str, fields: dict[str, str | None]) -> bool` (`PATCH users/{id}`, `False` se
  404).
- Produz: `DirectoryUser.organization: str | None = None` e `client_id: str | None = None` (cru,
  como veio), preenchidos pelo repositório quando há `PartnerAttributes`.

- [ ] Teste: sem os nomes, `partner_attributes` é `None` e o `$select` dos membros é só o
  `USER_FIELDS`; com os nomes, o `$select` leva os dois e a pessoa vem com `organization` e
  `client_id`; pessoa sem as chaves vem com os dois `None`.
- [ ] Teste: `update_user` manda `PATCH users/{id}` com o corpo exato e devolve `False` no 404.
- [ ] Implementar e rodar `pytest tests/unit/modules/access_control tests/unit/services -q`.

### B2: organização e cliente nas leituras (BFF)

**Arquivos:**
- Criar: `src/modules/access_control/business/scope.py`
- Modificar: `schemas.py`, `business/__init__.py`, `repository.py`, `viewer.py`
- Testes: `test_scope.py`, `test_people_routes.py`, `test_read_routes.py`, `test_clients_routes.py`

**Interfaces:**
- Produz: `ScopeState = Literal["ok", "no-organization", "no-client", "invalid-client"]` e
  `scope_state(organization: str | None, client_id: str | None, client_ids: set[int]) -> ScopeState`:
  sem organização → `no-organization`; interna → `ok` (o cliente é ignorado); parceiro sem cliente →
  `no-client`; cliente não numérico ou fora de `client_ids` → `invalid-client`; senão `ok`.
- Produz: `ClientOption(id: int, name: str)` (de `list_clients`: `id` e `social_name`; o documento
  não sai) e `ClientsResponse(clients)`; rota `GET access-control/clients` (Reader), com cache.
- Produz: `PersonSummary` ganha `organization`, `client_id: int | None`, `client_name`,
  `scope_state: ScopeState | None` (`None` sem atributos configurados); `PeopleStatus` ganha
  `"without-scope"` (situação diferente de `ok`); `PersonDetailResponse` ganha
  `scope: PersonScope | None` (`organization`, `client_id`, `client_name`, `state`).
- Produz em `AccessControlSettingsResponse`: `partner_attributes: Literal["not-configured", "ok"]`,
  `can_edit_partner: bool` (`can_write` e quem pede é da interna) e
  `organizations: list[OrganizationOption(value, label)]`, um por valor do `OrgType`, com o nome da
  marca correspondente e "Cliente" para o `client`.

- [ ] Testes de `scope_state` (os quatro estados, a interna com cliente, cliente "", " 12 ", "abc").
- [ ] Testes de rota: `people` com os campos e o filtro `without-scope`; detalhe com `scope`;
  `clients` com cache (segunda leitura não chama o product-manager); `settings` com os três campos
  novos, com e sem configuração, com quem pede interno e parceiro.
- [ ] Implementar e rodar os testes do módulo.

### B3: operação `set_person_scope` (BFF)

**Arquivos:**
- Modificar: `schemas.py`, `business/batch.py`, `business/__init__.py`, `viewer.py`
- Testes: `test_batch_scope.py`, `test_batch_routes.py`

**Interfaces:**
- Consome: B1 (`update_user`, `PartnerAttributes`), B2 (`ClientOption`).
- Produz: `SetPersonScopeOperation(type="set_person_scope", user: UserRef, organization: str,
  client_id: int | None)` no `Operation`; `PlanAction.UPDATE = "update"`.
- Produz: `preview_batch(request, user)` e `AccessControlBatch(..., actor: User, partner:
  PartnerAttributes | None, clients: Callable[[], Awaitable[list[ClientOption]]])`.

- [ ] Testes da prévia, um por motivo fixo (sem atributos, quem pede não é interno ou sem
  organização, pessoa inexistente, interna com cliente, parceiro sem cliente, cliente inexistente,
  sem mudança → `skip`) e o caso feliz (`update`, rótulo com a pessoa, a organização e o nome do
  cliente).
- [ ] Teste do apply: `PATCH` com os dois atributos (cliente como texto; interna grava cliente
  `None`), invalida o cache; falha do Graph vira `failed` só daquela linha.
- [ ] Teste: 500 operações chamam `list_clients` uma vez.
- [ ] Implementar e rodar os testes do módulo.

### B4: bloqueio de quem não tem escopo (BFF)

**Arquivos:**
- Modificar: `src/shared/business/users.py` (dependência `get_partner_internal_id_list`)
- Testes: `tests/unit/shared/business/test_partner_scope.py`

**Interfaces:**
- Produz: `partner_scope_reason(user: User, internal_ids: list[int]) -> str | None`: `None` para a
  interna ou com ids; senão `no-organization`, `no-client`, `invalid-client` ou `no-products`.

- [ ] Testes: variável desligada → comportamento de hoje nos quatro casos; ligada → interna passa,
  parceiro com ids passa, os outros recebem 403 com o texto fixo e o WARNING com `reason`.
- [ ] Implementar e rodar `pytest tests/unit -q` (só as 8 falhas antigas de `cerc_reconciliation`);
  `ruff check` e `black --check` nos arquivos mexidos.

### F1: contrato no front

**Arquivos:**
- Modificar: `features/access-control/data-access/access-control.dto.ts`,
  `access-control.service.ts`, `testing/access-control.testing.spec.ts`, `access-control.store.ts`
- Testes: os specs desses arquivos

**Interfaces:**
- Produz: os tipos de B2 e B3 em TypeScript (`AccessControlScopeState`, `AccessControlClient`,
  `AccessControlSetPersonScopeOperation`, `'update'` em `AccessControlPlanAction`, `'without-scope'`
  em `AccessControlPeopleStatus`), `listClients()` no serviço, `store.clients` (carregado na primeira
  vez que alguém pede) e `store.partnerSettings` (de `settings`).
- Produz em `models/access-change.ts`: `setPersonScopeOperation(personId, organization, clientId)` e
  os avisos novos em `accessChangeNotices`.

- [ ] Testes do serviço, do store e dos avisos; implementar.

### F2: aba Pessoas e modal da pessoa

**Arquivos:**
- Modificar: `components/people-tab/*`, `components/person-detail/*` (inclusive a view)

- [ ] Testes: colunas "Organização" (pílula) e "Cliente" (nome; número no tooltip); KPI "Sem
  organização ou cliente" filtra pelo `without-scope`; "não configurado" com o aviso; pílula ao lado
  do nome no modal; visão "Organização" com select e cliente buscado pelo nome; salvar abre o diálogo
  `typed` com o nome da pessoa, o aviso do próximo login e, para a interna, o aviso em vermelho; só
  leitura com o motivo (sem write, não interna, não configurado); cliente com `invalid-client`
  aparece como "cliente desconhecido"; lista de clientes com erro mostra o erro, desliga o salvar e
  o cliente atual aparece só com o número.
- [ ] Implementar com peças de `shared/ui`; rodar os specs da feature.

### F3: Em lote

**Arquivos:**
- Modificar: `models/batch-draft.ts`, `components/batch-builder/*`, `components/batch-preview/*`

- [ ] Testes: tipo novo "Organização e cliente" no construtor (pessoas, organização, cliente);
  linhas no lote; a prévia mostra a ação `update` com rótulo, tom e ícone próprios.
- [ ] Implementar; rodar os specs da feature.

### F4: smoke e `.ai`

**Arquivos:** `.ai/scripts/smoke-data/access-control.json`, `.ai/context/bff.md`

- [ ] Dados fictícios com organização e cliente (gente sem escopo também), `clients` e `settings`;
  o `bff.md` cita os campos e a rota novos.

## Commits (plano para revisão)

**BFF:** `feat(TS-5407): atributos de organização e cliente no Graph` (B1);
`feat(TS-5407): organização e cliente nas pessoas e lista de clientes` (B2);
`feat(TS-5407): mudar organização e cliente pela prévia e apply` (B3);
`fix(TS-5407): barra quem não tem escopo de parceiro, desligado` (B4).

**Front:** `feat(TS-5407): contrato de organização e cliente no front` (F1);
`feat(TS-5407): organização e cliente na aba Pessoas e no modal` (F2);
`feat(TS-5407): organização e cliente no Em lote` (F3);
`chore(TS-5407): .ai e smoke com organização e cliente` (F4).

Commit que não compilar ou não passar nos testes sozinho junta com o seguinte.
