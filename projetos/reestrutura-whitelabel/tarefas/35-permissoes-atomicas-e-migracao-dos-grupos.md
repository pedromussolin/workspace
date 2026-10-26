# 35 — Um escopo por área em todas as páginas e migração manual dos grupos

- **TS:** TS-5431 (épico TS-5357).
- **Repos:** BFF (catálogo de permissões, rotas, lista de migração) e front (abas e botões por escopo). Grupos e
  atribuições são manuais (D128), sem tela de migração de grupos e sem catálogo de perfis.
- **Status (26/10):** implementada e validada localmente, **sem commit** (revisão do Pietro pendente). Branch
  `feature/TS-5431-escopos-por-area` (front e BFF), a partir da `release/20261026`. BFF 2382 testes; front
  `validate.sh` ok com 4983 specs; smoke ok nas 11 rotas mexidas. Regras novas no `.ai/rules/permissions.md`
  do front e na skill `new-page`. Levantamento completo e a lista das roles (com nomes reais) em
  `~/repos/.reestrutura_whitelabel/agentes/ts5431/` (`levantamento/`, `roles-ts5431.md`, `app-roles-ts5431.json`).
- Fora da `release/20261026`.

## Por quê

O acesso passa a ser só por grupo (D124): grupos de página `[FRONT] <página> - <perfil>` e grupos de
instituição `[FRONT] <NOME>`. Na subida em produção, o Pietro quer recriar todos os grupos no padrão novo
e reatribuir as pessoas, sem se prender aos grupos de hoje, e depois atualizar a variável dos grupos de
instituição com os ids novos.

Hoje uma permissão às vezes cobre funções que o negócio quer separar: no Envio de relatórios,
`report-transfer:update` edita fluxos **e** agendamentos, então não dá para o time de produtos editar só o
agendamento.

## Desenho

1. **Um escopo por área (D129, D130).** Cada aba ou área com dados próprios tem o seu escopo, só com as ações dela.
   Nome `{escopo-da-página}-{área}`. Os escopos antigos saem; a lista de migração (antiga → nova) dá a quem tem a
   role antiga todas as novas que mantêm o acesso de hoje. A lista é composta: cobre tanto as roles de antes da
   TS-5391 quanto as de agora, porque a cópia não encadeia `A → B → C` num lote só.

   | Página | Escopos novos (ações) | Saem |
   |---|---|---|
   | Envio de Relatórios | `report-transfer-flows` (read, create, update, delete, test, run), `report-transfer-schedules` (read, create, update, delete, run), `report-transfer-executions` (read), `report-transfer-connections` (read, create, update, delete, test) | `report-transfer`, `report-transfer-manage` |
   | Controle de Acesso | `access-control-roles` (read, create, update, delete), `access-control-people` (read, update, impersonate), `access-control-organization` (update), `access-control-groups` (read, create, update, delete), `access-control-batch` (run), `access-control-migration` (read, run) | `access-control` |
   | Orquestrador | `orchestrator-executions` (read, reprocess), `orchestrator-product-view` (read) | `orchestrator`, `orchestrator-product` |
   | Dashboard de Registros | `cerc-reconciliation-dashboard` (read), `cerc-reconciliation-table` (read), `cerc-reconciliation-pending-assets` (read, run = "Verificar na CERC") | `cerc-reconciliation` |
   | Consolidado de Caixa | `cash-consolidation-summary` (read), `cash-consolidation-analytic` (read) | `cash-consolidation` |
   | PDD | `pdd-overview`, `pdd-history`, `pdd-stock-movement` (read) | `pdd` |
   | Gerenciamento de Produtos | `products-config-products` (read, create, update), `products-config-entities` (create) | `products-config` |
   | Onboarding BGT | `onboarding-bgt-listing` (read, reprocess), `onboarding-bgt-monitoring` (read), `onboarding-bgt-details` (read, reprocess, run = reenviar webhook) | `onboarding-bgt` |
   | Onboarding Interno e Externo | `users-list`, `users-details`, `users-documents` (read) | `users` |

   **Sem mudança:** Formalização e Formalização (unidades), Detalhes do Contrato, Lotes de Cessão, Lotes de Liquidação
   (os dois escopos já são um por aba), Pré-Trade (os sete escopos já são as áreas de aprovação, e o motor de workflow
   só aceita um escopo), Base de Conhecimento, Poli Chat, Desempenho de Carteira (a aba Tabela não tem dados),
   Acompanhamento de Clientes, Simulação de Propostas, Design System, Docs da API e Administrador.

