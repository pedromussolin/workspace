# 11 — Onboarding BGT, Usuários, Clientes e Simulação

- **TS:** TS-5368 · **Branch:** `refact/TS-5368-onboarding-usuarios-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** publicada (15/10), sem merge em ambiente
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/onboarding-bgt` | `pages/onboarding-bgt/listing/` |
| `/onboarding-bgt/monitoring` | `pages/onboarding-bgt/monitoring/` |
| `/onboarding-bgt/:id` | `pages/onboarding-bgt/detail/` |
| `/users` | `pages/users/users-list/` |
| `/users/:ecid` | `pages/users/user-detail/` |
| `/clients` | `pages/clients/` |
| `/simulate-proposal` | `pages/simulate-proposal/` (usa `components/forms/form-simulation`) |

## O que vai para `features/`

- `features/onboarding-bgt/`: telas, `services/onboarding.service.ts` e
  `interfaces/onboarding.interface.ts`.
- `features/users/`: telas, `onboarding-status-chip`,
  `services/users.service.ts` e `interfaces/users.interface.ts`.
- `features/clients/` e `features/simulate-proposal/`. O
  `form-simulation` vai junto, se só a simulação usar.

Inventário (`d0bc3de`): 22 arquivos, 4.941 linhas, 191 cores fixas, 2 specs.
Material: spinner (4), icon (4), tooltip (3), snack-bar (3), select (2),
table, paginator, checkbox e button.

## Fluxos críticos

- Monitoramento: cards por situação (`thumb_up`, `thumb_down`, `gavel`,
  `verified`, `cloud_off`), reprocessar em lote (TS-5254, merge em 09/10).
- Detalhe: papéis (consignante, tomador) com ícone próprio.
- Usuários: listagem, detalhe e status de onboarding.

## Pontos de atenção

- Depende da decisão D7 (onde fica o `product.service`).

## O que foi feito (15/10/2026)

Branch `refact/TS-5368-onboarding-usuarios-nova-arquitetura`, criada da 04
com as três correções de 15/10. São 24 commits.

| Commits | O quê |
|---|---|
| `f5c4bf3`, `f8040e7` | move as quatro áreas para `features/` (onboarding-bgt, users, clients, simulate-proposal), cada uma com `data-access/` e `routes.ts` com `loadChildren`. URLs, guards e trilhas iguais |
| `f5e87a5`, `e52752f`, `56b8f22`, `9e25379` | cópias (cherry-pick) das peças comuns da 05, com conteúdo idêntico |
| `b3b23fc` | `SearchTableConfig.dataSource` sem o tipo do Material. Esse arquivo fica fora da área; o outro uso dele continua compatível |
| `4b371fa` … `f97ec29` | usuários, clientes, simulação e onboarding (listagem, monitoramento e detalhe) em componentes, signals, OnPush e tokens, sem Material |
| `b69f685` | produtos sem lista não derrubam mais a listagem e o monitoramento. Antes, o shell inteiro parava de desenhar (sidebar vazia) |
| `62aded6` | `.app-input-icon` em `_forms.scss`: ícone dentro do campo, usado nos filtros |
| `ccf96df` | a barra de ações em lote tem animação de saída e respeita movimento reduzido |
| `0d490d5` | clicar no atalho de período já ativo volta a recarregar, como antes |
| `e06e4f7`, `6d14a5b` | cada status interno tem o seu ícone; "Não aceito" e "Em andamento" ficam distinguíveis no mesmo tom |
| `f1e481f` | lista de usuários direto em `shared/ui`, sem `app-search-table` nem `app-combobox-component` |

**Mudanças visíveis para listar na PR:**
- **Pílulas:**
  - as pílulas de status são tonais;
  - os antigos laranja e amarelo viraram o tom de atenção, diferenciados
    pelo ícone;
  - o chip de onboarding do usuário perdeu o ponto inicial e virou pílula.
- **Status BGT na listagem:** traduz mais códigos (ex.: `APPROVED` mostra
  "Aprovado"), com o mesmo mapa do detalhe.
- **Toasts:** usam o toast comum, colorido pelo tipo. O reprocessamento em
  lote mostra sucesso ou aviso, conforme alguma falha.
- **Detalhe do usuário:** o cabeçalho deixou de ser uma barra de cor sólida
  com texto branco. Valores longos terminam em reticências, com tooltip.
- **Funil do monitoramento:** os cards são o KPI comum, com "Clique para
  filtrar a lista". A descrição de cada card foi para um tooltip.
- **Listagem:** o `hasActiveFilters` passou a reagir aos filtros. Antes ele
  ficava desatualizado e afetava a oferta "todos do filtro" e o texto do
  estado vazio.
- **Lista de usuários:**
  - a barra de busca fica visível durante a carga e no erro, então dá para
    tentar de novo;
  - o estado vazio é o comum.

Ficou de fora, a decidir: os títulos fora do padrão (A15).

**Validação** (base: a 04 com as três correções, 678 testes com 77 falhando e lint 59/281):

| Item | 11 |
|---|---|
| Build | ok |
| Lint | 58 erros / 262 avisos |
| Testes | 876, com 77 falhando, nenhuma falha nova. Specs das quatro áreas: 184/184 |
| Smoke (mock) | rotas principais no desktop e no celular, sem erro de página; a sidebar volta a carregar no `/onboarding-bgt` |
