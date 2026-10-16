# 21 — Permissões por ação: escopos e ações bem definidos

- **TS:** TS-5391 · **Branch:** `feature/TS-5391-permissoes-por-acao` (front da 19; BFF da 19)
- **Status:** a planejar (pedido de 16/10)
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

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D27 | Vocabulário de ações | (a) `read`, `create`, `update`, `delete`, `approve`, `review`, `reprocess`, `run` e `test`, com exportar dentro de `read`; (b) idem mais `export` | (a): exportar quase sempre acompanha a leitura |
| D28 | Override do `admin:*` | (a) como hoje, em tudo; (b) só para `read`, e as outras ações exigem a role do escopo; os admins atuais ganham as roles explícitas na migração; (c) acabar com o admin | (b): o admin de hoje aprova lote e decide o Pré-Trade sem ninguém ver |
| D29 | Aprovação na Formalização | (a) `approve` para status e ativação, separado de `update`; (b) como hoje | (a) |
| D30 | Envio de Relatórios | (a) `test` e `run` separados, e ativar/desativar continua `update`; (b) também separar o liga/desliga | (a) |
| D31 | Transição | (a) período com role antiga ou nova, migração espelhando quem tem hoje e remoção das antigas depois; (b) troca direta num deploy | (a): ninguém perde acesso no dia |
| D32 | Como reatribuir | (a) tela da 19, com `copy_assignments`; (b) script com a CLI do Azure | (a): prévia, auditoria e repetível |
| D33 | Brechas achadas (escrita só com `read`, exclusão sem departamento, renomear sem dono, `app-role-assignments` sem sessão) | (a) entram na 21, junto com a transição; (b) correção urgente antes, da `master` | (b) para as brechas que expõem escrita hoje, se a transição demorar; senão (a) |