2. **Decisões técnicas (da implementação):**
   - os cinco `access-control-*` entram no `SCOPES_WITHOUT_ADMIN_OVERRIDE` (o `admin:read` não abre o Controle de
     Acesso);
   - o lote do Controle de Acesso checa cada operação pelo escopo dela (item proibido volta "Sem permissão" na
     prévia), porque `batch/apply` recebe qualquer operação; mudar organização pede `access-control-organization:update`;
   - rota enxuta `GET /products/lookup` para o filtro de produto de outras páginas (hoje a lista de usuários só
     funciona com `products-config:read`);
   - o casamento de rotas do `iam/navigation` testa as rotas literais antes das com `{id}` (`/onboarding-bgt/monitoring`
     casava com `/onboarding-bgt/{id}`);
   - Lotes de Liquidação: `/payments` e o export de recusados checam a leitura da aba certa;
   - abas que só reapresentam os mesmos dados (PDD, Dashboard e Tabela da CERC) escondem a aba no front; a rota do BFF
     aceita qualquer uma das leituras.
   - Bootstrap (D130): as roles novas do Controle de Acesso são criadas e atribuídas à mão antes do deploy.

3. **Migração manual dos grupos (D128):** o Pietro recria os grupos e reatribui as pessoas pelo Controle de
   acesso (o lote com prévia já existe na `release/20261026`: criar grupo, atribuir permissão, pôr e tirar
   membro, copiar atribuições, mudar a instituição da pessoa, apagar grupo). Ordem, para ninguém perder acesso:
   1. criar os grupos novos e pôr as pessoas, sem tirar nada;
   2. grupos de instituição: a infraestrutura troca as claims (`org_type` e `internal_client_id`) para os grupos
      novos **antes** de alguém sair dos antigos, senão a pessoa perde a organização e não entra;
   3. `CFG_ACCESS_CONTROL_INSTITUTION_GROUPS` com os ids novos, numa linha só, e o BFF reiniciado;
   4. só então tirar os grupos antigos e as atribuições diretas;
   5. os grupos `[PLGN AI]` ficam com o **nome exato** de hoje (ver abaixo).

## Grupos amarrados no código (levantamento de 26/10, na `release/20261026`)

**Pelo nome exato (BFF `src/shared/schemas/users.py:20`, enum `Groups`).** O BFF lê os ids do claim `groups` do
token, busca os nomes no Graph e compara o `displayName` com estes nomes, sem tolerar acento, caixa ou espaço
diferente. Quem está no grupo ganha o departamento (alias).

| Grupo no Azure | Alias | Onde pesa |
|---|---|---|
| `[PLGN AI] <empresa>-all` (nome real no `privado.md`) | `all` | nada hoje: na Base de Conhecimento, `all` vira "sem departamento" |
| `[PLGN AI] Dados` | `analytics` | POLI Dados e Analytics; Base de Conhecimento |
| `[PLGN AI] Financeiro` | `finance` | POLI Financeiro; Base |
| `[PLGN AI] RH` | `hr` | POLI RH; Base |
| `[PLGN AI] RI` | `ir` | POLI RI; Base |
| `[PLGN AI] TI` | `engineering` | POLI Engenharia de Software; Base |
| `[PLGN AI] Infra/SI` | `infrasec` | POLI Seg. Inf. & Infra; Base |
| `[PLGN AI] Juridico` | `legal` | POLI Jurídico; Base |
| `[PLGN AI] Gestao` | `management` | POLI Gestão; Base |
| `[PLGN AI] Operacoes` | `operations` | POLI Operações; Base |
| `[PLGN AI] Produtos` | `products` | POLI Produtos; Base |
| `[PLGN AI] Compliance` | `compliance` | só Base (não há POLI Compliance) |
| `[PLGN AI] Controladoria` | `controllership` | nenhuma tela: o front não tem esse departamento |

