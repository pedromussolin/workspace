# 05 — Pré-Trade

- **TS:** TS-5362 · **Branch:** `refact/TS-5362-pre-trade-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** commits feitos, sem push (13/10)
- **Depende de:** 04
- **Passos e critério de pronto:** [area-playbook.md](area-playbook.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/pre-trade` | `pages/pre-trade/pre-trade.page` |
| `/pre-trade/:key` | `pages/pre-trade/details/pre-trade-details.page` |

## O que entra em `features/pre-trade/`

- `pages/pre-trade/**`: página, detalhe, `components/`, `dialogs/`,
  `pre-trade.workflow.ts`, `pre-trade.labels.ts` e `attachment-type.ts`.
- `services/management/pre-trade.service.ts` → `data-access/pre-trade-api.service.ts`.
- `interfaces/management/pre-trade.interface.ts` → `data-access/pre-trade.dto.ts`.

Inventário (`d0bc3de`): 65 arquivos, 14.103 linhas, **583 cores fixas**, 9
`::ng-deep`, 3 specs. Material: icon (15), dialog (5), snack-bar (3),
tooltip e table.

## Fluxos críticos

- Listagem com cards de resumo, filtros, selo "Aguardando você" e estado vazio.
- Criar, editar, aprovar, devolver e reprovar (diálogos), com permissão por
  escopo (`iam.authorizeActions`).
- Detalhe: barra de etapas, histórico, anexos (arrastar, enviar, baixar),
  prazo vivo e comemoração na última etapa.
- Animações: respeitar `prefers-reduced-motion`. A versão reduzida usa só
  opacidade e não deixa nada parado pela metade.

## Pontos de atenção

- É a referência visual. Os tokens da 02 saíram daqui, então a tela tem que
  ficar visualmente **igual** no tema Poliedro claro. Comparar com print de
  antes.
- As cores de status do Pré-Trade e as do histórico passam a usar os
  semânticos (`--success`, `--warning`...).
- Specs: só 3. Vale um spec para `pre-trade.workflow.ts`, que decide etapa e
  ações.

## O que foi feito

Branch `refact/TS-5362-pre-trade-nova-arquitetura`, criada a partir da 04
(`feature/TS-5361-componentes-overlay-tabela`). São 15 commits, todos sem push:

| Commit | O quê |
|---|---|
| 94fdff3, 2daef65 | move para `features/pre-trade` (+ `data-access/`) e rotas com `loadChildren` |
| 9e5ee6c, 1216d00, be40f92 | `shared/ui`: select com limpar e opção com ícone, multiselect com busca, pílula, indicador e estado vazio |
| f34dc83, 688cef6, 669c6a4 | tela sobre `shared/ui` sem Material, estilos só com tokens, texto único para valor vazio |
| 4848b2f, f160a89 | modelo, regras da lista e visão do detalhe separados; peças comuns da prévia e do detalhe extraídas |
| 129bee4 | celebração fecha por Enter/Esc; o fade de opacidade vale também com movimento reduzido |
| fe152a7, 0748ee6, 231ed4d, 87ef8c8 | specs de fluxo, diálogos, página de detalhe, mapper e componentes visuais |

**Mudanças visíveis para listar na PR:**
- A celebração agora fecha pelo teclado (Enter/Esc).
- Com movimento reduzido, a celebração só faz o fade de opacidade. Antes não havia
  animação nenhuma.
- Componentes próprios no lugar do Material (select, multiselect, datas, pílulas,
  estado vazio), com o visual tonal do design system.

**Validação:**

| Item | 04 (base) | 05 |
|---|---|---|
| Build | ok | ok |
| Lint | 59 erros / 281 avisos | 59 erros / 266 avisos |
| Testes | 674, 76 falhando | 822, 76 falhando, nenhuma falha nova (specs do Pré-Trade: 160/160) |
| Smoke (mock) | 29 rotas | 29 rotas, sem erro de página |
