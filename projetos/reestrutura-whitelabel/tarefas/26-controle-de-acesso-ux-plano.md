# Controle de acesso: organização e UX/UI — plano de implementação

> **Para os agentes:** use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** deixar as abas de `/access-control` no padrão lista + modal de detalhe, com mudanças
diretas confirmadas num diálogo, Pessoas vindas do grupo dinâmico do Azure e "quem tem" cada
permissão.

**Arquitetura:** o BFF ganha um índice de acesso puro (quem tem o quê, direto e por grupo), montado
sobre o que já lê do Graph, com cache no Redis existente (5 min, geração apagada a cada `apply`). O
front troca o lote como caminho de toda escrita por um diálogo de mudança que usa o mesmo
`batch/preview` e `batch/apply`, e um modal de detalhe comum às três abas, aberto pela URL.

**Stack:** BFF FastAPI 0.117 / Pydantic 2.12 / pytest; front Angular 20 (signals, OnPush, CDK),
Karma/Jasmine, componentes de `shared/ui`.

**Spec:** [26-controle-de-acesso-ux.md](26-controle-de-acesso-ux.md) — leia antes; este plano não
repete o desenho.

## Restrições globais

- Repos e branches (D61–D63):
  - BFF: worktree `~/repos/apl-credit-whitelabel-api-wt/26`, branch
    `feature/TS-5405-controle-de-acesso-ux`, da `release/20261016` local, com `--no-track`;
  - front: worktree `~/repos/apl-credit-whitelabel-wt/26`, mesma branch, da
    `refact/TS-5395-refinamento-visual` (já com os commits da 25), com `--no-track`.
- **Sem commit pelos agentes:** cada tarefa termina com o relatório (arquivos e a mensagem sugerida
  `tipo(TS-5405): …`, PT-BR, até 72 caracteres, sem `Co-Authored-By`). Os commits saem depois da
  revisão do Pietro.
- **BFF sem banco de dados.** Cache só no Redis que já existe (`src/infra/redis`), com validade.
- Front: só `shared/ui`; peça nova em `shared/ui` passa pelo `main` antes. Tokens, OnPush, signals,
  `input()`/`model()`, sem `::ng-deep`. Código e comentário em inglês; texto de tela e descrição de
  teste em PT-BR.
- Padrões da 25: colunas no centro, ações `align="end"` com "Ver" por último e excluir isolado
  (`app-table__destructive-action`), `app-filter-bar`, `app-field-grid`, KPIs com
  `minItemWidth` 240, tabela de 10 por página, lista no modal de 5 (`NESTED_TABLE_PAGE_SIZE`).
- Valores fixos da spec: `CFG_ACCESS_CONTROL_PORTAL_USERS_GROUP_ID` (vazio por padrão); cache de
  300 s; status de pessoas `all` | `with-roles` | `without-roles`; aviso sem `write`: "Você pode
  consultar. Para alterar, é preciso a permissão `access-control:write`.".
- Máquina: comando pesado pelo `~/repos/.reestrutura_whitelabel/ng-slot.sh`; rascunho em
  `~/repos/.reestrutura_whitelabel/agentes/<pacote>/`; portas 4300 e 8765 são do Pietro.

## Foco da revisão

Entradas que a spec implica e que quebrariam a tela se ninguém testasse (cada uma tem o teste na
tarefa dona):

1. **Mesma permissão direta e por dois grupos:** conta uma vez em `roleCount` e `peopleCount`; em
   "quem tem", uma linha por pessoa com todas as origens. (B2, F6)
2. **Grupo dinâmico com mais de 999 membros:** o `nextLink` é seguido e ninguém some. (B3)
3. **Valor de permissão com `:` no caminho** (`roles/all-pre-trade:read/holders`): o front codifica e
   o BFF aceita. (B4, F1)
4. **Redis fora no meio:** ler cai no Graph; apagar a geração no `apply` falha sem derrubar o
   `apply`; WARNING registrado. (B1, B5)
5. **Busca sem acento e sem caixa:** "joao" acha "João Souza" e o e-mail. (B3)

---

## BFF

