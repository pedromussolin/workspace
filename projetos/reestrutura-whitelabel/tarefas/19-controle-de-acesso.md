# 19 — Controle de acesso pelo portal

- **TS:** TS-5390 · **Branch:** `feature/TS-5390-controle-de-acesso` (front da 13; BFF da `origin/master`)
- **Status:** em andamento (6ª leva, 16/10)
- **Depende de:** 04 (componentes). Não depende da 13.

## Por quê

Pedido do Pietro em 15/10:
- hoje, criar permissões e grupos e atribuí-los pelo portal do Azure é
  "péssimo" e "muito moroso";
- a ideia é fazer tudo pelo portal: atribuir permissões e criar grupos;
- as operações precisam ser **em lote**;
- se a permissão ainda não existir no Azure, a tela cria.

## Como funciona hoje

- **Permissão:** é uma app role do app registration do BFF. O `value` dela
  (ex.: `poli-chat:read`) chega no claim `roles` do token.
- **No BFF:**
  - cada rota confere as roles com
    `check_authorized_roles([...])`;
  - o `admin:read` funciona como override na maioria delas;
  - `FRONTEND_ROUTE_PERMISSIONS` (`src/shared/utils/constants.py`) diz quais
    roles abrem cada tela do front. O `iam/paths` vem dessa lista.
- **O BFF já fala com o Microsoft Graph (a API do Azure),** com a credencial
  do próprio app (`src/services/azure/__init__.py`), mas só para ler:
  - quem tem quais app roles (`list_app_role_users`);
  - os grupos do usuário.
- **No front:** a tela "Usuários" (11) é de clientes da plataforma, não de
  quem acessa o portal. Não existe tela de acesso.

## Proposta

**Tela `/access-control`**, dentro do shell, com o visual do design system.
Ela tem quatro abas.

1. **Permissões**
   - Catálogo das app roles do Azure, com quantas pessoas e grupos têm cada
     uma.
   - Cruzamento com o código: as roles que o BFF usa
     (`check_authorized_roles` e `FRONTEND_ROUTE_PERMISSIONS`) e que ainda
     **não existem no Azure** aparecem marcadas, com o botão "Criar no
     Azure".
   - O BFF gera essa lista a partir do próprio código, sem lista mantida à
     mão.
2. **Pessoas:** busca no diretório e, para cada pessoa, as roles que ela
   tem, direto ou por grupo.
3. **Grupos:** lista, criação de grupo de segurança, membros e roles do
   grupo.
4. **Em lote**
   - Escolher N pessoas e/ou grupos × M roles, ou colar uma lista de e-mails.
   - A tela mostra uma **prévia** do que vai acontecer:
     - o que será criado (roles e grupos novos);
     - o que será atribuído;
     - o que já existe e será pulado.
   - Depois de confirmar, executa e mostra o resultado item a item
     (sucesso, falha e o motivo).
   - Pode ser repetida sem duplicar nada.

**BFF:** módulo `access_control` (viewer, business e repository), com o
`AzureManager` ganhando a escrita:
- **criar app role:** `PATCH /applications/{id}` com a role nova
  (`id` novo, `value`, nome, descrição, `allowedMemberTypes` User e Group);
- **atribuir role:** `POST /servicePrincipals/{id}/appRoleAssignedTo`,
  para pessoa ou grupo;
- **criar grupo e mexer nos membros:** `POST /groups` e
  `POST /groups/{id}/members/$ref`;
- o lote roda no BFF, item a item, com limite de concorrência e
  repetição quando o Graph pede para esperar (429).

**Segurança:**
- **Escopo próprio** de escrita (ex.: `access-control:write`) e um de
  leitura. Escrever permissão é mais sensível que ler dado.
- **Auditoria:** cada alteração vira um evento de log com quem, o quê, para
  quem e quando, no padrão de logs como eventos.
- **Tudo passa pela prévia e pela confirmação.** A remoção em lote pede uma
  confirmação reforçada.
