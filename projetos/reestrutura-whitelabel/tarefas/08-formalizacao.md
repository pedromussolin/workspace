# 08 — Formalização

- **TS:** TS-5365 · **Branch:** `refact/TS-5365-formalizacao-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** a iniciar
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/formalization` | `pages/operations/formalization/formalization.page` |

## O que vai para `features/formalization/`

- A tela.
- `services/operations/formalization/*` e
  `interfaces/operations/formalization/*` → `data-access/`.

Inventário (`d0bc3de`): 6 arquivos, 3.013 linhas (página grande), 138
cores fixas e **nenhum** uso de token, 2 specs. Material: icon, dialog,
tooltip e snack-bar.

## Fluxos críticos

- Listagem com ordenação própria (`sortIcon`, `arrow_upward` e
  `arrow_downward`), filtros e edição.

## Pontos de atenção

- A página tem ordenação feita na mão. Avaliar trocar pelo `appSort` da 04
  **sem** mudar o comportamento, ou deixar como está e anotar.
- É a tela com mais cara de "defasada" (zero tokens hoje). É a que mais vai
  mudar visualmente.
