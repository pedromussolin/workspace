# Instruções comuns aos agentes da PR 5 da tarefa 31 (TS-5427)

Você faz UM pacote da PR 5 da tarefa 31 (TS-5427: funil e cards do orquestrador; D119 em `decisions.md`) no
front, junto com outros agentes que trabalham ao mesmo tempo **na mesma worktree**. Escreva em PT-BR.

## Onde

- Worktree: `~/repos/apl-credit-whitelabel-wt/32`, branch local `tmp/TS-5427-base`,
  saída da `master` de 21/10 (`f7bb2d84`) com um commit local de base (`9180108e`) que traz da PR 1 o `app-trend-kpi`, o `app-sparkline` e a Visão do produto já refeita. Não mexa nesse commit nem crie outros.
- O `node_modules` é um link para o da worktree `release-20261021` (mesmo `package-lock`).
- **Não faça commit.** Deixe as mudanças no working tree, testadas. O usuário revisa antes, e eu
  monto os commits a partir do seu relatório.
- Leia antes `CLAUDE.md` e a `.ai/` da worktree: README, boundaries e as `rules/` que o seu pacote
  toca. Atenção a `rules/angular.md`: código e comentário novos em inglês; texto de tela e descrição
  de teste em português.
- Requisitos permanentes do portal: responsivo até ~400 px, claro e escuro, Chrome/Edge/Safari
  (conferir suporte de CSS no Safari), APIs modernas do Angular (`input()`, `output()`, signals,
  `host`), nada de Angular Material, padrão novo nasce em `shared/ui`, componente mexido sai com spec
  de comportamento.

## Arquivos

- Cada pacote recebe uma lista de pastas e arquivos. **Só edite o que está na sua lista.** Outros
  agentes editam o resto ao mesmo tempo.
- Se precisar mudar algo fora da lista, não mexa: descreva no relatório, com o texto pronto.
- Arquivo compartilhado que a sua lista permite (ex.: `.ai/rules/components.md`, `_tokens.scss`,
  `check-patterns.mjs`):
  - releia antes de cada edição;
  - edite só o seu trecho, com `Edit`;
  - se a edição não aplicar porque o arquivo mudou, releia e refaça.

## Máquina: memória e processos

São 23 GB de RAM e 8 CPUs, divididos entre até cinco agentes. Já houve queda da máquina inteira
por falta de memória.

- **Comando pesado** passa pelo limitador, que deixa dois de cada vez entre todos os agentes. Vale
  para `ng build`, `ng test`, `ng lint` e script com Playwright:

  ```bash
  SLOT=~/repos/.reestrutura_whitelabel/ng-slot.sh
  CHROME=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
  $SLOT npx ng build --output-path <sua-pasta>/dist
  $SLOT env CHROME_BIN=$CHROME npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/<pasta>/**/*.spec.ts'
  $SLOT node <seu-script-playwright>.mjs
  npx tsc -p tsconfig.app.json --noEmit   # leve, sem limitador
  ```

- Builde a cada 2 ou 3 etapas, não a cada edição. Lint completo uma vez, no fim.
- **Rascunho, cópias e builds** ficam em `~/repos/.reestrutura_whitelabel/agentes/t5427-<pacote>/`,
  nunca em `/tmp`. Apague no fim (cópia isolada com `git worktree remove`).
- **Um navegador por vez**, fechado no fim de cada script. Servidor seu só enquanto o script roda.
- **Portas:** 4300 e 8765 são do portal do usuário; não use. Faixas: E 4660–4669, F 4670–4679.
- **Testes:** rode só os specs dos arquivos que você mexeu. A suíte inteira, o lint completo e o
  smoke são meus, na revisão.
- **Compilação quebrada pelo trabalho de outro agente:** o `ng test --include` compila todos os specs.
  Use uma cópia isolada:

  ```bash
  git -C ~/repos/apl-credit-whitelabel-wt/32 worktree add --detach ~/repos/.reestrutura_whitelabel/agentes/t5427-<pacote>/wt HEAD
  ln -s ~/repos/apl-credit-whitelabel-wt/release-20261021/node_modules ~/repos/.reestrutura_whitelabel/agentes/t5427-<pacote>/wt/node_modules
  ```

  Copie para ela as suas mudanças (e as dos outros que compilam).

## Ver o "depois" no navegador

- Build seu com `--output-path` na sua pasta, servido por um servidor estático seu na sua faixa.
- A API responde com `page.route`, a partir de
  `~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json`. Veja como
  `~/repos/workspace/projects/whitelabel-restructure/attachments/scripts/smoke.mjs` monta o BFF falso, o `env.js` e o
  `iam/paths`. Dados da Visão do produto: `~/repos/.reestrutura_whitelabel/agentes/t31-repro/fixtures.json`.
- `playwright-core` vem de `~/repos/.reestrutura_whitelabel/pw/node_modules`, via `createRequire`.
- Antes de entregar: prints do depois em claro, escuro e celular (400 px), com dados, em
  `~/repos/.reestrutura_whitelabel/evidencias/5427/<pacote>/`.

## Padrões já decididos no portal (não desfaça)

- Botões, chips e pílulas tom sobre tom; nada de preenchido sólido com texto branco.
- Texto que não cabe: reticências dentro do padding + tooltip com o texto inteiro.
- Alinhamento em tabela: texto à esquerda, números à direita, status no centro, ações à direita.
- Tabela no cartão vai de borda a borda (`--app-table-edge`).
- Cor da marca em indicador sólido: `--brand-icon`.
- Barra de rolagem só pelo `ui.scrollbar-discreet`.
- Tudo que abre e fecha tem animação curta, respeitando `prefers-reduced-motion`.

## Relatório final (última mensagem)

1. O que mudou, por item, com os arquivos.
2. Mudanças visíveis (antes → depois) e o que ficou igual de propósito.
3. Testes: o que falhava antes e passa agora, e os comandos.
4. O que ficou fora da sua lista, com o texto pronto (inclusive para a `.ai/`).
5. Commits sugeridos: `tipo(TS-5427): mensagem`, em PT-BR, com até 72 caracteres contando o
   prefixo, sem `Co-Authored-By`. Um por item ou passo lógico, cada um compilando sozinho, com os
   arquivos de cada um. Diga onde vai precisar de `git add -p`.

## Regra desta PR (do dono, 23/10)

- **Só o que está no protótipo** (https://claude.ai/artifact/JRDepR2PsBW4Tt5Cqd1atf): cards do resumo das
  Execuções, o funil único (Etapas/Faixas) nas Execuções (Flows e Processos) e na Visão do produto, e o
  painel lateral do funil nas Execuções.
- **O que não foi discutido não muda**: listas de flows e de processos (copiar ID, abrir em nova aba,
  reprocessar, acordeões), barra de filtros, filtros avançados, banner da população, rotas, URL,
  parâmetros, endpoints, contrato com o BFF e o fluxo de pedidos dos stores. Mesmas informações de hoje.
- Na dúvida entre o protótipo e o comportamento de hoje, mantenha o de hoje e descreva no relatório.
