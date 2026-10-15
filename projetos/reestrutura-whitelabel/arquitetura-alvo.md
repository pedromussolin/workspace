# Arquitetura alvo

Este documento é a referência, não um molde rígido. Cada pasta só existe se
tiver código de verdade. A regra geral é que o comportamento das telas não
muda: URLs, parâmetros, autenticação, permissões e contratos com o BFF ficam
como estão.

## Como está hoje (`d0bc3de`)

- **Inicialização:** Angular 20.3, componentes standalone, `bootstrapApplication`
  e `app.config.ts`. O tema é aplicado num `provideAppInitializer`.
- **Rotas:** 42 entradas num `app.routes.ts` plano, todas com `loadComponent`
  (lazy). A proteção vem do `iamGuard`; o Poli Chat usa também o `plgnGuard`.
- **Layout:** `app.html` é só um `<router-outlet>`. Cada uma das 26 páginas
  embrulha a si mesma em `<app-layout>` (header, sidebar e breadcrumbs). Por
  isso o header e a sidebar são recriados a cada navegação.
- **Autenticação:**
  - sessão por cookie gerenciada pelo BFF (`withCredentials`);
  - o login é um redirect externo (`auth.service.ts`);
  - o `authInterceptor` trata o 401 com um snackbar do Material e manda para
    `/login`.
- **Permissão:** o front guarda só a constante do escopo e pergunta ao BFF as
  ações (`iam.authorizeActions`). A rota usa o `iamGuard`, e o menu é
  filtrado por `iam/paths`. As roles ficam só no BFF.
- **Acesso ao BFF:**
  - `http/base-api.service.ts` monta URL e parâmetros;
  - os serviços ficam numa pasta global, `services/<área>/...`;
  - os modelos ficam em outra, `interfaces/<área>/...`, longe das telas.
- **Configuração:** `assets/env.js`, gerado na subida do container
  (`scripts/generate-env.js`), traz `apiUrl`, `themeKey` e os caminhos de
  auth. O tipo `environment.themeKey` não inclui `cerys`, embora a Cerys
  tenha deploy próprio.

## Estrutura alvo

```text
src/app/
├── app.ts / app.html / app.config.ts / app.routes.ts
├── core/
│   ├── auth/          auth.service, guards (auth, iam, plgn), interceptor, return-url, iam/
│   ├── http/          base-api.service, tratamento de erro da API (api-error)
│   ├── config/        leitura do window.__CONFIG__ (environment)
│   └── theme/         marcas, tokens aplicados no :root, esquema claro/escuro
├── shared/
│   ├── ui/            componentes próprios (page-header, breadcrumbs; na 03/04: icon, button, field, select, dialog, toast, table...)
│   ├── directives/    ex.: apx-chart-resize, diretivas do iam se forem só de UI
│   ├── pipes/         ex.: markdown
│   └── utils/         formatter, date-formats, table.utils, state_preservation
├── layouts/
│   └── app-shell/     shell (rota-mãe), header, sidebar e o AppShellStatus
└── features/
    ├── pre-trade/
    ├── liquidation-batches/  (+ manual-reconciliation)
    ├── assignment-batches/   (+ contract-details)
    ├── report-transfer/
    ├── formalization/
    ├── controllership/       (cerc-reconciliation, pdd, portfolio-performance)
    ├── cash-consolidation/
    ├── orchestrator/         (orchestrator, flow-detail, product-config)
    ├── onboarding-bgt/
    ├── users/  clients/  simulate-proposal/
    └── general/              (login, home, poli-chat, not-found, unauthorized)
```

Dentro de cada feature a organização é progressiva. Uma feature simples
fica com os arquivos juntos. Uma complexa ganha subpastas por necessidade:

```text
features/report-transfer/
├── report-transfer.routes.ts
├── report-transfer.page.ts/html/scss
├── components/    só desta feature
├── dialogs/
├── data-access/   report-transfer-api.service.ts, report-transfer.dto.ts
└── models/        quando o modelo da tela difere do DTO
```

## Regras de dependência

- `core` não importa nada de `features`.
- `shared` não importa nada de `features` nem de `core`. É a camada mais baixa.
- `core` pode usar `shared` (ex.: o interceptor de 401 usa o toast de
  `shared/ui`).
- `layouts` pode usar `core` e `shared`, nunca uma feature.
- Uma feature usa `core` e `shared`. Uma feature não importa arquivos
  internos de outra. Se duas precisarem da mesma coisa, ela sobe para
  `shared` (se for genérica) ou vira contrato explícito.
- Sem `index.ts` em toda pasta. Barril (arquivo que reexporta uma pasta) só
  onde ele marcar uma fronteira de verdade.
- Aliases de caminho (`@core/*`, `@shared/*`, `@layouts/*`, `@features/*`)
  só para atravessar fronteiras. Dentro da feature, import relativo.
- A tarefa 13 adiciona regras de lint que travam essas direções:
  `no-restricted-imports` para `@angular/material` e para imports entre
  features.

## Rotas

- `app.routes.ts` vira um índice: rotas públicas (login, unauthorized,
  not-found) e uma rota-mãe com o **app-shell** que carrega cada feature por
  `loadChildren` (`features/<x>/<x>.routes.ts`).
- URLs, redirects, parâmetros, `data.breadcrumb`, `data.department` e guards
  continuam idênticos.
- **Shell como rota-mãe** (feito na 01):
  - as 25 telas que usavam `<app-layout>` agora são filhas do `AppShellComponent`
    (`layouts/app-shell`);
  - cada página abre com `<app-page-header>` (`shared/ui/page-header`), que
    mostra título, ajuda e breadcrumbs;
  - login, unauthorized, not-found e Poli Chat ficam fora do shell, como
    antes.
- Guards funcionais retornam `UrlTree` para redirecionar, em vez de navegar
  por conta própria. Isso evita corrida entre guards.

## Integração com o BFF

- O BFF continua sendo a única porta. Nenhum contrato muda nesta reestruturação.
- `core/http` cuida só do que é transversal: URL base, `withCredentials`,
  normalização de erro e o 401 global.
- Os métodos de cada endpoint ficam na feature (`data-access/`).
- Os tipos de request e response ficam junto da feature. Mapeador só onde a
  tela realmente precisar de outro formato.
- Erros:
  - quem mostra a mensagem é a tela;
  - o interceptor cuida só do 401;
  - o objetivo é que nunca saiam dois avisos para o mesmo erro.

## Estado

- Signals para estado síncrono da tela: filtros, seleção, abertura de painel.
- RxJS para HTTP, debounce e cancelamento.
- Sem store global novo. O estado fica perto de quem usa.

## O que pode quebrar e como cuidamos

| Risco | Cuidado |
|---|---|
| Mover arquivos e mudar código no mesmo commit faz o git perder o histórico | Commit só de mover em cada área |
| O shell como rota-mãe muda a ordem em que guard e layout iniciam | Testar login, sessão expirada, refresh numa rota profunda e o `returnUrl` |
| Serviço `providedIn: 'root'` que vira provider de rota passa a ter outra vida útil | Manter `providedIn: 'root'`, salvo motivo explícito |
| `::ng-deep` das telas mira classes internas do Material (`.mat-mdc-*`) | Some junto com o Material em cada área. Conferir tela a tela |
| Karma precisa de Chrome | O baseline da 01 registra se os testes rodam no ambiente local |