### Tarefa B1: configuração e cache do controle de acesso

**Arquivos:**
- Modificar: `src/config/__init__.py` (`AccessControlSettings`)
- Criar: `src/modules/access_control/cache.py`
- Teste: `tests/unit/modules/access_control/test_cache.py`

**Interfaces:**
- Produz:
  - `AccessControlSettings.portal_users_group_id: str = ""` e
    `AccessControlSettings.cache_ttl_seconds: int = 300`;
  - `class AccessControlCache(redis: RedisManager | None, ttl_seconds: int)` com
    `async def get_or_load(self, key: str, load: Callable[[], Awaitable[list[dict[str, Any]]]]) -> list[dict[str, Any]]`
    e `def invalidate(self) -> None`.
- Regra: chave real `access-control:{geração}:{key}`; a geração mora em
  `access-control:generation` (lida com `get`, trocada com `client.incr`); `invalidate` só incrementa
  (as chaves antigas expiram pelo TTL). Qualquer erro do Redis: carrega do Graph e registra um
  WARNING fixo "Cache do controle de acesso indisponível" com `extra={"operation": ...}`. Com
  `redis=None`, sempre carrega.

- [ ] **Passo 1: testes que falham** (`test_cache.py`, com um Redis falso em memória com
  `get`/`set`/`delete`/`client.incr`; procure um já existente em `tests/` antes de criar):
  - `test_segunda_leitura_vem_do_cache`: `load` chamado 1 vez em duas leituras da mesma chave;
  - `test_invalidar_faz_ler_de_novo`: depois de `invalidate()`, `load` chamado de novo;
  - `test_ttl_e_o_da_configuracao`: o `set` recebe `ex=300`;
  - `test_redis_fora_le_do_graph_e_avisa`: `get` levanta `ConnectionError` → devolve o `load` e há
    um WARNING com a mensagem fixa (`caplog`);
  - `test_invalidar_com_redis_fora_nao_levanta`;
  - `test_sem_redis_sempre_carrega`.
- [ ] **Passo 2:** `pytest tests/unit/modules/access_control/test_cache.py -q` → falha (módulo não
  existe).
- [ ] **Passo 3:** implementar `AccessControlCache` e os dois campos de configuração.
- [ ] **Passo 4:** os testes passam; `ruff check` e `black --check` nos arquivos.
- [ ] **Passo 5:** relatório (`feat(TS-5405): cache do controle de acesso no Redis`).

### Tarefa B2: índice de acesso (quem tem o quê)

**Arquivos:**
- Criar: `src/modules/access_control/business/access_index.py`
- Teste: `tests/unit/modules/access_control/test_access_index.py`

**Interfaces:**
- Consome: `AppRegistration`, `AssignmentRecord`, `DirectoryUser` (`schemas.py`).
- Produz (funções puras):
  - `build_access_index(registration: AppRegistration, assignments: list[AssignmentRecord], members_by_group: Mapping[str, list[DirectoryUser]], owned_group_ids: set[str]) -> AccessIndex`;
  - `AccessIndex` (dataclass congelada) com:
    - `roles_of(person_id: str, enabled_only: bool = True) -> set[str]` (direto + grupos de que é
      membro direto);
    - `groups_of(person_id: str) -> list[str]` (ids dos grupos do portal: com role do app ou do
      app, de que é membro direto);
    - `holders(role_value: str) -> list[RoleHolderRow]`, `RoleHolderRow(person: DirectoryUser, origins: list[HolderOrigin])`,
      `HolderOrigin(via: Literal["direct","group"], group_id: str | None, group_name: str | None, assignment_id: str)`;
    - `holder_groups(role_value: str) -> list[tuple[str, str, str]]` (group_id, nome, assignment_id);
    - `people_count(role_value: str) -> int` (pessoas distintas, direto ou por grupo; vale também
      para role desabilitada).

