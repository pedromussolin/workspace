# 21 — Permissões por ação: escopos e ações bem definidos

- **TS:** TS-5391 · **Branch:** `feature/TS-5391-permissoes-por-acao` (front da 19; BFF da 19)
- **Status:** a iniciar (decisões tomadas em 16/10)
- **Depende de:** 19 (catálogo de roles a partir do código e lote para reatribuir)

## Por quê

Pedido do Pietro em 16/10: hoje várias telas usam a mesma role para ações de
natureza diferente. Exemplo: no Envio de Relatórios, a `update` serve para
editar fluxos e também para o dry run. A ideia:
- deixar cada escopo com ações bem definidas;
- depois, reatribuir as permissões já concedidas.

## Inventário (16/10, `origin/master` do BFF e branch da 13 no front)

**Uma role cobrindo ações de natureza diferente:**

| Tela | Role | Cobre hoje |
|---|---|---|
| Envio de Relatórios | `report-transfer:update` | editar fluxo, editar e ativar/desativar agendamento e o **dry run** |
| Envio de Relatórios | `report-transfer:create` | criar e duplicar fluxo, criar agendamentos e o **dry run** |
| Envio de Relatórios | `report-transfer:reprocess` | "Enviar agora" (execução manual, não reprocesso) |
| Envio de Relatórios | `report-transfer-manage:read` | listar conexões e **testar conexão** (abre a conexão real) |
| Formalização | `whitelists:update` | editar o cadastro **e aprovar/ativar/inativar** (a ação `approve` não é usada) |
| Formalização | `whitelists:create` | cadastrar já com status "ativo" |
| Lotes de Liquidação | `liquidation-fake-batches:update` | **fechar lote** (execução, não edição) |
| Lotes de Liquidação | `liquidation-real-batches:approve` | aprovar **e recusar**. No front, a recusa aparece como "Excluir lote", com outra role |
| Onboarding | `onboarding-bgt:update` | reprocessar (um ou em lote) e reenviar webhook |
| Orquestrador | `orchestrator:read` | ler **e re-executar processo** |
| Produtos | `products-config:read` | ler **e criar/alterar** produto e cadastros |
| Poli Chat | `poli-chat` (sem ação) | conversar, excluir e renomear conversas, **indexar e excluir documentos** |
| Todas | `admin:{ação}` | vale em todo escopo e grupo. Ex.: `admin:approve` aprova lote real e decide as duas rodadas do Pré-Trade |
| Todas | `:read` | exportar e baixar (não existe ação `export`) |

**Divergências e brechas achadas no caminho:**
- **Escrita só com `read`:**
  - Produtos: criar e alterar;
  - Orquestrador: re-executar;
  - Base de Conhecimento: indexar e excluir. A exclusão é pelo nome do
    arquivo, em qualquer departamento.
- **Poli Chat:**
  - renomear conversa não confere o dono;
  - a rota pede `poli-chat:read`, e a API pede `poli-chat` sem ação. Quem só
    tem a `:read` toma 403.
- **`GET /iam/app-role-assignments`:** lista quem tem cada role, sem sessão.
  A única proteção é não existir com o prefixo `/api`.
- **Conciliação manual:** o "Excluir lote" confere `:delete` no front, mas
  chama a recusa, que exige `:approve`. A `liquidation-real-batches:delete`
  não é conferida em nenhum endpoint.
- **Detalhe do contrato:** a rota pede `contract-details:read`, e a API,
  `assignment-batches:read`.
- **PDD:** o menu sai por `pdd:read`, e a API pede `valid:read`.
- **Consolidado de Caixa:** o analítico (`/cash-consolidation/:fund/analytic`)
  não está no `FRONTEND_ROUTE_PERMISSIONS`, então o `iamGuard` nega todo
  mundo. Já era assim na master.
- **Pré-Trade:**
  - a `all-pre-trade:approve-bypass` existe no serviço compartilhado, mas as
    `Policies` do BFF não a têm, e o header que o BFF manda apaga o bypass a
    cada acesso;
  - `admin:approve` decide as duas rodadas.