- **POLI de um departamento** (`/legal-poli-chat` etc.): abrir a página pede a app role `{alias}-poli-chat:read`
  (`src/shared/utils/constants.py:34`); mandar mensagem e ver conversas pede **também** estar no grupo
  (`check_user_groups`, `src/shared/business/users.py:173`, 403 se não estiver). A POLI Geral não pede grupo.
- **Base de Conhecimento:** documento de um departamento pede estar no grupo **e** a app role
  `{alias}-poli-knowledge-base:{ação}` (ou `admin:{ação}`); sem departamento, `poli-knowledge-base:{ação}`
  (`src/modules/ai_assistant/business.py:28`). O front oferece os departamentos de
  `core/auth/groups.constants.ts`, que tem `ceo` e `risk` (sem grupo no BFF: ninguém consegue agir neles) e não
  tem `controllership`.
- **"Ver como":** monta os departamentos da pessoa simulada pelos mesmos nomes
  (`src/modules/access_control/viewer.py:308`).

**Pela configuração (id do grupo, fora do código):**
- `CFG_ACCESS_CONTROL_INSTITUTION_GROUPS`: os grupos de instituição; a organização e o cliente vêm das claims do
  Enterprise Application ligadas a eles (infraestrutura).
- `CFG_ACCESS_CONTROL_PORTAL_USERS_GROUP_ID`: grupo com todos que acessam o portal (lista de Pessoas), mantido pela
  infraestrutura (D92).

**Só convenção de nome, sem lógica:** os grupos `[FRONT] <página> - <perfil>`. O acesso vem das app roles
atribuídas ao grupo; o nome só serve para a tela mostrar a página e o perfil. Ao criar à mão, usar o rótulo da
página exatamente como na lista (`src/modules/access_control/business/pages.py`).

**Parece grupo, mas é app role:** as áreas do Pré-Trade (`management`, `compliance`, `risk`, `legal`, `ceo`,
`operations`, `all`) são prefixos de app role (`legal-pre-trade:approve`), e os avisos do Pré-Trade vão por
e-mail de quem tem a role. O disparo de e-mail do apl-shared-service aceita grupo do Entra ID como destino, mas
nenhum código passa um. apl-ai-service, data-lake-api, orquestrador e TSE não citam grupo.

**Conferir com a infraestrutura:** se o App Registration só emite no token os grupos atribuídos ao app
(`groupMembershipClaims` = `ApplicationGroup`), um `[PLGN AI]` recriado precisa ser atribuído ao Enterprise
Application, senão os membros não ganham o departamento.

## Fora desta tarefa

- Checagem das roles de departamento da POLI no BFF (`{departamento}-poli-chat`, `{departamento}-poli-knowledge-base:read`)
  e o menu da Base de Conhecimento: outra tarefa (D130).

## Pronto quando

- Toda área de tela com escopo próprio, cada ação com a sua permissão, sem perda de acesso para ninguém na troca
  (lista de migração na tela Migração).
- Grupos recriados à mão (D128), conferidos com o levantamento acima, e a variável dos grupos de instituição
  com os ids novos.

## Regras

As da [32](32-envio-por-subfluxo.md): git do `~/repos/CLAUDE.md`, commit só depois da revisão do
Pietro, Python em inglês, log com mensagem fixa e dimensões no `extra`, `.ai/` do front, validar local
antes.
