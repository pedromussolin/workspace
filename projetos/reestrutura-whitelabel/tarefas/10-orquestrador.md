# 10 — Orquestrador

- **TS:** TS-5367 · **Branch:** `refact/TS-5367-orquestrador-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** a iniciar
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/orchestrator` | `pages/orchestrator/orchestrator/` (com funil e detalhe de processo) |
| `/orchestrator/flow/:flowId` | `pages/orchestrator/flow-detail/` |
| `/orchestrator/product-config` | `pages/orchestrator/product-config/list/` |
| `/orchestrator/product-config/:id` | `pages/orchestrator/product-config/edit/` |

## O que vai para `features/orchestrator/`

- As quatro telas.
- `services/orchestrator.service.ts` e `interfaces/orchestrator.interface.ts`.
- `components/entity-drawer`: só é usado pelo `product-config-edit` e
  depende do `product.service`. É componente da feature, não genérico.
- `services/product.service.ts` e `interfaces/product-config.interface.ts`
  são usados também por onboarding-bgt e users. Ver a decisão D7.

Inventário (`d0bc3de`): 18 arquivos, 6.743 linhas, **382 cores fixas**, 1
`::ng-deep`, **0 specs**. Material: tooltip (5), spinner (5), icon (5),
snack-bar (4), select (3), table, paginator, form-field e expansion.

## Fluxos críticos

- Listagem e funil por status. O mapa status → ícone e classe passa a usar
  `IconName` e os semânticos.
- Detalhe de fluxo com subfluxos e processos.
- Config de produto: os toggles (`toggle_on` e `toggle_off` desenhados como
  ícone viram um switch de verdade, com `role="switch"`) e o salvamento.

## Pontos de atenção

- Sem nenhum spec. Antes de mexer, escrever specs mínimos para o mapeamento
  de status e para o salvamento da config de produto, e só então refatorar.