- [ ] **Passo 1: testes que falham:**
  - `test_mesma_role_direta_e_por_dois_grupos_conta_uma_vez`: `roles_of` tem 1 valor,
    `people_count` = 1, `holders` = 1 linha com 3 origens (Foco 1);
  - `test_role_desabilitada_fica_fora_de_roles_of_mas_aparece_em_holders`;
  - `test_grupo_aninhado_nao_conta` (só membro direto);
  - `test_groups_of_so_grupos_do_portal` (grupo sem role e sem dono fica fora);
  - `test_role_que_nao_existe_devolve_vazio`.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** passa; ruff/black.
- [ ] **Passo 5:** relatório (`feat(TS-5405): índice de quem tem cada permissão`).

### Tarefa B3: pessoas do grupo dinâmico, paginadas

**Arquivos:**
- Modificar: `src/modules/access_control/repository.py`, `business/__init__.py`, `schemas.py`,
  `viewer.py`
- Teste: `tests/unit/modules/access_control/test_people_routes.py`; ajustar `test_read_routes.py`
  (`test_busca_pessoas`) e `tests/unit/services/fake_graph.py` (grupo com `nextLink`)

**Interfaces:**
- Consome: B1 (`AccessControlCache`), B2 (`build_access_index`).
- Produz:
  - `AccessControlRepository(graph, cache: AccessControlCache | None = None)`;
    `list_assignments` e `list_group_members` passam pelo cache (chaves
    `assignments:{sp_id}` e `members:{group_id}`); novo
    `list_portal_users(group_id: str) -> list[DirectoryUser]` (membros, só contas habilitadas,
    cache `portal-users:{group_id}`);
  - `GET /people?search=&status=all|with-roles|without-roles&sort=name|-name|roles|-roles&page=1&perPage=10`
    (`perPage` de 1 a 100) → `PeoplePageResponse { people: PersonSummary[], total, page, perPage, source: "group" | "directory" }`,
    `PersonSummary = Person + roleCount + groupCount`;
  - `AccessControlSettingsResponse.portal_users_group: Literal["not-configured", "ok", "not-found"]`
    (o `get_settings` confere o grupo com `get_group`);
  - grupo configurado que não existe: `GET /people` responde 404 "O grupo de quem tem acesso ao
    portal não existe no Azure.";
  - sem o grupo: a busca no diretório de hoje (`search_users`), `source="directory"`, `page=1`,
    `total` = quantos voltaram;
  - o viewer injeta o Redis por `dependencies.get_redis_manager_dependency()`; se não estiver
    ligado (`NotImplementedError`), segue sem cache.
- Busca: casefold e sem acento (`unicodedata` NFKD) em nome, `mail` e `userPrincipalName`. Ordem
  padrão: nome; empate por nome.

- [ ] **Passo 1: testes que falham:**
  - `test_lista_os_membros_do_grupo_sem_contas_desabilitadas`;
  - `test_segue_o_next_link_do_grupo` (fake com duas páginas, 1.000 + 3 membros → `total` 1.003)
    (Foco 2);
  - `test_busca_sem_acento_e_sem_caixa` ("joao" acha "João Souza" e "joao@…") (Foco 5);
  - `test_situacao_sem_permissao` e `test_situacao_com_permissao`;
  - `test_ordena_por_permissoes_decrescente`;
  - `test_pagina_e_total` (`page=2&perPage=2` → itens 3 e 4, `total` certo);
  - `test_contagens_direto_e_por_grupo`;
  - `test_sem_grupo_configurado_busca_no_diretorio`;
  - `test_grupo_configurado_inexistente_responde_404`;
  - `test_settings_diz_o_estado_do_grupo` (os 3 valores);
  - `test_segunda_requisicao_usa_o_cache` (o fake conta 1 chamada a `groups/{id}/members`).
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar repositório, business, schema e rota.
- [ ] **Passo 4:** `pytest tests/unit/modules/access_control -q` passa (inclusive os antigos);
  ruff/black.
- [ ] **Passo 5:** relatório (`feat(TS-5405): pessoas do grupo dinâmico com página e filtros`).

### Tarefa B4: quem tem cada permissão, contagem e grupos da pessoa

**Arquivos:**
- Modificar: `business/__init__.py`, `schemas.py`, `viewer.py`
- Teste: `tests/unit/modules/access_control/test_holders_routes.py`; ajustar `test_read_routes.py`

