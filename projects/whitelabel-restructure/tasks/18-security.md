# 18 — Segurança do front

- **TS:** TS-5386 · **Branch:** `fix/TS-5386-seguranca-front` (da `master`, com
  `--no-track`)
- **Status:** **commits feitos, sem push** (15/10)
- **Depende de:** nada. Nasce da `master` e entra direto, sem esperar o
  épico. As branches do épico pegam a mudança no próximo rebase.

## Objetivo

Deixar o portal sem falha conhecida nas bibliotecas de produção, com as
proteções do navegador valendo em todas as respostas e a permissão checada
em todas as rotas.

No pitch para a diretoria, entra como parte do plano e aparece só pelo
resultado (D12).

## Escopo

1. **Bibliotecas** ([A17](../findings.md)). Em 15/10, o
   `npm audit --omit=dev` acusava 12 falhas (9 altas e 3 moderadas), todas
   com correção sem versão major:
   - `@angular/*` 20.3.11 → 20.3.34, que corrige 8 das altas. CLI, `cdk` e
     `material` sobem juntos, na mesma linha;
   - `dompurify`, `markdown-it` e `linkify-it`, usados no markdown do chat;
   - `moment`: atualizar agora. Ele sai de vez na 13, com o datepicker
     próprio.
2. **Cabeçalhos do nginx** ([A16](../findings.md)):
   - antes de tudo, confirmar com a infraestrutura o que o gateway já
     envia, inclusive HSTS;
   - repetir os cabeçalhos de segurança em todo `location` que tem
     `add_header` próprio (ex.: um `include` de um arquivo só com eles);
   - conferir com `curl -I` em `/`, `/index.html`, uma rota profunda (ex.:
     `/pre-trade`) e `/assets/env.js`;
   - trocar `X-XSS-Protection: 1; mode=block` por `0`, que é a
     recomendação atual. O filtro antigo dos navegadores foi removido e
     podia ser explorado.
3. **CSP** (lista de origens de onde o navegador pode carregar script,
   estilo, fonte e chamadas):
   - começa como `Content-Security-Policy-Report-Only`, liberando só o
     próprio domínio, o Google Fonts e o BFF;
   - o script do `index.html` que aplica o esquema de cor antes do Angular
     subir é inline: precisa de hash na CSP (ou o `autoCsp` do Angular);
   - os estilos dos componentes pedem `style-src 'unsafe-inline'` ou nonce;
   - depois de um ciclo na sandbox sem violação, vira
     `Content-Security-Policy`.
4. **Permissão em todas as rotas** ([A10](../findings.md)):
   - `/pdd` ganha o `iamGuard`. O BFF já libera a rota com `pdd:read` (e
     `admin:read`) no `FRONTEND_ROUTE_PERMISSIONS`, então não há escopo
     novo a decidir (conferido em 15/10);
   - um spec percorre as rotas e falha se uma rota autenticada ficar sem
     guard.
5. **Checagem contínua:**
   - `npm audit --omit=dev --audit-level=moderate` entra no `validar.sh` da
     `.ai/` ([17](17-ai-folder.md));
   - no pipeline, entra com a infraestrutura (D9, tarefa 16).
6. **Regras na `.ai/fronteiras.md`:**
   - `bypassSecurityTrust*` só com conteúdo estático do próprio código,
     como os ícones (`shared/ui/icon`);
   - HTML vindo de fora passa pelo DOMPurify, como o markdown do chat já
     faz.

## Conflitos esperados

- `package-lock.json` com as áreas e a 13: na hora do rebase, refazer o
  lock a partir do `package.json` resolvido.
- `/pdd`: a 09 move a rota para `features/controllership`. Quem rebasear
  por último leva o guard junto.

## Critérios de aceite

- `npm audit --omit=dev` sem nenhuma falha.
- Build, lint e testes sem falha nova. Smoke das rotas sem erro.
- `curl -I` mostra os cabeçalhos em todas as respostas listadas.
- CSP em report-only sem violação ao navegar por todas as rotas na
  sandbox.
- Sem permissão, `/pdd` leva para `/unauthorized`, como as outras rotas.

## Fora do escopo

Sessão, cookie e CORS do BFF: ficam no apl-credit-whitelabel-api.

## O que foi feito (15/10/2026)

Branch `fix/TS-5386-seguranca-front`, criada da `origin/master`
(`576957c`). São 6 commits, sem push:

| Commit | O quê |
|---|---|
| `45f2d2a` | cherry-pick do `9bcf7b7` da 01 (specs que não compilavam, A21), com o conteúdo idêntico |
| `9ed89a3` | bibliotecas sem versão major: Angular 20.3.11 → 20.3.34 (CLI e build 20.3.40; `cdk` e `material` 20.2.14, que é a linha deles), `dompurify` 3.4.17, `markdown-it` 14.3.2 (`linkify-it` 5.0.2) e `moment` 2.31.0 |
| `b257967` | cabeçalhos em `nginx-security-headers.conf`, incluído no `server` e em todo `location` com `add_header` próprio; `X-XSS-Protection: 0`; HSTS pronto e comentado |
| `4e2a013` | CSP em `Content-Security-Policy-Report-Only`. A origem do BFF vem do `entrypoint.sh`, a partir do `API_URL`, quando ele é absoluto |
| `85a5abd` | `iamGuard` no `/pdd` e o `app.routes.spec.ts`, que falha se uma rota autenticada ficar sem guard |
| `d88c896` | `npm run audit:prod` e uma seção no README |

