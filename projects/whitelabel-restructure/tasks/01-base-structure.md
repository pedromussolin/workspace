+++
card = "TS-5358"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 01 — Estrutura base

- **TS:** TS-5358 · **Branch:** `refact/TS-5358-estrutura-base-front` (de `origin/master`)
- **Status:** commits feitos na branch, sem push (10/10/2026). Falta a revisão do Pietro
- **Depende de:** —

## Escopo

1. **Baseline** antes de mexer:
   - rodar `npm ci`, `npm run build`, `npm run lint` e `npm test` (Karma,
     Chrome headless);
   - registrar o resultado em `evidence/baseline-<data>.md`, com falhas e
     avisos que já existem.
2. **`core/`:** mover `auth/` (guards, interceptor, `iam/`, `return-url`),
   `http/base-api.service.ts`, `utils/api-error.ts` e `theme/`. Criar
   `core/config/` para o `environment`. Corrigir o tipo de `themeKey`, que
   hoje não inclui `cerys` (a Cerys tem deploy próprio).
3. **`shared/`:**
   - mover `utils/` (formatter, date-formats, table.utils,
     state_preservation), o `markdown.pipe` e a diretiva
     `apx-chart-resize`;
   - mover `interfaces/general/*`, que são tipos de componentes genéricos,
     para junto dos componentes, ou para `shared/` quando ainda não houver
     componente.
4. **`layouts/app-shell/`:**
   - mover header, sidebar, breadcrumbs, layout, utility-sidebar e
     context-sidebar;
   - criar o shell como rota-mãe, que convive com o `<app-layout>` antigo
     até as tarefas de área (ver [target-architecture](../target-architecture.md#rotas)).
5. **Aliases** `@core`, `@shared`, `@layouts`, `@features` no
   `tsconfig.json`.

## Fora do escopo

- Trocar componentes do Material. Isso é da 03 e da 04.
- Mexer em cores. Isso é da 02.

## Pontos de atenção

- Hoje o `authInterceptor` importa `MatSnackBar` e o `SnackbarComponent`.
  Ele continua assim até a 04 trazer o toast próprio.
- O `iamGuard` é o dono do 401 de `/iam/navigation`, e o interceptor ignora
  essa URL de propósito. Isso tem que continuar igual.
- O shell como rota-mãe não pode disparar `iam/paths` duas vezes, nem
  recriar a sidebar a cada navegação de forma diferente do que acontece hoje.

## Validação

- Build, lint e testes iguais ou melhores que o baseline.
- No navegador:
  - login;
  - refresh numa rota profunda (ex.: `/pre-trade/<id>`);
  - sessão expirada, que leva ao `/login?sessionExpired=true`;
  - rota sem permissão, que leva ao `/unauthorized`;
  - rota inexistente, que leva ao `/not-found`;
  - menu filtrado por permissão.

## O que foi feito (10/10/2026)

| Commit | O quê |
|---|---|
| `e7a8dec` test | Corrige os 6 specs que não compilavam. A suíte volta a rodar |
| `8d28396` refact | Aliases `@core`, `@shared` e `@layouts` |
| `0fc3754` refact | `auth/`, `http/`, `api-error` e `theme/` → `core/` |
| `13de722` refact | Utilitários, pipe de markdown, diretiva do ApexCharts e breadcrumbs → `shared/` |
| `6f2ad7c` refact | Header, sidebar e layout → `layouts/app-shell/` |
| `308442a` refact | **Shell como rota-mãe**. As 25 telas trocam `<app-layout>` por `<app-page-header>`. A sidebar volta a recolher e a abrir o grupo da rota a cada navegação, como antes. A Home espera o shell pelo `AppShellStatus`. Header, sidebar e shell usam `input()`, `output()`, signals e `host` |
| `32755ec` test | Specs de comportamento: shell, sidebar, header, page-header, breadcrumbs e home |
| `552baad` refact | `iamGuard` e `plgnGuard` redirecionam devolvendo `UrlTree` |
| `d58fe8c` test | Specs dos redirecionamentos dos dois guards |
| `1185fee` chore | Remove o `condominiums.service` e o `context-sidebar`, que ninguém usava |
| `9767e3e` fix | O tipo do `themeKey` passa a aceitar `cerys` (A1) |
| `2b05952` chore | Import sem uso no `BaseApiService` (A6) |
| `b38f4c0` fix | Home centralizada de novo dentro do shell (A12, achado pela regressão visual) |

Diferenças de comportamento, todas intencionais:
- Header e sidebar não são mais recriados a cada navegação. Por isso `iam/paths` e
  `iam/profile` são chamados uma vez por sessão do shell, e não uma vez por
  página.
- O redirecionamento dos guards devolve `UrlTree` em vez de chamar
  `navigate`. A URL final é a mesma.

### Validação

Baseline em [evidence/baseline-2026-10-10.md](../evidence/baseline-2026-10-10.md).

| Checagem | Antes (`d0bc3de`) | Depois |
|---|---|---|
| `npm run build` | passa | passa |
| `npm run lint` | 73 erros / 286 avisos | 71 erros / 285 avisos (nenhum novo) |
| Testes | não compilavam (depois do conserto: 249, 95 falhando) | 263 testes, 88 falhando, nenhuma falha nova |
| Smoke com BFF falso ([smoke.mjs](../attachments/scripts/smoke.mjs)) | — | 29 rotas em desktop e celular, sem erro no console. O shell persiste na navegação interna |
| Regressão visual (prints da master × branch) | — | ver [evidence/visual-regression-ts-5358.md](../evidence/visual-regression-ts-5358.md) |

Não validado: login real no Azure e a sessão expirando de verdade. Precisam
do BFF; testar na sandbox.