**Interfaces:**
- Consome: B2, B3 (repositório com cache).
- Produz:
  - `GET /roles/{value}/holders` (`value: RoleValue`) →
    `RoleHoldersResponse { people: [{ id, displayName, mail, origins: [{ via, groupId, groupName, assignmentId }] }], groups: [{ id, displayName, memberCount, assignmentId }] }`;
    role fora do Azure → listas vazias; valor fora do formato → 422;
  - `Role.people_count: int` (de `AccessIndex.people_count`);
  - `PersonDetailResponse.groups: list[PersonGroup]`, `PersonGroup { id, displayName, roleCount, ownedByApp }`.

- [ ] **Passo 1: testes que falham:**
  - `test_holders_direto_e_por_grupo_uma_linha_por_pessoa` (Foco 1);
  - `test_holders_com_dois_pontos_no_caminho` (`/roles/all-pre-trade:read/holders` → 200) (Foco 3);
  - `test_holders_de_role_que_falta_no_azure_vem_vazio`;
  - `test_catalogo_traz_people_count`;
  - `test_pessoa_traz_os_grupos_do_portal`.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** a pasta de testes do módulo passa; ruff/black.
- [ ] **Passo 5:** relatório (`feat(TS-5405): quem tem cada permissão e grupos da pessoa`).

### Tarefa B5: `apply` apaga o cache

**Arquivos:**
- Modificar: `business/__init__.py` (`apply_batch`)
- Teste: `tests/unit/modules/access_control/test_batch_routes.py`

**Interfaces:**
- Consome: B1. Produz: depois do `apply` (com sucesso, falha parcial ou exceção do Graph no meio),
  `cache.invalidate()` é chamado uma vez (`try/finally`).

- [ ] **Passo 1: testes que falham:**
  - `test_apply_apaga_o_cache` (a leitura seguinte de `/people` chama o Graph de novo);
  - `test_apply_com_redis_fora_continua` (o `incr` levanta; o `apply` responde 200 e há WARNING)
    (Foco 4).
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** `pytest tests/unit -q`: só as 8 falhas antigas de `cerc_reconciliation`; ruff/black.
- [ ] **Passo 5:** relatório (`feat(TS-5405): mudança pela tela apaga o cache do acesso`).

---

## Front

Caminhos relativos a `src/app/features/access-control/`.

### Tarefa F1: data-access

**Arquivos:**
- Modificar: `data-access/access-control.dto.ts`, `data-access/access-control.service.ts`
- Teste: `data-access/access-control.service.spec.ts`

**Interfaces:**
- Produz:
  - `AccessControlSettings.portalUsersGroup: 'not-configured' | 'ok' | 'not-found'`;
  - `AccessControlRole.peopleCount: number`;
  - `AccessControlPeopleStatus = 'all' | 'with-roles' | 'without-roles'`;
    `AccessControlPeopleSort = 'name' | '-name' | 'roles' | '-roles'`;
    `AccessControlPeopleQuery { search: string; status: AccessControlPeopleStatus; sort: AccessControlPeopleSort; page: number; perPage: number }`;
  - `AccessControlPersonSummary extends AccessControlPerson { roleCount: number; groupCount: number }`;
    `AccessControlPeoplePage { people: AccessControlPersonSummary[]; total: number; page: number; perPage: number; source: 'group' | 'directory' }`;
  - `AccessControlHolderOrigin { via: AccessControlRoleOrigin; groupId: string | null; groupName: string | null; assignmentId: string }`;
    `AccessControlRoleHolders { people: { id; displayName; mail: string | null; origins: AccessControlHolderOrigin[] }[]; groups: { id; displayName; memberCount: number; assignmentId: string }[] }`;
  - `AccessControlPersonGroup { id; displayName; roleCount: number; ownedByApp: boolean }` e
    `AccessControlPersonDetailResponse.groups`;
  - `listPeople(query: AccessControlPeopleQuery): Observable<AccessControlPeoplePage>` (sai o
    `searchPeople`) e `getRoleHolders(value: string): Observable<AccessControlRoleHolders>` (valor
    com `encodeURIComponent`).

