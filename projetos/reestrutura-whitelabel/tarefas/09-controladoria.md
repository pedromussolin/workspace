# 09 — Controladoria e Consolidação de Caixa

- **TS:** TS-5366 · **Branch:** `refact/TS-5366-controladoria-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** a iniciar
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/cerc-reconciliation` | `pages/controllership/cerc-reconciliation/` |
| `/pdd` | `pages/controllership/pdd/` |
| `/portfolio-performance` | `pages/controllership/portfolio-performance/` |
| `/cash-consolidation` | `pages/management/cash-consolidation/` |
| `/cash-consolidation/:fundName/analytic` | `pages/management/cash-consolidation/analytic/` |

## O que vai para `features/`

- `features/controllership/`: as três telas, com `services/controllership/*`
  e `interfaces/controllership/*` (incluindo os `*.mock.ts`, ver abaixo).
- `features/cash-consolidation/`: as duas telas, com
  `services/management/cash-consolidation.service.ts` e a interface.

Inventário (`d0bc3de`): 31 arquivos, 7.812 linhas, 291 cores fixas, 6
`::ng-deep`, 2 specs. Material: icon, snack-bar, menu, tooltip, table,
spinner, paginator, dialog e button.

## Fluxos críticos

- Gráficos ApexCharts (CERC e Performance): cores dos tokens, refeitos ao
  trocar o esquema, e o redimensionamento (`apx-chart-resize`).
- Alternância de visualização: dashboard, tabela e pendências; gráfico e
  tabela.
- Exportações e filtros por fundo e produto.

## Pontos de atenção

- `cerc-reconciliation.mock.ts` e `stock.mock.ts`: confirmar se ainda são
  usados. Se só servem a teste, vão para junto do spec.
