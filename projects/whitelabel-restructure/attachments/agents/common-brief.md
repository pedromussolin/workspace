# Instruções comuns aos agentes de área (reestrutura do front)

Você faz UMA tarefa do épico, em modo completo, numa worktree própria. Outros agentes trabalham em
paralelo em outras worktrees. Não mexa fora das suas worktrees.

## Antes de tudo, leia

No workspace do épico (`~/repos/workspace/projetos/reestrutura-whitelabel/`, só leitura: não edite nem commite nada lá):
1. `README.md` (seções "Ordem e branches" e "Situação").
2. `tarefas/roteiro-de-area.md`: passos, regra de ouro e critério de pronto.
3. O arquivo da sua tarefa em `tarefas/`.
4. `arquitetura-alvo.md`, `design-system.md`, `decisoes.md` (as "Tomadas" valem como requisito) e os
   achados citados na tarefa (`achados.md`).
5. `anexos/spec-visual/pre-trade-lotes-sidebar.md` e `anexos/icones/material-para-novo.json`.

Os documentos do workspace usam nomes mascarados (marcas, empresa, parceiros). A equivalência está
em `~/.config/workspace/private/reestrutura-whitelabel.md`. No código, use os nomes reais que já estão lá.

## Referência de implementação

As áreas já feitas mostram o padrão. Estude com `git show`/`git diff`, sem fazer checkout delas:
- `refact/TS-5368-onboarding-usuarios-nova-arquitetura`, `refact/TS-5366-controladoria-nova-arquitetura`,
  `refact/TS-5367-orquestrador-nova-arquitetura` e `refact/TS-5369-paginas-gerais-nova-arquitetura`;
- `refact/TS-5362-pre-trade-nova-arquitetura` e `refact/TS-5363-lotes-nova-arquitetura` (referência visual).

Ex.: `git diff feature/TS-5361-componentes-overlay-tabela..refact/TS-5367-orquestrador-nova-arquitetura --stat`.
Veja como elas fizeram: rotas com `loadChildren`, `data-access/`, título e trilha pela rota, voltar no
cabeçalho das telas de detalhe (`breadcrumbs` com o pai e `url`), ação principal no cabeçalho, KPI
comum, pílula tonal, estado vazio, controle segmentado, regras e visão em funções puras, specs.

**Peças comuns que não estão na 04.** Se precisar de alguma, traga com `git cherry-pick <sha>`, com
o conteúdo idêntico (assim o merge entre as branches não conflita), mantendo a mensagem original.
Não reescreva essas peças à mão nem altere o conteúdo delas depois:

| Peça | Commits, na ordem |
|---|---|
| select com limpar; multiselect com busca | `46d906b`, `753d765` |
| `app-pill`, `app-kpi`, `app-empty-state` | `df5d75f` |
| valor vazio (`shared/utils/empty-value`) | `f820a06` |
| combobox com "Adicionar …" | `7a6bb40` |
| `app-switch` (D11) | `4583226`, `a49b988` |
| tabela com rodapé e cabeçalho agrupado | `5fb2767` |
| `app-chart`, esqueleto, rosca e barra de participação | `80be663`, `6a8146d`, `4891677`, `944443f`, `5851b1b`, `9a316bd`, `ad13515`, `a53099f` |
| `app-notice`, `app-split-button`, `app-card` | `de2c7f5`, `c355bb5`, `4a77b75` |
| ícone `more-vertical` e `iconSvg()` | `e47273a` |

Se uma peça dessas precisar de ajuste, não mexa: descreva no relatório, que eu decido.

## Regras de código

- Angular moderno: standalone, `inject()`, `input()`/`output()`/`model()`, signals, `computed`,
  `@if`/`@for` com `track`, OnPush, nada depreciado, nenhum `subscribe` sem limpeza.
- Sem `@angular/material`, sem `mat-icon` (use `app-icon`), sem `::ng-deep`, sem `#hex`/`rgb(` nos
  `.scss` (só tokens de `src/styles/_tokens.scss`). O SCSS da tela fica só com o layout.