- **Base de Conhecimento:** os grupos `ceo` e `risk` existem no front, mas
  não no `Groups` do BFF. Com eles, a API sempre devolve 403.
- **CERC e PDD:** o front chama rotas que não existem na master do BFF
  (pendências e registro do CERC, PDD por produto). São de tarefas em
  andamento fora do épico.

## Proposta

1. **Catálogo único de permissões no BFF.** Para cada escopo: as ações que
   ele aceita, o nome e a descrição em PT-BR.
   - As rotas passam a declarar `require(escopo, ação)`, no lugar de listas
     soltas de strings.
   - O `require` acrescenta sozinho o `admin:{ação}`, exceto nos escopos de
     `SCOPES_WITHOUT_ADMIN_OVERRIDE` (hoje só o `access-control`). Hoje,
     cada lista inclui o admin à mão, ou esquece (D28 e D55).
   - Toda página tem um escopo próprio, e cada contexto dentro dela com
     permissão diferente também (D55).
   - O `FRONTEND_ROUTE_PERMISSIONS`, o `iam/actions` e o catálogo da 19 leem
     dele. A tela de acesso mostra o nome e a descrição de cada permissão.
2. **Vocabulário fixo de ações**, cada uma com significado (D27): `read`,
   `create`, `update`, `delete`, `approve`, `review`, `reprocess`, `run` e
   `test`.
