+++
card = "TS-5492"
type = "bug"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 43 — Barras da provisão do PDD com a mesma largura

- **TS:** TS-5492 (épico TS-5357) · **Branch:** `fix/TS-5492-barras-da-provisao-com-mesma-largura` (front), da `master`
- **Status:** **na `release/20261030`** (30/10): 1 commit; sandbox PR #253, release PR #254; `validate.sh` ok, 5018 testes.

## O que aconteceu

Na Conciliação de Estoques e VALIDs (aba Abertura de Rating), o card "Provisão do produto" tem uma barra por rating
com valor e % à direita. Cada linha era uma grade própria com a coluna da direita em `auto`, então cada barra
ficava de um tamanho (801, 810 e 818 px nos dados fictícios).

## O que mudou

- A lista vira grade e cada linha usa `subgrid`: a coluna da direita tem a largura do maior texto e todas as barras
  ficam iguais; valor e % alinhados à direita.
- O outro uso do `app-meter`, no Orquestrador (`bar-row`), já tem colunas fixas e não muda.
- `.ai/rules/components.md`: "Barras lado a lado".

## Validação

1 teste novo (`pdd-tabs.spec.ts`), falhando com o estilo da `master`; portal local com todas as barras em 801 px
(239 px no celular).
