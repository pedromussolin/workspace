# Instruções comuns aos agentes do controle de acesso (tarefa 26, TS-5405)

Você faz UMA parte do plano `tasks/26-access-control-ux-plan.md` (leia também a spec
`tasks/26-access-control-ux.md`), junto com outros agentes que trabalham ao mesmo tempo. Escreva
em PT-BR.

## Onde

| Repo | Worktree | Branch |
|---|---|---|
| Front (Angular 20) | `~/repos/apl-credit-whitelabel-wt/26` | `feature/TS-5405-controle-de-acesso-ux` |
| BFF (FastAPI) | `~/repos/apl-credit-whitelabel-api-wt/26` | `feature/TS-5405-controle-de-acesso-ux` |

- **Não faça commit nem push.** Deixe as mudanças no working tree, testadas. O usuário revisa antes, e
  o `main` monta os commits a partir do seu relatório.
- Front: leia `CLAUDE.md` e a `.ai/` da worktree (README, `boundaries.md` e as `rules/` que a sua
  parte toca). Código e comentário novos em inglês; texto de tela e descrição de teste em português.
  Só peças de `shared/ui`; se precisar de peça nova ou de mudar uma de `shared/ui`, não mexa:
  descreva no relatório.
- BFF: siga o estilo do módulo `src/modules/access_control`. Venv: `~/.venvs/whitelabel-api`
  (pytest, ruff, black). O projeto não usa mypy. Comentário só para um porquê; nada de comentário
  divisor. Logs como eventos: mensagem fixa, dimensões no `extra`.
- **O BFF nunca tem banco de dados.** Cache só no Redis que já existe, com validade.

## Arquivos

- Cada parte recebe uma lista de pastas e arquivos. **Só edite o que está na sua lista.** Se precisar
  mudar algo fora dela, não mexa: descreva no relatório, com o texto pronto.
- Arquivo compartilhado que a sua lista permite: releia antes de cada edição, edite só o seu trecho
  com `Edit` e, se a edição não aplicar porque o arquivo mudou, releia e refaça.

## Máquina: memória e processos

São 23 GB de RAM e 8 CPUs, divididos entre até cinco agentes. Já houve queda da máquina inteira por
falta de memória.

- **Comando pesado** passa pelo limitador (dois de cada vez entre todos): `ng build`, `ng test`,
  `ng lint` e script com Playwright.

  ```bash
  SLOT=~/repos/.reestrutura_whitelabel/ng-slot.sh
  CHROME=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
  $SLOT npx ng build --output-path <sua-pasta>/dist
  $SLOT env CHROME_BIN=$CHROME npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/access-control/**/*.spec.ts'
  npx tsc -p tsconfig.app.json --noEmit   # leve, sem limitador
  ```

- **Rascunho, cópias e builds** em `~/repos/.reestrutura_whitelabel/agentes/<sua-parte>/`, nunca em
  `/tmp`. Apague essa pasta no fim.
- **Um navegador por vez**, fechado no fim de cada script. Servidor seu só enquanto o script roda.
- **Portas:** 4300 e 8765 são do portal do usuário; não pare, não reinicie e não use. Faixas: K
  4510–4519, L 4520–4529, M 4530–4539, N 4540–4549, O 4550–4559.
- **Testes:** rode só os specs do que você mexeu (front: os de `features/access-control`; BFF: a pasta
  `tests/unit/modules/access_control` e os que você criou). A suíte inteira e o smoke são do `main`.

## Ver no navegador (front)

- Build seu com `--output-path` na sua pasta, servido por um servidor estático seu na sua faixa.
- A API responde com `page.route`, a partir de
  `~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json` (cópia na sua pasta; não edite o
  original). Para as rotas novas, monte respostas fictícias no formato do plano. Veja como
  `~/repos/workspace/projects/whitelabel-restructure/attachments/scripts/smoke.mjs` monta o BFF falso, o `env.js` e o
  `iam/paths`.
- `playwright-core` vem de `~/repos/.reestrutura_whitelabel/pw/node_modules`, via `createRequire`.
- Prints em `~/repos/.reestrutura_whitelabel/evidencias/26/<sua-parte>/`.
- Dados fictícios só (nada de CPF, CNPJ ou nome real de cliente).

## Padrões já decididos (não desfaça)

- **Alinhamento:** colunas no centro; ações `align="end"`, com "Ver" por último e o excluir isolado na
  ponta direita (`app-table__destructive-action`); texto corrido de várias linhas à esquerda.
- **Filtros:** `app-filter-bar` com `app-field-grid`; KPI que filtra liga o mesmo filtro.
- **Tabela no cartão:** de borda a borda; 10 por página; lista dentro de modal ou linha com 5
  (`NESTED_TABLE_PAGE_SIZE`).
- **KPIs:** `app-kpi-grid` com `minItemWidth` 240.
- **Cor da marca em indicador sólido:** `--brand-icon`.
- **Ações da página:** na linha do título.

## Relatório final (última mensagem)

1. O que mudou, por tarefa do plano, com os arquivos.
2. Mudanças visíveis (antes → depois) e o que ficou igual de propósito.
3. Testes: o que falhava antes e passa agora, e os comandos.
4. O que ficou fora da sua lista, com o texto pronto.
5. Commits sugeridos: `tipo(TS-5405): mensagem`, PT-BR, até 72 caracteres contando o prefixo, sem
   `Co-Authored-By`, com os arquivos de cada um.
