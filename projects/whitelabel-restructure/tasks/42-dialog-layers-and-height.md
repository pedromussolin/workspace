# 42 — Tags sobre o rodapé e altura padrão dos modais

- **TS:** TS-5491 (épico TS-5357) · **Branch:** `fix/TS-5491-tags-e-altura-dos-modais` (front), da `master`
- **Status:** **na `release/20261030`** (30/10): 2 commits; sandbox PR #252, release PR #254; `validate.sh` ok, 5020 testes.

## O que aconteceu

- No formulário do Pré-Trade, a tag "Pendente" de um acordeão passava por cima do botão "Salvar e enviar para
  aprovação" ao rolar. O lado direito do cabeçalho do acordeão tem `z-index: 1` (fica acima do botão que cobre a
  linha) e as ações presas do diálogo não tinham `z-index`.
- O diálogo centralizado crescia até 16 px das bordas antes de rolar. Os do Pré-Trade usam `100vh - 128px` e o
  Pietro quis isso como padrão.

## O que mudou

- Acordeão e corpo do diálogo com `isolation: isolate`; ações presas com `z-index: 1`.
- Altura máxima padrão do diálogo centralizado: `calc(100dvh - var(--app-dialog-gutter-block, 128px))`, com a
  variável em 32 px abaixo de 600 px. Centralizado (escolha do Pietro, não preso ao topo como o Pré-Trade).
- `.ai/rules/components.md`: "Altura do diálogo" e "Camada própria".

## Validação

- 3 testes novos (diálogo e acordeão), todos falhando com os estilos da `master`.
- Portal local, imagem atual e nova lado a lado: com a `master` a tag fica por cima do rodapé e do cabeçalho; com a
  correção, não. Diálogo longo a 64 px das bordas (16 px antes).
