# TS-5193: porte da área do Orquestrador para a base nova (21/10)

Um dev refez a área do Orquestrador (aba **Visão do produto**, nova, e aba **Execuções**, por
produto) na estrutura antiga do front: `pages/`, Angular Material e cores fixas. O trabalho dele
está na branch `origin/feature/ts-5193-estruturacao-metricas`, já buscada no repo. Leia qualquer
arquivo com `git show origin/feature/ts-5193-estruturacao-metricas:<caminho>`, e o diff com
`git diff $(git merge-base origin/feature/ts-5193-estruturacao-metricas origin/sandbox) origin/feature/ts-5193-estruturacao-metricas -- <caminho>`.

**Decisão do Pietro:** o desenho e o comportamento são os do dev, refeitos na base nova. A base nova é
a de todas as telas do portal hoje: componentes de `shared/ui`, cor só por token, claro e escuro,
celular, signals e OnPush, spec de comportamento. A lógica pura e os specs do dev são aproveitados.
Isso entra no deploy de produção de **hoje à noite**, então foque no que a tela faz. Acabamento fino,
só se sobrar tempo.

## Como portar

O porte segue o [roteiro das áreas](../../tasks/area-playbook.md): os passos 4 a 7, a "Regra
de ouro" e o "Pronto quando". Não é só trocar o visual.

- **Lógica:** sai do componente para modelo, regras e visão (`*.view.ts`, funções puras
  testáveis). O componente fica fino: signals, `inject()`, `input()`/`output()`/`viewChild()`,
  OnPush, `@if`/`@for` com `track` e nenhum `subscribe` sem limpeza.
- **Funções puras do dev** (`*-presentation.ts`, `*-url-state.ts`, `execution-population.ts`,
  `execution-conditions.ts`): são aproveitadas, mas passam pelo padrão. Nomes explícitos, sem
  `any`, comentário novo em inglês, `check-patterns` e lint.
- **Estados e formatação:** carregando, vazio e erro vêm de `shared/ui`; valor vazio, datas, moeda e
  percentual, de `shared/utils`.
- **Specs das páginas:** os do dev testam o template antigo e os seletores do Material. Viram specs
  de comportamento sobre a tela nova, com os mesmos casos. O relatório diz o que ficou sem
  equivalente.

## Regras comuns

Valem as do `brief-release-21-10.md` (mesma pasta): worktree própria, sem commit, limitador
`ng-slot` para comando pesado, rascunho em `~/repos/.reestrutura_whitelabel/agentes/<pacote>/`,
prints em `~/repos/.reestrutura_whitelabel/evidencias/release-21-10/<pacote>/`, portas da sua
faixa e relatório em PT-BR. Leia o `CLAUDE.md` e a `.ai/` da worktree antes de começar.

## O que já está na base (`cfc60379`, na sua worktree)

- **Camada de dados** em `src/app/features/orchestrator/data-access/`:
  - `orchestrator.interface.ts` com os tipos novos do dev;
  - `orchestrator.service.ts` com `getOrchestratorProducts`, `getProductCatalog`, `listFlows`,
    `listProcesses` e `getPopulationContext`. O spec do dev está em
    `orchestrator.service.products.spec.ts`;
  - `product-analytics.interface.ts`, `product-analytics.service.ts` e o spec.
- **Fixtures do dev** em `src/app/features/orchestrator/testing/`: `product-view.mock.ts`,
  `product-step.mock.ts` e `product-view-v2.mock.ts`. Servem para specs e para os dados fictícios do
  seu navegador, **nunca** para código que vai para produção.
- **Calendário de dias úteis** em `src/app/shared/utils/business-calendar.ts`: era o
  `utils/business-calendar.ts` do dev, e o `formatDateToISO` virou `toApiDate`.
- **Seletor de visão da área:** `src/app/features/orchestrator/components/orchestrator-tabs/`
  (`<app-orchestrator-tabs [context]="...">`), com as rotas em
  `src/app/features/orchestrator/orchestrator-area.ts`. É o `app-toggle-group` do padrão "Seletor de
  visão", logo depois do `app-page-header`. Ele só aparece com as duas rotas liberadas no
  `iam/paths`.

Não mude a interface desses arquivos. Se precisar, descreva no relatório.

## Dados fictícios no navegador

O BFF falso do smoke responde pelo caminho, sem olhar a query. As visões `flows` e `processes` saem
as duas de `GET orchestrator/flows`. Para vê-las, responda as rotas do orquestrador no seu script
Playwright (`page.route`, olhando `view` na query), a partir das fixtures do dev.