- **Graph com o mínimo de permissão:** `Application.ReadWrite.OwnedBy` (o
  app só altera o próprio registro), `AppRoleAssignment.ReadWrite.All`,
  `Group.ReadWrite.All` e `User.Read.All`. Todas pedem o consentimento de
  um administrador do Azure (time de infraestrutura).

**Avisos na tela:**
- a role nova só aparece no token no **próximo login** de quem a recebeu;
- quando uma role é atribuída a um grupo, os membros herdam.

## Fatias sugeridas

1. **Leitura:** catálogo, pessoas, grupos e a diferença entre o código e o
   Azure. Já ajuda e não precisa das permissões de escrita no Graph.
2. **Atribuição em lote** de roles a pessoas e grupos, com prévia,
   auditoria e resultado item a item.
3. **Criar** roles e grupos que faltam, inclusive dentro do lote.

## Decisões a tomar (antes de começar)

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D16 | Quem usa a tela | (a) escopo próprio de escrita, sem override do `admin:read`; (b) o `admin:read` | (a): quem administra acesso é um grupo menor que os admins de dados |
| D17 | Atribuir roles a grupos ou só a pessoas | (a) grupos e pessoas; (b) só pessoas | Depende da licença: atribuir app role a **grupo** exige Entra ID P1 ou P2 no tenant. Confirmar com a infraestrutura |
| D18 | Permissões de escrita no Graph para o app do BFF | as quatro acima, com consentimento de admin | Pedir à infraestrutura já na fatia 1, porque o consentimento costuma demorar |
| D19 | Remover pela tela | (a) remover atribuições e membros, com prévia; (b) também apagar roles e grupos | (a). Apagar role ou grupo continua no Azure no começo |

## Testes

- BFF:
  - a business do lote com o Graph falso, cobrindo criar o que falta,
    pular o que existe, falha parcial e repetição no 429;
  - as rotas com e sem o escopo;
  - o evento de auditoria.
- Front:
  - a prévia do lote (diferença entre o pedido e o estado atual);
  - a confirmação;
  - o resultado item a item.

## Contrato da API (16/10, para a 6ª leva)

Front e BFF trabalham em paralelo sobre este contrato. O que precisar
mudar passa pelo `main`, que avisa o outro lado.

**Permissão (D16):**
- escopo `access-control`, com as ações `read` e `write`, ou seja, as
  roles `access-control:read` e `access-control:write`;
- **sem** o override do `admin:*`;
- a rota `/access-control` fica no `FRONTEND_ROUTE_PERMISSIONS` com
  `access-control:read`;
- o front usa o `iamGuard` na rota e libera os botões de escrita pelo
  `authorizeActions({ scope: 'access-control' })`.

**Rotas do BFF** (JSON em camelCase, como os outros módulos):

| Rota | Escopo | Resposta |
|---|---|---|
| `GET access-control/settings` | read | `{ canWrite, groupAssignmentEnabled, appDisplayName }` |
| `GET access-control/roles` | read | `{ roles: Role[] }` |
| `GET access-control/people?search=&limit=` | read | `{ people: Person[] }` |
| `GET access-control/people/{id}` | read | `{ person: Person, roles: PersonRole[] }` |
| `GET access-control/groups?search=` | read | `{ groups: Group[] }` |
| `GET access-control/groups/{id}` | read | `{ group: Group, members: Person[] }` |
| `POST access-control/batch/preview` | write | `{ items: PlanItem[], summary }`, para o corpo `{ operations: Operation[] }` |
| `POST access-control/batch/apply` | write | `{ items: ResultItem[], summary }`, para o corpo `{ operations, confirm? }` |

**Tipos:**
- `Role`:
  - `{ value, displayName, description, appRoleId | null, isEnabled }`;
  - `inAzure` (existe no app registration) e `usedInCode` (aparece em
    `check_authorized_roles` ou no `FRONTEND_ROUTE_PERMISSIONS`);
  - `codeRefs: string[]` (ex.: "tela /pre-trade", "GET /operations/...");
  - `userCount`, `groupCount`;
  - `deletable` e `notDeletableReason`.
