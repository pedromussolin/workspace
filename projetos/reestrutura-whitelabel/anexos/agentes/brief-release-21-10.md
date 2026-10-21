# Instruções comuns aos agentes das correções da release (21/10)

Você faz UM pacote de correções no front (`apl-credit-whitelabel`), pedidas pelo Pietro depois da
primeira subida da `release/20261021` na sandbox. Outros quatro agentes fazem outros pacotes ao
mesmo tempo, cada um na sua worktree. Escreva o relatório em PT-BR.

## Onde

- **Sua worktree:** `~/repos/.reestrutura_whitelabel/agentes/<pacote>/wt`. É uma cópia isolada,
  sem branch, na ponta da release (`e426aca9`), com o `node_modules` ligado. Só você mexe nela.
- **Não faça commit.** Deixe as mudanças no working tree, testadas. Eu reviso e monto os commits.
- Leia antes `CLAUDE.md` e a `.ai/` da worktree: `README.md`, `boundaries.md` e as `rules/` que o seu
  pacote toca. Em especial `rules/components.md` (tabelas, estados da lista), `rules/styling.md` e
  `rules/angular.md`: código e comentário novos em inglês; texto de tela e descrição de teste em
  português.
- **No BFF** (`apl-credit-whitelabel-api`), nome de teste, docstring e comentário de teste também são em
  inglês, porque são código ([tarefa 30](../../tarefas/30-testes-do-bff-em-ingles.md)). Só as mensagens que o
  teste confere ficam no idioma em que o código as produz.
- As telas de referência são o Pré-Trade e os Lotes de Liquidação (`.ai/context/reference-screens.md`).
- **Só edite as pastas e arquivos da sua lista.** Se precisar mudar algo fora dela, não mexa:
  descreva no relatório, com o texto pronto.

## Máquina

São 23 GB de RAM e 8 CPUs, divididos entre cinco agentes.

- **Comando pesado** passa pelo limitador, que deixa dois de cada vez entre todos:

  ```bash
  SLOT=~/repos/.reestrutura_whitelabel/ng-slot.sh
  CHROME=$(node -e "process.stdout.write(require('playwright-core').chromium.executablePath())")
  $SLOT npx ng build --output-path ~/repos/.reestrutura_whitelabel/agentes/<pacote>/dist
  $SLOT env CHROME_BIN=$CHROME npx ng test --watch=false --include='src/app/<pasta>/**/*.spec.ts'
  npx tsc -p tsconfig.app.json --noEmit     # leve, sem limitador
  node .ai/scripts/check-patterns.mjs       # leve
  ```

- **Rascunho, builds e prints** em `~/repos/.reestrutura_whitelabel/agentes/<pacote>/`, nunca em
  `/tmp`. Não apague a worktree: eu tiro o diff dela.
- **Um navegador por vez**, fechado no fim de cada script.
- **Portas:** não use a 4300 nem a 8765. Cada pacote tem a sua faixa: home 4610–4619, produtos
  4620–4629, relatórios 4630–4639, caixa 4640–4649, pdd-avisos 4650–4659.

## Ver o "depois" no navegador (pacotes visuais)

- O jeito mais curto: o servidor do smoke com as portas trocadas, servindo o seu build:

  ```bash
  P=<primeira porta da sua faixa>; B=$((P+1))
  sed "s/4300/$P/g; s/8765/$B/g" ~/repos/whitelabel-workspace/anexos/scripts/smoke.mjs > ~/repos/.reestrutura_whitelabel/agentes/<pacote>/smoke-$P.mjs
  cp ~/repos/whitelabel-workspace/anexos/scripts/smoke-escrita.mjs ~/repos/.reestrutura_whitelabel/agentes/<pacote>/
  SERVE=1 FIXTURES=~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json \
    PW_DIR=~/repos/.reestrutura_whitelabel/pw/node_modules \
    node ~/repos/.reestrutura_whitelabel/agentes/<pacote>/smoke-$P.mjs <seu dist>/browser "$(mktemp -d -p ~/repos/.reestrutura_whitelabel/agentes/<pacote>)"
  ```

  Rode em segundo plano, tire os prints com um script Playwright seu (`playwright-core` de
  `~/repos/.reestrutura_whitelabel/pw/node_modules`, via `createRequire`; o Chromium pelo `CHROME`
  acima) e pare o servidor no fim.
- Prints do "antes" e do "depois", em claro, escuro e celular (390 px), em
  `~/repos/.reestrutura_whitelabel/evidencias/release-21-10/<pacote>/`. Abra cada print e confira:
  nada cortado, nada sobreposto, sem rolagem lateral.

## Entrega

No fim, responda com:
- o que mudou, arquivo por arquivo, e o porquê;
- os comandos de validação que rodou e o resultado (specs, `tsc`, `check-patterns`, build);
- os caminhos dos prints;
- o que ficou de fora ou precisa de decisão.
