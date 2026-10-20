# Instruções comuns aos agentes da organização e cliente (tarefa 27, TS-5407)

Você faz uma parte do plano `tarefas/27-organizacao-e-cliente-plano.md` (leia também a spec
`tarefas/27-organizacao-e-cliente.md`), ao mesmo tempo que outro agente. Escreva em PT-BR.

## Onde

| Repo | Worktree | Branch |
|---|---|---|
| BFF (FastAPI) | `~/repos/apl-credit-whitelabel-api-wt/27` | `feature/TS-5407-organizacao-e-cliente` |
| Front (Angular 20) | `~/repos/apl-credit-whitelabel-wt/27` | `feature/TS-5407-organizacao-e-cliente` |

- **Não faça commit, push, stash nem checkout.** Deixe as mudanças no working tree, testadas.
- BFF: siga o estilo do módulo `src/modules/access_control` (da 26). Venv `~/.venvs/whitelabel-api`
  (pytest, ruff, black). Comentário só para um porquê; nada de comentário divisor. Logs como eventos:
  mensagem fixa, dimensões no `extra`. **Nunca banco de dados**; cache só no `AccessControlCache`.
- Front: leia `CLAUDE.md` e a `.ai/` da worktree (README, `boundaries.md`, as `rules/` que tocar e
  `context/reference-screens.md`, seção Controle de acesso). Só peças de `shared/ui`; precisou mudar
  `shared/ui`, não mexa: descreva no relatório. Código e comentário em inglês; texto de tela e
  descrição de teste em português.
- Os textos fixos do plano (motivos, avisos, rótulos) são exatos.

## Máquina

- Comando pesado pelo limitador, dois de cada vez entre todos:
  ```bash
  SLOT=~/repos/.reestrutura_whitelabel/ng-slot.sh
  CHROME=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
  $SLOT env CHROME_BIN=$CHROME npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/access-control/**/*.spec.ts'
  npx tsc -p tsconfig.app.json --noEmit
  node .ai/scripts/check-patterns.mjs
  ```
- Portas 4300 e 8765 são do portal do usuário: não use. Front, se precisar de navegador: 4520–4529,
  um navegador por vez, fechado no fim. Nada de `ng build` na worktree (o `main` faz).
- Rascunho em `~/repos/.reestrutura_whitelabel/agentes/27-<sua-parte>/`, nunca em `/tmp`; apague no fim.

## Relatório final (última mensagem, curto)

1. Por tarefa do plano: o que mudou e os arquivos.
2. Decisões que o plano deixou abertas e o que você escolheu.
3. Testes: comandos e resultado (`TOTAL`/`passed`), lint e formatação.
4. O que ficou fora da sua lista, com o texto pronto.
5. Commits sugeridos, com os arquivos de cada um.
