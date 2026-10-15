# 19 — Controle de acesso pelo portal

- **TS:** a criar · **Branch:** `feature/TS-?-controle-de-acesso` (front e BFF)
- **Status:** a planejar. Fica para depois do épico (pedido de 15/10).
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
