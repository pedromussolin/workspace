# 11 — Onboarding BGT, Usuários, Clientes e Simulação

- **TS:** TS-5368 · **Branch:** `refact/TS-5368-onboarding-usuarios-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** a iniciar
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
