# 35 — Permissões atômicas por ação, perfis por página e migração manual dos grupos

- **TS:** TS-5431 (épico TS-5357).
- **Repos:** BFF (catálogo de permissões e de perfis, rotas) e front (ações, "Novo grupo"). A migração dos grupos
  é manual (D128), sem tela.
- **Status (26/10):** desenho combinado com o Pietro (D125, D126 e D128). Feito o levantamento dos grupos
  amarrados no código (abaixo). **Antes de implementar as permissões, falta o levantamento de todas as telas.**
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

1. **Permissões atômicas (D125):** toda ação na tela tem uma permissão própria. Uma página pode ter vários
   escopos, um por área, como o Envio de relatórios já faz com as conexões (`report-transfer-manage`). Ex.:
   Fluxos (`report-transfer`), Agendamentos (`report-transfer-schedules`, novo) e Conexões.
   - Cada separação mexe no catálogo do BFF, na proteção das rotas, nas ações do front e nas app roles do
     App Registration.
   - Ninguém perde acesso na troca: quem tem a permissão antiga ganha as novas pela migração de permissões
     que a tela já tem.
2. **Catálogo de perfis por página (D126):** no BFF, ao lado do catálogo de permissões. Cada página declara
   perfis com nome, descrição e as permissões exatas (ex.: Leitura, Agendamentos, Fluxos, Conexões, Admin).
   - Perfis se somam: uma pessoa pode estar em mais de um perfil da mesma página.
   - Página sem perfis próprios ganha Leitura e Admin.
   - No "Novo grupo" de página, o perfil vem do catálogo com as permissões dele; "Perfil próprio" fica para
     exceções. Grupo de página só recebe permissões da página dele.
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

## A fazer antes de implementar

- **Levantamento de todas as telas:** as ações de cada uma, a permissão que protege cada ação e onde uma
  permissão cobre mais de uma função. Com ele, o Pietro decide o que separar e os perfis de cada página.

## Pronto quando

- Toda ação de tela com permissão própria, sem perda de acesso para ninguém na troca.
- Catálogo de perfis por página no BFF, usado pelo "Novo grupo".
- Grupos recriados à mão (D128), conferidos com o levantamento acima, e a variável dos grupos de instituição
  com os ids novos.

## Regras

As da [32](32-envio-por-subfluxo.md): git do `~/repos/CLAUDE.md`, commit só depois da revisão do
Pietro, Python em inglês, log com mensagem fixa e dimensões no `extra`, `.ai/` do front, validar local
antes.