**Mudanças visíveis para listar na PR:**
- `/pdd` sem permissão vai para `/unauthorized`. Antes, a tela abria e só
  o BFF barrava as chamadas.
- As respostas do nginx (`/`, `/index.html`, rotas profundas, `env.js` e
  estáticos) saem com os 4 cabeçalhos e a CSP em report-only. Antes, não
  saía nenhum.
- Nas telas, nada muda.

**CSP:**
- **O que libera:**
  - `script-src 'self'` mais o hash do `onload` do CSS crítico, que o build
    do Angular põe;
  - `style-src` com `'unsafe-inline'` e o Google Fonts;
  - `img-src 'self' data:`;
  - `connect-src`/`frame-src 'self'` mais a origem do BFF.
- **Por que não o `autoCsp` do Angular:**
  - ele gera um `<meta>`, e o navegador ignora report-only em meta;
  - ele quebraria o `env.js`, que o `entrypoint.sh` reescreve com
    `?v=<ts>`.
- **Script inline do esquema de cor (da 02):** seria acusado depois da
  junção com o épico. A 13 o leva para um arquivo em `assets/`.

**Validação:**

| Item | Resultado |
|---|---|
| `npm audit --omit=dev` | 12 falhas (9 altas e 3 moderadas) → **0** |
| Build e lint | build ok; lint 73/288, igual à master |
| Testes | 253, com as 96 falhas da base e nenhuma nova. O spec das rotas falha sem o guard no `/pdd` |
| `curl -I` na imagem de produção | os 4 cabeçalhos e a CSP em `/`, `/index.html`, `/pre-trade`, `/assets/env.js`, `/api/...`, `/main-*.js` e `/health` |
| CSP no navegador | nenhuma violação nas 31 rotas, com os eventos `securitypolicyviolation` escutados |
| Smoke | igual à master. Sem dados, a master já tem erros de console no `/pdd` e na Formalização; e a home no celular rola de lado (137 px), também na master |

**Falta confirmar com a infraestrutura:**
- o que o gateway já envia (HSTS, `X-Frame-Options`, CSP), para não
  duplicar;
- onde termina o TLS e qual valor de HSTS usar;
- se o gateway repassa os cabeçalhos do nginx;
- se haverá endpoint de relatório da CSP (`report-to`).

**Antes de trocar para CSP que bloqueia** (depois de um ciclo na sandbox):
- o download do chat por iframe com link pré-assinado do S3 vai violar o
  `frame-src`;
- imagens externas no markdown da IA vão violar o `img-src`;
- os dois só aparecem com dados reais.

**Regras para a `.ai/fronteiras.md` (17):**
- `bypassSecurityTrust*` só com conteúdo estático do código;
- HTML de fora passa pelo DOMPurify;
- script inline novo no `index.html` não pode, vai para `assets/`;
- origem externa nova entra na CSP no mesmo PR;
- rota autenticada tem `iamGuard`;
- cabeçalho novo vai no `nginx-security-headers.conf`;
- `npm run audit:prod` sem falha antes do PR.

**Conflitos esperados:**
- `package-lock.json` com o épico: refazer a partir do `package.json`
  resolvido. A 13 tira o Material, que a 18 atualiza;
- o guard do `/pdd` quando a 09 mover a rota.

### Junção com o épico (16/10)

Ensaiada sobre a 13, que já junta todas as áreas. São 10 conflitos, e o
script `$PRIV/resolucoes/fix_TS-5386-seguranca-front.sh` resolve todos:
1. **Specs do `9bcf7b7`** (cherry-pick com o conteúdo igual ao da 01):
   ficam na versão do épico. Os caminhos antigos saem.
2. **`package.json`:** é o do épico (sem Material nem `moment`), com as
   versões da 18 e o script `audit:prod`.
3. **`package-lock.json`:**
   - o lock do épico prende o Angular velho (ERESOLVE);
   - tirar as entradas `node_modules/@angular/*` e rodar
     `npm install --package-lock-only`.
4. **`app.routes.ts`:** fica o do épico, e o `iamGuard` do `/pdd` vai para
   o `PDD_ROUTES` de `features/controllership/controllership.routes.ts`.
5. **`entrypoint.sh`:** ficam as duas linhas de debug (`ENVIRONMENT` da 14 e
   `CSP_BFF_ORIGIN` da 18).
6. **`app.routes.spec.ts`:**
   - imports de `@core/auth/iam` e `ToastService` no lugar do Material;
   - o teste das rotas públicas percorre as filhas lazy, porque no épico o
     login e as páginas de erro ficam em `features/general`.

Resultado: os 3 testes de rotas passam e o audit fica em 0.