- [ ] **Passo 1: testes que falham:** `listPeople` manda os 5 parâmetros; `getRoleHolders('all-pre-trade:read')`
  chama `…/roles/all-pre-trade%3Aread/holders` (Foco 3).
- [ ] **Passo 2:** rodar só o spec → falha.
- [ ] **Passo 3:** implementar tipos e métodos; trocar os usos de `searchPeople` (o
  `models/directory-search.ts` passa a usar `listPeople({ search, status: 'all', sort: 'name', page: 1, perPage: 20 })`).
- [ ] **Passo 4:** `tsc -p tsconfig.app.json` e o spec passam.
- [ ] **Passo 5:** relatório (`feat(TS-5405): contrato novo do controle de acesso no front`).

### Tarefa F2: diálogo de mudança

**Arquivos:**
- Criar: `dialogs/access-change-dialog/access-change-dialog.component.{ts,html,scss,spec.ts}` e
  `dialogs/access-change-dialog/access-change.ts`
- Modificar: `components/batch-preview/*`, `components/batch-result/*` (entrada `compact` para
  caber no diálogo, se precisar)

**Interfaces:**
- Consome: F1 (`previewBatch`, `applyBatch`, `ACCESS_CONTROL_REMOVAL_CONFIRMATION`).
- Produz:
  - `AccessChangeLevel = 'simple' | 'danger' | 'typed'`;
  - `AccessChangeData { title: string; operations: AccessControlOperation[]; level: AccessChangeLevel; typedName?: string; notice?: string }`;
  - `openAccessChange(dialog: DialogService, data: AccessChangeData): Observable<AccessChangeOutcome>`,
    `AccessChangeOutcome { applied: boolean; response: AccessControlBatchApplyResponse | null }`.
- Comportamento: abre e chama a prévia; mostra o que vai acontecer e os bloqueados com o motivo;
  "Aplicar" desabilitado se tudo está bloqueado ou, no `typed`, até o texto digitado (sem espaços
  nas pontas) ser igual a `typedName`; `confirm: "REMOVER"` só quando há `remove_*`/`delete_*`;
  sucesso completo fecha, mostra o toast e devolve `applied: true`; falha parcial fica aberta com o
  item e o motivo e "Tentar de novo" reaplica só as operações que falharam. `danger` e `typed` usam
  o tom de perigo no botão e `role="alertdialog"`.

- [ ] **Passo 1: testes que falham** (com o service falso de `testing/`):
  - abre e pede a prévia uma vez;
  - `simple`: "Aplicar" chama `applyBatch` sem `confirm`;
  - `danger` com `remove_member`: manda `confirm: 'REMOVER'`;
  - `typed`: botão desabilitado até digitar `typedName`; com espaço nas pontas libera;
  - tudo bloqueado: botão desabilitado e o motivo visível;
  - sucesso: fecha com `applied: true` e chama o toast;
  - falha parcial: fica aberto; "Tentar de novo" manda só as operações que falharam.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar, reaproveitando a prévia e o resultado do Em lote.
- [ ] **Passo 4:** passa.
- [ ] **Passo 5:** relatório (`feat(TS-5405): diálogo de mudança direta com prévia`).

### Tarefa F3: modal de detalhe e seletores

**Arquivos:**
- Criar: `components/access-detail/access-detail.component.{ts,html,scss,spec.ts}` (casca do modal),
  `components/access-pickers/{people-picker,group-picker,role-picker}.component.{ts,spec.ts}`

**Interfaces:**
- Consome: F1.
- Produz:
  - `<app-access-detail [heading] [subheading] [views] [(view)]>`, `views: { key: string; label: string; count: number }[]`;
    conteúdo projetado: `[detailPills]`, `[detailActions]`, `[detailDanger]` (o excluir, à
    direita, separado) e o corpo (o pai usa `@switch (view())`). No celular (container estreito),
    ocupa a tela.
  - `<app-access-people-picker [(value)]>` (`string[]` de ids; busca remota por `listPeople`, só
    quem tem acesso), `<app-access-group-picker [(value)] [ownedOnly]>` (ids; grupos do portal e,
    com 2 letras ou mais, do diretório), `<app-access-role-picker [(value)] [enabledOnly]>`
    (valores). Todos sobre o `app-multiselect` (`searchMode="remote"` no de pessoas e grupos).

