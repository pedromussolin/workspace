# Instruções comuns aos agentes do refinamento visual (tarefa 25)

Você faz UM pacote de itens da tarefa 25 (`tasks/25-visual-refinement.md`) no front, junto com
outros agentes que trabalham ao mesmo tempo **na mesma worktree**. Escreva em PT-BR.

## Onde

- Worktree: `~/repos/apl-credit-whitelabel-wt/25`, branch `refact/TS-5395-refinamento-visual`.
- **Não faça commit.** Deixe as mudanças no working tree, testadas. O usuário revisa antes, e eu
  monto os commits a partir do seu relatório.
- Leia antes `CLAUDE.md` e a `.ai/` da worktree: README, boundaries e as `rules/` que o seu pacote
  toca. Atenção a `rules/angular.md`: código e comentário novos em inglês; texto de tela e descrição
  de teste em português.

## Arquivos

- Cada pacote recebe uma lista de pastas e arquivos. **Só edite o que está na sua lista.** Outros
  agentes editam o resto ao mesmo tempo.
- Se precisar mudar algo fora da lista, não mexa: descreva no relatório, com o texto pronto.
- Arquivo compartilhado que a sua lista permite (ex.: `.ai/rules/components.md`, `_tokens.scss`):
  - releia antes de cada edição;
  - edite só o seu trecho, com `Edit`;
  - se a edição não aplicar porque o arquivo mudou, releia e refaça.

## Máquina: memória e processos

São 23 GB de RAM e 8 CPUs, divididos entre até cinco agentes. Já houve queda da máquina inteira
por falta de memória.

- **Comando pesado** passa pelo limitador, que deixa dois de cada vez entre todos os agentes. Isso
  vale para `ng build`, `ng test`, `ng lint` e script com Playwright:

  ```bash
  SLOT=~/repos/.reestrutura_whitelabel/ng-slot.sh
  CHROME=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
  $SLOT npx ng build --output-path <sua-pasta>/dist
  $SLOT env CHROME_BIN=$CHROME npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/<pasta>/**/*.spec.ts'
  $SLOT node <seu-script-playwright>.mjs
  npx tsc -p tsconfig.app.json --noEmit   # leve, sem limitador
  ```

- **Rascunho, cópias e builds** ficam em `~/repos/.reestrutura_whitelabel/agentes/<seu-pacote>/`,
  nunca em `/tmp`: o `/tmp` some quando a máquina reinicia. Apague essa pasta no fim (cópia
  isolada com `git worktree remove`).
- **Um navegador por vez**, fechado no fim de cada script. Servidor seu só enquanto o script roda.
- **Portas:** o portal do usuário usa a 4300 e o BFF falso a 8765. Não pare, não reinicie e não use
  essas portas. Cada pacote tem a sua faixa: A 4510–4519, B 4520–4529, C 4530–4539, D 4540–4549,
  E 4550–4559.
- **Testes:** rode só os specs dos arquivos que você mexeu. A suíte inteira, o lint completo e o
  smoke são meus, na validação da rodada.
- **Compilação quebrada pelo trabalho de outro agente:** o build de teste compila o projeto inteiro.
  Use uma cópia isolada:

  ```bash
  git worktree add --detach ~/repos/.reestrutura_whitelabel/agentes/<pacote>/wt HEAD
  ln -s ~/repos/apl-credit-whitelabel-wt/25/node_modules ~/repos/.reestrutura_whitelabel/agentes/<pacote>/wt/node_modules
  ```

  Copie para a cópia isolada as suas mudanças e as dos outros que compilam.

## Ver o "depois" no navegador

- Build seu com `--output-path` na sua pasta, servido por um servidor estático seu na sua faixa de
  portas.
- A API responde com `page.route`, a partir de
  `~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json`. Veja como
  `~/repos/workspace/projects/whitelabel-restructure/attachments/scripts/smoke.mjs` monta o BFF falso, o `env.js` e o
  `iam/paths` (inclua as rotas de que precisar).
- `playwright-core` vem de `~/repos/.reestrutura_whitelabel/pw/node_modules`, via `createRequire`.
- Prints em `~/repos/.reestrutura_whitelabel/evidencias/25-rodada1/<pasta-do-pacote>/`.

## Padrões já decididos nesta rodada (não desfaça)

- **Alinhamento:**
  - texto, nomes e datas à esquerda (padrão do `appColumn`);
  - números à direita;
  - status no centro;
  - ações à direita, com a mais usada por último. A exceção é o **excluir**, que fica sempre na
    ponta direita, isolado.
- **Tabela dentro da linha que abre:** 5 linhas por página (`NESTED_TABLE_PAGE_SIZE`).
- **Tabela no cartão:** vai de borda a borda, com recuo `--app-table-edge` na primeira e na última
  coluna.
- **Cor da marca em indicador sólido** (marcado, ligado, foco, hoje): `--brand-icon`, nunca o
  `--brand-secondary` puro.
- **Barra de rolagem:** só pelo `ui.scrollbar-discreet`.
- **Seletor de visão:** dentro do cartão de filtros, rotulado "Visualização".
- **Ações da página:** na linha do título.
- **Shell:** `.shell__content` é uma coluna flex com a altura da tela.

## Relatório final (última mensagem)

1. O que mudou, por item, com os arquivos.
2. Mudanças visíveis (antes → depois) e o que ficou igual de propósito.
3. Testes: o que falhava antes e passa agora, e os comandos.
4. O que ficou fora da sua lista, com o texto pronto (inclusive para a `.ai/`).
5. Commits sugeridos: `tipo(TS-5395): mensagem`, em PT-BR, com até 72 caracteres contando o
   prefixo, sem `Co-Authored-By`. Um por item ou passo lógico, com os arquivos de cada um. Diga
   onde vai precisar de `git add -p`.