- `Person`: `{ id, displayName, mail, userPrincipalName }`.
- `PersonRole`: `{ value, via: 'direct' | 'group', groupId?, groupName?,
  assignmentId? }`.
- `Group`: `{ id, displayName, description, memberCount, roles: string[],
  ownedByApp, deletable, notDeletableReason }`.
- `Operation`, com o campo `type`:
  - `create_role { value, displayName, description }`;
  - `create_group { displayName, description }`;
  - `assign_role { role, principal: { kind: 'user' | 'group', id? | email?
    | name? } }`. O `name` aponta para um grupo criado no mesmo lote;
  - `add_member { group: { id? | name? }, user: { id? | email? } }`;
  - `remove_assignment { role, principal: { kind, id } }`;
  - `remove_member { groupId, userId }`;
  - `delete_role { value }`;
  - `delete_group { groupId }`.
- `PlanItem`: `{ index, type, label, action, reason | null }`.
  - `label` é o texto em PT-BR do que vai acontecer.
  - `action` é um de `create`, `assign`, `add`, `remove`, `delete`, `skip`
    e `blocked`.
- `ResultItem`: o `PlanItem` mais `{ status: 'ok' | 'skipped' | 'failed',
  error | null }`.
- `summary`: as contagens por `action` (ou por `status`, no resultado).

**Regras do lote:**
- **Execução:** o `apply` recalcula o plano e nunca confia na prévia. Pode
  ser repetido sem duplicar nada: o que já existe vira `skip`.
- **Ordem:** criar roles e grupos → membros → atribuições → remoções →
  exclusões.
- **E-mail:** é resolvido para o id na prévia. Se não achar, o item fica
  `blocked`.
- **Grupo (D17):** com `groupAssignmentEnabled` desligado, atribuir a grupo
  fica `blocked`, com o motivo.
- **Apagar role (D19):**
  - só app role do app registration do BFF;
  - `blocked` se a role ainda é usada no código;
  - as atribuições dela entram na prévia como itens de remoção antes da
    exclusão;
  - no Graph, a role é desabilitada antes de sair.
- **Apagar grupo (D19):**
  - só grupo de que o app é dono e sem atribuição em outro app. Senão, o
    item fica `blocked`, com o motivo;
  - a exclusão no Azure é recuperável por 30 dias. A tela avisa.
- **Confirmação reforçada:** lote com remoção ou exclusão só roda com
  `confirm: "REMOVER"`. Na tela, a pessoa digita a palavra.
- **Concorrência:** no máximo 4 chamadas ao Graph ao mesmo tempo. No 429,
  repete respeitando o `Retry-After`, até 3 vezes.
- **Auditoria:** um evento INFO por lote aplicado, com mensagem fixa e no
  `extra` quem fez e a lista de itens (tipo, alvo, role e resultado). Item
  que falha vai como WARNING. Segue o padrão de logs como eventos.

**Graph (D18):** o agente do BFF confere na documentação da Microsoft o
menor conjunto de permissões que limita a escrita ao próprio app e aos
grupos de que ele é dono, por exemplo `Application.ReadWrite.OwnedBy` e
`Group.Create` no lugar de `Group.ReadWrite.All`, se cobrirem os membros.
A lista final vai para o Pietro pedir à infraestrutura.

**Tela `/access-control`:**
- **Abas:** Permissões, Pessoas, Grupos e Em lote.
- **Peças:** as de `shared/ui` (tabela, `app-search-field`,
  `app-kpi-grid`, pílulas, diálogo e confirmação).
- **Avisos:**
  - a role nova só chega no token no próximo login;
  - os membros de um grupo herdam as roles dele;
  - grupo apagado é recuperável por 30 dias no Azure.