3. **Ações por tela** (proposta, a fechar nas decisões):
   - Envio de Relatórios: `test` (dry run e testar conexão) e `run` ("Enviar
     agora"), separados de `create`/`update`.
   - Formalização: `approve` para mudar status e ativar; cadastrar com status
     diferente de pendente exige `approve`.
   - Liquidação: fechar lote vira `run`; recusa continua com `approve`, e o
     front corrige o botão.
   - Onboarding: reprocessar e reenviar webhook viram `reprocess`.
   - Orquestrador: re-executar vira `reprocess`.
   - Produtos: escrita com `create`/`update`.
   - Poli Chat: `poli-chat:read` de verdade. A Base de Conhecimento confere a
     role por departamento na indexação e na exclusão.
   - Correções das divergências acima.
4. **Transição sem ninguém perder acesso** (D31):
   - por um período, o BFF aceita a role antiga ou a nova, por
     configuração;
   - a reatribuição espelha quem tem hoje: quem tem `report-transfer:update`
     ganha também `report-transfer:test`, e assim por diante;
   - depois, o dono de cada área revisa, e as roles antigas saem pela tela da
     19.
5. **Reatribuição pela tela da 19** (D32): uma operação nova no lote,
   `copy_assignments { from, to }`, com prévia.

## Mapa de permissões (decidido em 16/10)

**Regras gerais:**
- toda rota declara `require(escopo, ação)`, que aceita `{escopo}:{ação}` ou
  `admin:{ação}`, menos nos escopos de `SCOPES_WITHOUT_ADMIN_OVERRIDE`
  (D28, D55);
- o catálogo de cada escopo (ações, nome e descrição em PT-BR) é a fonte do
  `iam/actions`, do `FRONTEND_ROUTE_PERMISSIONS` e da tela da 19;
- **transição** (D31): cada ação nova aceita também a role antiga enquanto
  `CFG_PERMISSIONS_LEGACY_ROLES` estiver ligada.

| Escopo | Ação na tela | Hoje | Depois | Na transição, também aceita |
|---|---|---|---|---|
| `report-transfer` | dry run (testar fluxo) | `create` ou `update` | `test` | `create`, `update` |
| `report-transfer` | "Enviar agora" | `reprocess` | `run` | `reprocess` |
| `report-transfer` | criar e duplicar fluxo, criar agendamento | `create` | `create` | — |
| `report-transfer` | editar fluxo, editar e ativar agendamento | `update` | `update` | — |
| `report-transfer-manage` | testar conexão | `read` | `test` | `read` |
| `whitelists` | mudar status em lote, ativar/inativar, cadastrar com status ≠ pendente, editar mudando o status | `update` (`create` no cadastro) | `approve` | `update` |
| `whitelists` | editar os dados, sem mudar o status | `update` | `update` | — |
| `liquidation-fake-batches` | fechar lote | `update` | `run` | `update` |
| `liquidation-real-batches` | recusar ("Excluir lote" no front) | front `delete`, BFF `approve` | `approve`; o botão do front confere `approve` | — |
| `onboarding-bgt` | reprocessar (um e em lote), reenviar webhook | `update` | `reprocess` | `update` |
| `orchestrator` | re-executar processo | `read` | `reprocess` | `read` |
| `products-config` | criar produto e cadastros | `read` | `create` | `read` |
| `products-config` | salvar produto | `read` | `update` | `read` |
| `poli-chat` | conversar e gerir conversas | `poli-chat` (sem ação) | `read` | `poli-chat` |
| `{dept}-poli-knowledge-base` | indexar e excluir documento | `poli-chat` (fix da D33 já confere o departamento) | `create` e `delete` do departamento | — |
| `pdd` | ver o PDD | menu `pdd:read`, API `valid:read` | `pdd:read` | `valid:read` |
| `contract-details` | abrir o detalhe do contrato | rota `contract-details:read`, API `assignment-batches:read` | `contract-details:read` | `assignment-batches:read` |
| `cash-consolidation` | analítico do fundo | rota sem entrada (nega todos) | `cash-consolidation:read` em `/cash-consolidation/{fund}/analytic` | — |
| `all-pre-trade` | bypass de aprovação | **sai do mapa (16/10):** o serviço compartilhado removeu a permissão de propósito (TS-5270); o bypass agora é aprovado por um usuário "Sistema". O inventário estava desatualizado | — |

**Migração** (D32, pela tela da 19 com `copy_assignments`; espelha quem tem
hoje, sem tirar nada):
- `report-transfer:create` e `report-transfer:update` → `report-transfer:test`;
- `report-transfer:reprocess` → `report-transfer:run`;
- `report-transfer-manage:read` → `report-transfer-manage:test`;
- `whitelists:update` → `whitelists:approve`;
- `liquidation-fake-batches:update` → `liquidation-fake-batches:run`;
- `onboarding-bgt:update` → `onboarding-bgt:reprocess`;
- `orchestrator:read` → `orchestrator:reprocess`;
- `products-config:read` → `products-config:create` e
  `products-config:update`;
- `poli-chat` → `poli-chat:read`;
- `valid:read` → `pdd:read`.

Depois de um ciclo, o dono de cada área revisa quem precisa da nova, a
`CFG_PERMISSIONS_LEGACY_ROLES` desliga e as roles antigas que sobraram saem
pela tela da 19. Isso fica na 24.

## Decisões (tomadas em 16/10, ver `decisoes.md`)

D27 a D33 aprovadas como recomendadas; D28 com a regra do admin (D55).

## O que foi feito: fix das brechas (D33, 16/10/2026)

BFF, branch `fix/TS-5391-brechas-de-permissao`, criada da `origin/master`
(`946dce3`). São 5 commits, sem push:

| Commit | O quê |
|---|---|
| `5680763` | indexar documento na Base de Conhecimento exige `{dept}-poli-knowledge-base:create` (ou `admin:create`), além do grupo. Sem departamento, `poli-knowledge-base:create` |
| `39cc6bc` | excluir documento exige o grupo e `{dept}-poli-knowledge-base:delete` (ou `admin:delete`) e só apaga se o documento existe naquele departamento. Se o mesmo nome existe em mais de um, devolve 409. O `department` ficou opcional, porque o front ainda não manda |
| `780e558` | renomear conversa manda o e-mail da sessão, e o serviço de IA confere o dono. **Hoje a função está quebrada para todos** (422 no serviço de IA, 500 no BFF), e volta a funcionar |
| `6b3a696` | o BFF recusa (400) a exclusão de documento com apóstrofo no nome. Isso fecha, do lado do BFF, a falha A29 do serviço de IA |
| `99dcd3e` | a listagem da Base de Conhecimento usa só o índice padrão: o `index_name` livre, que deixava ler outro índice do Azure AI Search, sai da rota. O front nunca mandou esse parâmetro |

**Validação:**
- 555 testes, com as mesmas 8 falhas da base; `ruff` e `black` iguais à
  base;
- os testes novos falham no código antigo.

**Quem perde acesso:**
- pela tela, ninguém;
- pela API, quem só tinha `poli-chat` e indexava ou excluía sem a role do
  departamento. Era essa a brecha.

**Não feito:** o `app-role-assignments` sem sessão (A31). Precisa de um
segredo novo, e a decisão está com o Pietro.

**Para a parte do front da 21:** a exclusão passa a mandar o `department`.

## O que foi feito: BFF (16/10/2026)

Branch `feature/TS-5391-permissoes-por-acao`, criada da 19 (`bc7187f`). São
12 commits, sem push.

**O que entrou:**
- **Catálogo único** em `src/shared/utils/permissions.py`: escopo, ações,
  nome e descrição. As `Policies` ganham `run` e `test`.
- **O catálogo alimenta** o `FRONTEND_ROUTE_PERMISSIONS` (igual ao antigo,
  mais a entrada do analítico), o `iam/actions` e a tela da 19.
- **`require(escopo, ação)` e `require_any`:** aceitam `admin:{ação}`, menos
  no `access-control`, e recusam na subida do app uma ação que não está no
  catálogo. Aceitam também uma condição (`when`), ex.: só quando o corpo
  muda o status. Saem o `check_authorized_roles` e o `check_scope_actions`.
- **O mapa inteiro**, menos o `approve-bypass`. O Pré-Trade passa a aceitar o
  `admin` de qualquer ação dele (D28).
- **`CFG_PERMISSIONS_LEGACY_ROLES`**, ligada por padrão. Ela vale nas rotas e
  no `iam/actions`.
- **`GET access-control/migrations`:** devolve o plano e o lote pronto, com
  um `create_role` para cada role que falta e um `copy_assignments` por
  linha.
- **`copy_assignments`:** um item por pessoa ou grupo que tem a `from`. Quem
  já tem a `to` é pulado, e o item fica bloqueado se a `to` não existe.
- **Validação:** 809 testes, com as mesmas 8 falhas da base. Cada commit
  testado isolado.

**Riscos para desligar a transição (vão para a 24):**
- **Admins:** `admin:test` e `admin:run` ainda não existem no Azure.
  Decisão pendente: como migrar os `admin:*`.
- **Grupos:** quem recebe a role antiga só pelo grupo perde acesso enquanto a
  atribuição a grupo estiver desligada (D17).
- **Token:** a role copiada só chega à sessão no próximo refresh do token
  (cerca de 1 h). Desligar só depois de um ciclo.
- **Formalização:** a edição com `status` no corpo pede `approve`. O front da
  21 passa a mandar o status só quando ele muda.

**Ajustes feitos** (3 commits, 15 no total, 828 testes, com as mesmas 8
falhas da base):
- **`ff0a35f`:** a migração copia `assignment-batches:read` para
  `contract-details:read`. O plano fica com 13 linhas.
- **`e4c6806`:** a role antiga passa a valer só nas rotas que a aceitavam.
  Na transição, cadastrar como ativo aceita também `whitelists:create`.
- **`4617037`:** a exclusão de role na tela da 19 passa a ser protegida pelo
  catálogo. Com a transição desligada, as roles antigas ficam apagáveis
  (`report-transfer:reprocess`, `onboarding-bgt:update`,
  `liquidation-fake-batches:update`, `poli-chat` e `valid:read`).

**Pendente:** a migração dos `admin:*` (D56, decisão do Pietro).