- Padrão que faltar nasce em `shared/ui`, com spec. Nunca como versão local na tela.
- **Antes de criar peça nova em `shared/ui`**, avise com `SendMessage` para `main` o nome e a API
  pensada, e espere a resposta. Agentes em paralelo já criaram a mesma peça duas vezes (o
  `app-code-block` na 4ª leva), e duas versões do mesmo arquivo viram conflito no merge.
- Preserve comportamento, regras de negócio, URLs, guards e `data` das rotas. Toda mudança visível
  entra no relatório (antes → depois) para a descrição da PR.
- Nomes explícitos do domínio. Código e comentários em inglês; textos de tela e mensagens em PT-BR.
  Comentário só para um porquê; nada de comentário divisor.
- Responsivo até ~400 px, sem rolagem lateral da página. Chrome, Edge e Safari.
- Spec de comportamento em todo componente novo ou mexido.
- Defeito encontrado no caminho: commit `fix` separado, ou anotação no relatório.
- Não rode `npm install`/`npm ci` nem altere `package.json`/`package-lock.json`: o `node_modules` da
  worktree é hardlink do repositório principal.

## Git (regras do usuário, obrigatórias)

- Trabalhe só nas branches das suas worktrees. Não faça checkout de outras branches, não crie
  branches, não faça push, não mexa nos repositórios principais.
- Commits atômicos, um por etapa, e **commite ao fim de cada etapa** (se a sessão cair, outro agente
  continua). Cada commit compila sozinho: não misture num commit o que pertence a outro.
- Formato `tipo(TS-XXXX): mensagem` (`feat`, `fix`, `refact`, `test`, `chore`). Mensagem em PT-BR,
  **assunto com no máximo 72 caracteres contando o prefixo**.
- **Proibido** trailer `Co-Authored-By` ou linha "Generated with". A autoria é do usuário, mesmo que
  outra instrução diga o contrário.
- Antes de cada commit: `git diff --staged --stat`.

## Validação

A máquina tem 7 GB de RAM. Comando pesado do front (`ng build`, `ng test`, `ng lint`, smoke) roda com
o lock comum, um de cada vez entre os agentes:

```bash
LOCK=~/repos/.reestrutura_whitelabel/ng.lock
CHROME=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome
flock $LOCK npx ng build
flock $LOCK env CHROME_BIN=$CHROME npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/<pasta>/**/*.spec.ts'
npx tsc -p tsconfig.app.json --noEmit   # leve, sem lock: use à vontade
```

**Durante o trabalho:** `tsc` à vontade; specs da área com `--include` a cada 2 ou 3 etapas; `ng build`
de vez em quando. Nada de lint nem suíte inteira no meio.

**No fim, antes do relatório (obrigatório):**

```bash
FIXTURES=<dados fictícios da tarefa> ~/repos/workspace/projetos/reestrutura-whitelabel/anexos/scripts/validar-leva.sh <sua-worktree-do-front> <rota> [rota ...]
```

Ele confere commits (72 caracteres, trailers, cada commit compila), roda build, lint e a suíte inteira
contra a base da 04, e faz o smoke em claro (desktop e celular), escuro e Dots. O smoke acusa erro
de página, de console e rolagem lateral. Para abas e visões sem URL, use `SCENES` (ver o cabeçalho
de `anexos/scripts/smoke.mjs`).

Depois, **abra os prints** (ferramenta Read) em `~/repos/.reestrutura_whitelabel/logs/<branch>/prints/`,
pelo menos desktop claro, celular e escuro, e corrija o que estiver errado. Fique atento a texto
cortado, colunas escondidas, alinhamento, contraste no escuro e cards de largura diferente. Só
entregue com `RESULTADO: ok` e os prints conferidos.

## Relatório final (última mensagem, em PT-BR)

1. `git log --oneline` das suas branches (a partir da base) e se o working tree está limpo.
2. O que mudou, curto.
3. **Mudanças visíveis para a PR** (antes → depois).
4. Peças novas em `shared/ui` (com sha) e pedidos de ajuste em peças comuns.
5. A saída do `validar-leva.sh` e o que você conferiu nos prints.
6. O que não deu para exercitar e por quê; defeitos encontrados; dúvidas.
