# 16 — E2E, cobertura e regressão visual

> **Adiada (11/10/2026):** workflows, E2E, cobertura no CI e CI/CD ficam para depois; o Pietro vai fazer com o time de infraestrutura. D9 segue em aberto.

- **TS:** a criar · **Branch:** `test/TS-?-e2e-cobertura-regressao-visual`
- **Status:** adiada. O Pietro faz depois, com o time de infraestrutura. O protótipo do smoke já roda: [attachments/scripts/smoke.mjs](../attachments/scripts/smoke.mjs)
- **Depende de:** 01. Decisão D9.

## Escopo

1. **E2E com Playwright** no repo do front (`e2e/`):
   - projetos Chromium (Chrome/Edge) e WebKit (Safari), cada um em desktop
     (1440×900) e celular (390×844);
   - BFF falso: sessão válida, permissões configuráveis por teste e dados de
     exemplo por tela;
   - roteiro mínimo:
     - login e redirecionamentos (sem sessão, sem permissão, rota
       inexistente);
     - abrir cada rota do menu;
     - navegação interna mantendo o shell;
     - trocar tema e esquema (depois da 02).
2. **Regressão visual:** `toHaveScreenshot` do Playwright em cada rota, nas
   4 combinações (Poliedro claro e escuro, Dots claro, celular). As imagens
   de referência ficam versionadas. Mudança visual intencional atualiza a
   referência no mesmo PR.
3. **Cobertura:**
   - Karma com `--code-coverage`;
   - limite mínimo para `shared/ui` e `core/` (proposta: 80% de linhas);
   - o resto do projeto sobe junto com as tarefas de área.
4. **CI** (ver [findings.md](../findings.md) A9):
   - incluir `refact/*`, `chore/*`, `fix/*` e `test/*` nos gatilhos;
   - job com testes unitários, cobertura e E2E (D9).

## Pontos de atenção

- O WebKit do Playwright é o mais próximo do Safari que roda no Linux do CI,
  mas não é o Safari. Antes de cada PR grande de UI, vale um teste manual
  num Mac ou iPhone.
- A 16 pode andar em paralelo com 02–04, e as tarefas de área já ganham E2E
  da própria tela.
