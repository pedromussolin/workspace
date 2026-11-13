+++
card = "TS-5363"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 06 — Lotes de Liquidação, Lotes de Cessão e Detalhe do Contrato

- **TS:** TS-5363 · **Branch:** `refact/TS-5363-lotes-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** commits feitos, sem push (13/10)
- **Depende de:** 04
- **Passos e critério de pronto:** [area-playbook.md](area-playbook.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/liquidation-batches` | `pages/operations/liquidation-batches/` (abas Fechamento de Lotes e Conciliação Manual) |
| `/assignment-batches` | `pages/operations/assignment-batches/` |
| `/contract/details` | `pages/operations/contract-details/` |

## O que vai para `features/`

- `features/liquidation-batches/`:
  - telas, `shared/` (o `_batches-shell.scss` e a toolbar de filtros) e
    `manual-reconciliation/`;
  - `services/operations/{liquidation-batches,manual-reconciliation}/*` →
    `data-access/`;
  - `interfaces/operations/{liquidation-batches,manual-reconciliation}/*` →
    `data-access/`.
- `features/assignment-batches/`:
  - telas, `contract-details/`;
  - `services/operations/assignment-batches/*` e
    `interfaces/operations/assignment-batches/*`.

Inventário (`d0bc3de`): 45 arquivos, 6.913 linhas, 188 cores fixas, 18
`::ng-deep`, 12 specs. Material: snack-bar (7), table (6), paginator (6),
icon (6), tooltip (3), dialog (3).

## Fluxos críticos

- Lotes fake e reais: filtros (o fundo é obrigatório), paginação e
  expansão do lote com a tabela aninhada de pagamentos.
- Fechar lote (fake), conciliação manual: aprovar e reprovar no diálogo de
  revisão, saldo, exportação de rejeitados.
- Cuidado com o Artemis V2: há tarefas abertas nessas mesmas telas (ver
  `../../.artemis_v2/README.md`). Combinar a ordem dos merges para não gerar
  conflito grande.

## Pontos de atenção

- `_batches-shell.scss` tem os overrides da `expandable-table` ancorados em
  seletores de filho. Com a `app-table` da 04, eles devem sumir.
- O mapa `ManualReconciliationStatus` → ícone (`fact_check`, `lock_open`)
  está em `interfaces/`. Ele passa a usar `IconName`.

## O que foi feito

Branch `refact/TS-5363-lotes-nova-arquitetura`, criada a partir da 04. São 18
commits, todos sem push:

| Commit | O quê |
|---|---|
| 804c63f, f488ce7, ca1316c | move lotes e detalhe do contrato para `features/`, rotas com `loadChildren` e specs com HttpClient, rota e escopos |
| 4011eb0, 3acae32, 3228549 | `dataSource` sem tipo do Material, toolbar de filtros e pílula tonal de estado com componentes próprios |
| 4c6e152, 95b5306, 092d21f | fechamento, conciliação manual, cessão e contrato com toast, diálogo, tooltip, skeleton e ícones próprios |
| a415e24, eac0195, 5fb021c | fundos, pagamentos e tabela plana de pagamentos num só lugar para as duas abas |
| 52ded10 | filtros cabem numa linha e quebram sem divisor |
| c53313b, 7037e9e | estado das telas em signals, para atualizar sob o shell OnPush |
| d98d28f, 7c4ec9b, 9fc3b8c | detalhe do contrato com cards e estilos dos lotes só com tokens; spec do skeleton |

**Mudanças visíveis para listar na PR:**
- Os filtros ficam numa linha e quebram sem o divisor.
- A tabela de pagamentos é a mesma, e plana, nas duas abas.
- O detalhe do contrato é montado em cards.
- Toast, diálogo e tooltip são os próprios, no lugar dos do Material.

**Validação:**

| Item | 04 (base) | 06 |
|---|---|---|
| Build | ok | ok |
| Lint | 59 erros / 281 avisos | 42 erros / 251 avisos |
| Testes | 674, 76 falhando | 756, 31 falhando, nenhuma falha nova (specs de lotes: 124/124) |
| Smoke (mock) | 29 rotas | 29 rotas, sem erro de página |

O mock do smoke não tem os escopos dos lotes. Por isso a tela de liquidação
aparece com "sem permissão". A tabela precisa ser conferida no sandbox.