- [ ] **Passo 1: testes que falham:** o segmentado troca a lista e mostra os contadores; as ações
  ficam no topo e o perigo separado; cada seletor devolve ids/valores e busca no BFF só com 2 letras
  ou mais.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** passa.
- [ ] **Passo 5:** relatório (`feat(TS-5405): modal de detalhe e seletores do acesso`).

### Tarefa F4: store, página e URL do modal

**Arquivos:**
- Modificar: `access-control.store.ts`, `access-control.page.{ts,html,scss,spec.ts}`,
  `access-control.view.ts`
- Criar: `access-control.store.spec.ts`

**Interfaces:**
- Consome: F1, F3.
- Produz no store:
  - `peopleQuery: WritableSignal<AccessControlPeopleQuery>`, `people: Signal<AccessControlPeoplePage | null>`,
    `peopleState`, `loadPeople()`;
  - `detail: Signal<{ kind: 'role' | 'group' | 'person'; id: string } | null>` (da query: `role`,
    `group`, `person`), `openDetail(kind, id)`, `closeDetail()`;
  - `refreshAfterChange(): void` (recarrega roles, grupos, a página de pessoas e o detalhe aberto).
  - o lote fica só para a aba Em lote (sai o `addToBatch` usado pelas outras abas).
- Página: sai o aviso das 3 regras e o "N operações esperam no lote"; sem `write`, o aviso fixo da
  spec; abre o modal certo quando a query tem `role`/`group`/`person` e limpa ao fechar.

- [ ] **Passo 1: testes que falham:** sem `write`, o aviso com o texto exato; `?tab=groups&group=g1`
  abre o modal do grupo; fechar tira o `group` da URL e mantém o `tab`; trocar de aba fecha o modal;
  `refreshAfterChange` chama as quatro recargas.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** passa; os specs antigos da página ajustados ao comportamento novo.
- [ ] **Passo 5:** relatório (`refact(TS-5405): página e estado do acesso sem o lote no centro`).

### Tarefa F5: aba Permissões

**Arquivos:**
- Modificar: `components/roles-tab/*`, `dialogs/role-draft-dialog/*`
- Criar: `components/role-detail/role-detail.component.{ts,html,scss,spec.ts}`

**Interfaces:**
- Consome: F1–F4. Produz: nada para outras tarefas.
- Conteúdo: KPIs, filtros, colunas, ações e modal exatamente como na spec ("### Permissões"). Criar
  aplica direto (`create_role`, nível `simple`) e abre o modal da nova; "Criar no Azure" idem;
  excluir é `typed` com o valor da permissão; remover pessoa direta ou grupo é `danger`; atribuir
  usa os seletores de pessoas e grupos (nível `simple`, aviso "vale no próximo login"; a grupo, mais
  "os membros herdam").

- [ ] **Passo 1: testes que falham:** KPI "Faltando no Azure" liga o filtro; a coluna Pessoas mostra
  `peopleCount`; "Sem ninguém" filtra `peopleCount === 0 && groupCount === 0`; o modal lista uma
  linha por pessoa com as origens e só a direta tem remover (Foco 1); "Atribuir" desabilitado com
  motivo quando falta no Azure; excluir abre o `typed` com o valor.
- [ ] **Passo 2–4:** rodar (falha), implementar, rodar (passa).
- [ ] **Passo 5:** relatório (`feat(TS-5405): aba Permissões com quem tem cada uma`).

### Tarefa F6: aba Pessoas

**Arquivos:**
- Modificar: `components/people-tab/*`
- Substituir: `components/person-detail/*` pelo modal `components/person-detail/` sobre o
  `app-access-detail`

**Interfaces:**
- Consome: F1–F4.
- Conteúdo: como na spec ("### Pessoas"), com paginação, ordenação, busca e situação mandadas ao BFF
  (`peopleQuery`); avisos por `settings.portalUsersGroup` (`not-configured`: aviso de busca no
  diretório; `not-found`: erro dizendo que o grupo não existe).

