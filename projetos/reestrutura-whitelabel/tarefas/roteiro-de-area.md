# Roteiro comum das tarefas de área (05–12)

Cada tarefa de área segue estes passos. O arquivo da tarefa traz só o que é
específico dela: telas, serviços, fluxos críticos e armadilhas.

## Branch

- Nasce da 04 enquanto a 04 não entra na master. Depois, da `origin/master`
  com `--no-track`.
- Antes de qualquer ação, dar `git pull` na branch de base.

## Commits, nesta ordem

1. **Mover** (`refact`): levar as telas para `features/<área>/` e os
   serviços e interfaces de `services/` e `interfaces/` para
   `data-access/`/`models/`, só corrigindo imports. Nenhuma outra mudança,
   para o git reconhecer como renomeação.
2. **Rotas** (`refact`): criar `<área>.routes.ts` e trocar as entradas do
   `app.routes.ts` por `loadChildren`. URLs, guards e `data` ficam
   idênticos.
3. **Shell** (`refact`): tirar o `<app-layout>` das telas. Título e
   breadcrumbs passam a vir da rota.
4. **Componentes** (`refact`): trocar `mat-*` pelos componentes de
   `shared/ui` e `mat-icon` por `app-icon`, usando
   [material-para-novo.json](../anexos/icones/material-para-novo.json).
5. **Tokens** (`refact`): trocar cores fixas por tokens semânticos e apagar
   os `::ng-deep` que miravam classes do Material.
6. **Organização** (`refact`), sem mudar comportamento, usabilidade nem lógica:
   - quebrar componentes gigantes em partes com responsabilidade clara (ex.:
     a toolbar de filtros, o card de resumo, o diálogo);
   - tirar a regra de negócio do template para funções puras testáveis, e as
     chamadas HTTP para o `data-access/`;
   - reaproveitar o que se repete entre telas (formatadores, mapas de
     status, montagem de filtros) em `shared/` ou na própria feature;
   - padronizar comportamentos comuns:
     - valor vazio com um formatador só, no lugar de cada tela com o seu
       `-`, `—` ou `N/A`;
     - estados de carregando, vazio e erro com os componentes de `shared/ui`;
     - datas, moeda e percentual com os formatadores de `shared/utils`;
   - signals no estado da tela, `inject()`, `input()`/`output()`, `@if`/`@for`
     com `track`. Sem API depreciada e sem `subscribe` sem limpeza.

   Toda padronização que muda algo visível (ex.: o texto do valor vazio)
   fica listada na descrição da PR, com o antes e o depois.
7. **Limpeza** (`refact`/`fix`): código morto confirmado, tipos melhores.
   Um defeito encontrado no caminho vai num commit `fix` separado, ou vira
   anotação na tarefa.

## Regra de ouro

Toda tela segue os estilos e os componentes definidos por nós:
- **Visual:** só tokens (cor, raio, espaçamento, fonte, sombra). Nada de cor
  ou valor solto no SCSS da tela.
- **Componentes:** botão, campo, select, tabela, diálogo, pílula de status,
  card de resumo, toolbar de filtros, estado vazio etc. vêm de `shared/ui`.
  A tela não recria um componente que já existe nem sobrescreve o visual
  dele com `::ng-deep`.
- **SCSS da tela:** fica só com o layout dela (grid, ordem, larguras).
- **Faltou alguma coisa?** Se a tela precisa de um padrão que ainda não
  existe, ele entra em `shared/ui`, com spec e exemplo na vitrine (15), e só
  então a tela usa. Não fica como versão local.

## Pronto quando

- `npm run build` e `npm run lint` passam sem erro novo em relação ao
  baseline da 01.
- Os specs da área passam, inclusive os que já falhavam no
  [baseline](../evidencias/baseline-2026-10-10.md). A correção deles vai num
  commit `test` separado, **antes** da refatoração. Spec que mudou de lugar
  continua testando a mesma coisa.
- `grep -r "@angular/material" features/<área>` não retorna nada.
- Não sobra cor fixa nos `.scss` da área, salvo as anotadas com motivo (ex.:
  logo de parceiro).
- A tela foi aberta no navegador nos 4 casos: Poliedro claro, Poliedro
  escuro (forçado por `data-scheme`), Dots claro e no celular (~400 px).
- Os fluxos críticos da tarefa foram exercitados. O que não deu para
  exercitar (ex.: falta de dado na sandbox) fica escrito na tarefa.

## Como validar uma leva (comandos)

O scratchpad do Claude fica em `/tmp` e se perde entre sessões. Por isso os
números de base estão aqui:

- **Base da 04:**
  - lint: 59 erros e 281 avisos;
  - testes: 674, com 76 falhando.
- **Regra:** nenhuma falha nova e nenhum erro de lint novo.

Comandos:

1. **Testes:**
   `CHROME_BIN=~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome npx ng test --watch=false --browsers=ChromeHeadless`.
   - A lista de falhas sai das linhas `... FAILED` do log, depois de tirar as
     cores ANSI.
   - Compare essa lista com a da 04, gerada com o mesmo comando na branch da 04.
2. **Smoke:** a navegação com dados fictícios (mock) pelas 29 rotas.
   - Instale uma vez: `npm i playwright-core` numa pasta qualquer.
   - Rode `PW_DIR=<pasta>/node_modules node anexos/scripts/smoke.mjs <dist>/browser <pasta-prints>`.
   - O mock não tem os escopos de lotes, então essa tela abre em "sem permissão".
3. **Juntar os commits:**
   [anexos/scripts/juntar-branch.py](../anexos/scripts/juntar-branch.py) monta
   a branch final a partir da worktree do agente.
   - Os agentes Sonnet costumam passar de 72 caracteres no assunto do commit.
   - Os assuntos encurtados vão no mapa `R` do script.
4. **Conferências de revisão:** sem `@angular/material`, sem `#hex`/`rgb(` nos
   `.scss`, sem `@Input`/`*ngIf`/`::ng-deep` e com um spec por componente.

**Lição da 1ª leva:**
- Os agentes da 05 e da 06 bateram no limite de sessão no meio do trabalho.
- Os agentes da próxima leva vão com escopo enxuto e com commit a cada etapa.
- Se um agente cair, um agente novo termina o que ficou pendente no working
  tree da worktree.
