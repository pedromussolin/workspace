# 25 / R61 — Teste local que guarda as mudanças (BFF falso e navegador)

- **TS:** TS-5395 · **Status:** **feito e publicado** (20/10): parte 1 (BFF falso) neste repo; parte 2 (navegador) na TS-5395 (`b8a02a7f`), levada à 26 e à 27 por merge
- **Pedido do Pietro (20/10):** rodando local, dá para sair e ver o login (feito no portal local:
  "Sair" encerra a sessão, "Entrar com Microsoft" volta logado sem Azure); e o que se muda nos testes
  locais tem que ficar guardado. **Padrão: o BFF falso** (testes com a integração); **reserva: o
  navegador** (testes só do front).

## Regras de escrita (as duas camadas seguem as mesmas)

Os dados são um mapa `{ "caminho/da/api": resposta }` (o formato do `smoke-data`).

**Controle de acesso** (`access-control/batch/preview` e `batch/apply`, corpo `{ operations,
confirm? }`): cada operação vira um item `{ index, type, label, action, reason? }` e o `summary`
conta por `action`. O `apply` devolve os mesmos itens com `status` (`ok`, `skipped` ou `failed`) e
**muda os dados**:

| Operação | Ação na prévia | O que o apply muda |
|---|---|---|
| `create_role` | `create`; `skip` "Já existe no Azure." se a permissão já existe | a permissão em `access-control/roles` (`inAzure: true`) e o `holders` vazio |
| `create_group` | `create`; `skip` se já há grupo com o nome | o grupo em `access-control/groups` (dono: o app) e o `groups/<id>` |
| `assign_role` | `assign`; `skip` "Já tem." | a permissão no `people/<id>` (via `direct`) ou no grupo; `roleCount`, `peopleCount` e `holders` |
| `add_member` | `add`; `skip` "Já é membro." | o membro no `groups/<id>`, `memberCount`, os grupos da pessoa e os `holders` das permissões do grupo |
| `remove_assignment` / `remove_member` | `remove`; `skip` se não tem | o inverso das duas acima |
| `delete_role` / `delete_group` | `delete` | some de todas as listas e detalhes |
| `copy_assignments` | `assign` para cada um que tem a de origem | como `assign_role` |
| `set_person_scope` | `update`; `skip` "Já está com essa organização e esse cliente." | `organization`, `clientId`, `clientName` e `scopeState` na lista e no detalhe |

Pessoa e grupo citados por e-mail ou nome são achados nos dados; não achados: `blocked` com o motivo.

**Listas em geral** (o resto):
- `POST caminho` com uma lista em `caminho` (array, `{ records }` ou `{ items }`): acrescenta o corpo
  com um `id` novo e devolve o item.
- `PATCH`/`PUT caminho/<id>`: acha o item pelo `id` (ou `key`) na lista de `caminho` e junta o corpo;
  se existir o detalhe `caminho/<id>`, junta nele também.
- `DELETE caminho/<id>`: tira da lista e apaga o detalhe.
- Contadores da resposta (`total`, `pagination.total_count`) acompanham.
- Sem regra: responde como hoje e avisa ("escrita sem efeito: <método> <caminho>").

## 1. BFF falso (portal local, `anexos/scripts/smoke.mjs`)

- As mudanças vão para uma cópia dos dados em `$PRIV/smoke-dados/alteracoes/<nome-do-arquivo>.json`:
  sobrevivem a recarregar e a reiniciar o portal. Com a cópia, ela vale mais que o arquivo original.
- `http://localhost:4300/__reset` apaga a cópia e volta aos dados originais (página curta dizendo isso).
- O smoke (prints) nunca escreve na cópia: só o `SERVE=1` (portal local) guarda.

## 2. Navegador (`npm start` sem BFF, código do front)

- `MOCK_API=true` faz o `scripts/generate-env.js` gravar `mockApi: true` no `env.js` (padrão:
  `false`). O `entrypoint.sh` não conhece a variável: no container é sempre `false`.
- Com `mockApi` e sem `production`, o `app.config` registra o interceptor
  `core/http/mock-api/mock-api.interceptor.ts`, que responde às chamadas ao `apiUrl` a partir dos
  `.ai/scripts/smoke-data/*.json` (servidos só no build `development`, pelo `angular.json`, em
  `mock-api/`) e guarda as escritas no `localStorage` (`portal.mock-api`), com as regras acima e as
  respostas do IAM do `.ai/scripts/smoke.mjs`.
- Sessão: `iam/status` lê `portal.mock-api.session`; `auth/logout` desliga; no login, com
  `mockApi`, o `AuthService.login` liga a sessão e vai para a home em vez de ir ao BFF.
- Voltar ao original: `?mock-reset` em qualquer URL, ou apagar a chave no navegador.
- Um script `npm run start:mock` (sem variável na linha, para funcionar no Windows e no WSL).
- `.ai`: como rodar só o front com dados, no `README.md` da `.ai` e em `context/bff.md` ("Sem BFF").

## Validação

Specs das regras (funções puras, as mesmas tabelas acima), do interceptor (respostas, escrita
guardada, reset, sessão) e do `generate-env`; o build de produção não leva o interceptor ativo nem
os JSON; smoke do portal local fazendo uma mudança no controle de acesso, recarregando e vendo a
mudança, e o `__reset` voltando.

## O que foi feito

**Parte 1 (20/10):** regras em `anexos/scripts/smoke-escrita.mjs` (funções puras e o `createDataStore`),
usadas pelo `smoke.mjs`; 30 testes em `smoke-escrita.test.mjs` (`node --test`). Prévia e aplicar usam
as mesmas regras sobre uma cópia, então `create_role` seguido de `assign_role` no mesmo lote funciona.
Os contadores, as permissões herdadas e os `holders` são derivados a cada escrita (rodar a derivação
sobre os dados atuais não muda nenhuma das 135 chaves). No aplicar, `blocked` vira `failed` com o
motivo. Decisões fora da tabela: textos "Já existe um grupo com esse nome.", "Não tem.", "Não é
membro.", "Permissão não encontrada.", "Pessoa não encontrada.", "Grupo não encontrado."; atribuir
permissão que não existe no Azure bloqueia; buscas por POST (`pre-trade/investor-vehicles`,
`pre-trade/assets`) ficam sem regra (`SEARCH_POSTS`); fora da prévia e do aplicar, escrever em
`access-control/` fica sem regra. Limites: não confere o `confirm: 'REMOVER'`; não bloqueia o que o
BFF real bloqueia por configuração (`deletable`, `groupAssignmentEnabled`, `canEditPartner`); o POST
genérico não cria o detalhe; o DELETE genérico não apaga subcaminhos.

**Parte 2 (20/10):** `core/http/mock-api/` com 122 testes (regras de lista e do controle de acesso,
interceptor, estado, sessão e reset). O `app.config` e o interceptor usam a mesma função
(`isMockApiEnabled`): só liga com `mockApi` e sem `production`. O build de produção não leva os
JSON. Checagem nova no `check-patterns` (`mock-api-fora-da-lista`): arquivo de `smoke-data` fora
da lista do mock falha. Na 26, que tem `access-control.json`, o arquivo entrou na lista e o README
da `.ai` deixou de dizer que não há dados do controle de acesso.