- [ ] **Passo 1: testes que falham:** mudar a página, a ordenação ou a situação chama `listPeople`
  com os parâmetros; KPI "Sem permissão" liga `status: 'without-roles'`; os dois avisos de
  `portalUsersGroup`; no modal, "Tirar do grupo" desabilitado com o motivo em grupo que não é do app.
- [ ] **Passo 2–4:** rodar, implementar, rodar.
- [ ] **Passo 5:** relatório (`feat(TS-5405): aba Pessoas com quem tem acesso ao portal`).

### Tarefa F7: aba Grupos

**Arquivos:**
- Modificar: `components/groups-tab/*`, `dialogs/group-draft-dialog/*` (membros e permissões
  iniciais)
- Substituir: `components/group-detail/*` pelo modal sobre o `app-access-detail`

**Interfaces:**
- Consome: F1–F4.
- Conteúdo: como na spec ("### Grupos"). "Novo grupo" aplica `create_group` + `add_member` +
  `assign_role` (por nome do grupo novo) num só diálogo; excluir é `typed` com o nome do grupo.

- [ ] **Passo 1: testes que falham:** Origem "Todo o diretório" só busca com 2 letras ou mais; a
  coluna Permissões é contagem; o modal alterna Membros/Permissões com 5 por página e busca; ações
  desabilitadas com o motivo (`ownedByApp` falso; `groupAssignmentEnabled` falso); "Novo grupo"
  manda as três operações na ordem.
- [ ] **Passo 2–4:** rodar, implementar, rodar.
- [ ] **Passo 5:** relatório (`feat(TS-5405): aba Grupos com membros e permissões no modal`).

### Tarefa F8: Em lote e Migração em passos

**Arquivos:**
- Criar: `components/access-steps/access-steps.component.{ts,html,scss,spec.ts}`
- Modificar: `components/batch-tab/*`, `components/batch-builder/*`, `components/migration-tab/*`,
  `components/batch-result/*`

**Interfaces:**
- Consome: F1, F3 (seletores), F4.
- Produz: `<app-access-steps [steps] [current]>` (`steps: string[]`, `current: number`), só visual,
  com `aria-current="step"`.
- Conteúdo: como na spec ("### Em lote" e "### Migração"); saem do builder "Nova permissão" e "Novo
  grupo"; colunas "Operação" e "Item" no centro; tabela do lote e do resultado com paginação;
  "Nada a migrar" quando o plano não tem linhas.

- [ ] **Passo 1: testes que falham:** os passos mostram o atual; "Voltar e editar" volta ao passo 1
  sem perder o lote; o builder não tem mais os dois botões de criar; a Migração sem linhas mostra
  "Nada a migrar".
- [ ] **Passo 2–4:** rodar, implementar, rodar.
- [ ] **Passo 5:** relatório (`refact(TS-5405): Em lote e Migração em passos`).

### Tarefa F9: dados fictícios, `.ai/` e validação (o `main`)

**Arquivos:**
- Modificar: `~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json` (rotas novas e o
  formato novo de `access-control/people`, `settings` e `roles`), `.ai/context/reference-screens.md`
  (padrão lista + modal do controle de acesso), `.ai/rules/components.md` se nascer regra nova.

- [ ] **Passo 1:** dados fictícios das rotas novas (um `holders` por permissão usada no smoke).
- [ ] **Passo 2:** `validar-leva.sh` na worktree do front (build, lint igual à base, suíte inteira)
  e o smoke de `/access-control` em claro, escuro, celular e outra marca.
- [ ] **Passo 3:** `pytest tests/unit -q` e ruff/black no BFF.
- [ ] **Passo 4:** prints no portal local e plano de commits para o Pietro.

## Ordem e paralelismo

1. **Leva 1 (paralela):** agente BFF (B1→B5) e agente do front base (F1→F4).
2. **Leva 2 (paralela, depois da base):** F5, F6, F7 e F8, um agente cada, com pastas disjuntas.
3. **Fechamento:** F9 pelo `main`.
