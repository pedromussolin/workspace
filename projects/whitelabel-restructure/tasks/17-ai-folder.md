# 17 — Pasta `.ai`: repositório pronto para desenvolver com IA

- **TS:** TS-5389 · **Branch:** `chore/TS-5389-pasta-ai` (da 13)
- **Status:** **commits feitos, sem push** (16/10). Aceite cumprido e lacunas corrigidas. Na junção com a 13, a regra de datas aponta para a camada de formatação
- **Depende de:** 04. Pode começar já e fecha depois da 13, quando as regras
  de lint que garantem as fronteiras existirem.

## Objetivo

Deixar no próprio repositório tudo o que uma pessoa ou um agente de IA
precisa para entregar no padrão do portal, sem contexto extra: regras,
referências, receitas, scripts de validação e fronteiras. Uma fonte só,
que serve a qualquer ferramenta de IA.

No pitch para a diretoria, é o "nível 3 · IA nativa": o padrão do nível 2
(design system, arquitetura, testes) escrito e verificável.

## Estrutura

Nomes padrão de mercado, em inglês (D26). O conteúdo fica em PT-BR (D25).

```text
.ai/
├── README.md              porta de entrada: ordem de leitura e como validar
├── rules/                 regras sempre válidas
│   ├── architecture.md    core/shared/layouts/features e direções de import
│   ├── styling.md         só tokens, tom sobre tom, nada de cor solta
│   ├── components.md      sempre shared/ui; padrão novo nasce lá, com spec e vitrine
│   ├── angular.md         signals, input/output, inject, @if/@for; nada depreciado
│   ├── testing.md         spec de comportamento; nenhuma falha nova
│   ├── responsive.md      até ~400 px; Chrome, Edge e Safari
│   ├── permissions.md     o front só conhece o escopo; roles ficam no BFF
│   ├── security.md        CSP, DOMPurify, bypassSecurityTrust, audit
│   └── git.md             branch e commit com TS, commits atômicos, PT-BR, 72 caracteres
├── context/               conhecimento de referência
│   ├── design-system.md   tokens, marcas, claro/escuro e ícones (aponta para a vitrine, 15)
│   ├── reference-screens.md  Pré-Trade e Lotes como exemplo, com os caminhos
│   ├── domain.md          glossário dos módulos (lote, cessão, formalização...)
│   └── bff.md             onde achar o contrato (docs da API, 14) e o data-access de cada feature
├── skills/                passo a passo no formato Agent Skills (SKILL.md com name e description)
│   ├── new-page/
│   ├── new-component/
│   ├── new-brand/
│   ├── fix-bug/           teste que falha antes da correção
│   └── validate-change/
├── scripts/
│   ├── validate.sh        build, lint, testes e audit, com a lista de falhas conhecidas
│   ├── smoke.mjs          abre as rotas com BFF falso, no desktop e a ~400 px, e tira prints
│   └── check-patterns.mjs acusa o que o lint não pega
└── boundaries.md          o que não se toca sem pedido explícito
```

Na raiz, adaptadores finos que só apontam para a `.ai/`, sem repetir
conteúdo:
- `CLAUDE.md` e `AGENTS.md`;
- `.github/copilot-instructions.md`;
- `.cursor/rules/`, se o time usar.

## Fronteiras (conteúdo mínimo)

- **Não mexer sem pedido explícito:**
  - login e sessão (`core/auth`), guards, interceptors e permissões;
  - `env.js` e arquivos de deploy;
  - contratos com o BFF: URLs, parâmetros e payloads.
- **Proibido:** `@angular/material`, cor fora dos tokens, `::ng-deep` em
  `shared/ui`, import entre features e API depreciada.
- Cada item diz quem garante: regra de lint (a 13 cria as de import e de
  estilo), spec, script ou só revisão.

## De onde vem o conteúdo

A maior parte já existe e só muda de lugar, com os nomes reais (vai para o
repo da empresa):
- [target-architecture.md](../target-architecture.md),
  [design-system.md](../design-system.md) e [decisions.md](../decisions.md)
  → `regras/` e `referencias/`;
- [area-playbook.md](area-playbook.md) → `receitas/nova-tela.md` e
  `regras/`;
- `attachments/scripts/smoke.mjs` → `scripts/`, sem URL da sandbox nem dado
  real;
- as regras de git e de comunicação do `CLAUDE.md` da pasta de
  repositórios.

## Regra de manutenção

Mudou um padrão, muda a `.ai/` na mesma PR. Vai escrito no `README.md` da
`.ai/` e no modelo de descrição de PR.

## Critérios de aceite

- Um agente sem contexto além do repositório cria uma tela-exemplo (lista
  com filtro e linha expansível) que passa no `validar.sh` e no
  `checar-padrao.mjs` sem correção manual.
- Cada regra cita onde é verificada (lint, spec, script) ou diz que é só de
  revisão.
- Os adaptadores da raiz não repetem conteúdo.
- O `README.md` da `.ai/` se lê em cinco minutos.

## Depois

Levar o mesmo modelo para o apl-credit-whitelabel-api, o apl-shared-service
e o data-lake-api. Está como pedido no pitch para a diretoria.

## O que foi feito (16/10/2026)

Branch `chore/TS-5389-pasta-ai`, criada da 13 (`4bd8380f`). São 21 commits,
sem push. A estrutura usa nomes padrão (D26):
- **`.ai/rules/`:** architecture, styling, components, angular, testing,
  responsive, permissions, security e git;
- **`.ai/context/`:** design-system, reference-screens, domain e bff;
- **`.ai/skills/`**, no formato Agent Skills:
  - `new-page`, com o `scaffold.mjs`, que gera uma lista completa e testada;
  - `new-component`, `new-brand`, `fix-bug` e `validate-change`;
- **`.ai/scripts/`:** `validate.sh`, `check-patterns.mjs`, `smoke.mjs`,
  `known-failures.txt` (vazia), `known-lint-errors.txt` (os 20 da base) e
  `smoke-data/` (11 JSONs fictícios);
- **`.ai/boundaries.md`** e o **`.ai/README.md`** (cerca de 860 palavras,
  uns 4 minutos de leitura).

**Na raiz:**
- `CLAUDE.md` (com `@.ai/README.md` e `@.ai/boundaries.md`), `AGENTS.md` e
  `.github/copilot-instructions.md`, que só apontam para a `.ai/`;
- `.github/pull_request_template.md`, com a regra de manutenção;
- `.claude/skills` e `.agents/skills` como links simbólicos para
  `.ai/skills`. Cobrem Claude Code, Copilot e Codex, conforme a
  documentação de cada um;
- `docs/architecture.md` vira ponteiro (D23).

**Outros commits:**
- `512f3b9b` corrige o spec que falhava ("should render title"). A suíte
  fica sem nenhuma falha;
- `505476dc` põe o `playwright-core` 1.63.0 como devDependency.

**O que cada script verifica:**
- **`validate.sh`:**
  - build, lint, `check-patterns`, a suíte e o
    `npm audit --omit=dev --audit-level=moderate`;
  - falha com lint ou teste fora das listas conhecidas;
  - separa teste instável;
  - aceita `SKIP_AUDIT=1` até a 18 entrar.
- **`check-patterns.mjs`:** 15 verificações que o lint não faz, entre elas
  `::ng-deep`, decorador antigo, `*ngIf`, `subscribe` sem limpeza, sem
  `OnPush`, sem spec, spec só de "should create", HTTP fora do
  `data-access`, cor fixa no template, URL absoluta, `bypassSecurityTrust`,
  script inline, resto do Material, API depreciada e comentário divisor. O
  legado fica em listas que só diminuem.
- **`smoke.mjs`:**
  - BFF falso, rotas do menu lidas da `navigation.ts`, claro, celular,
    escuro, outra marca e marca no escuro;
  - falha com erro de página ou de console e com rolagem lateral;
  - lista as origens externas, para a CSP.

**Validação:**
- `validate-batch.sh`: ok. Build ok; lint 20/163; **1.820 testes, nenhuma
  falha**;
- smoke sem erro em claro, escuro, Dots e celular;
- `validate.sh` com `SKIP_AUDIT=1`: ok;
- `smoke.mjs --all`: 29 rotas, 116 páginas, sem erro.

**Pedidos de ajuste em peças comuns** (não feitos aqui): ver A27 e A28.

## Critério de aceite (16/10)

Um agente novo, com acesso só ao repositório (worktree descartável
`$PRIV/aceite-17`), recebeu o pedido de uma tela "Contratos de exemplo":
- lista vinda do BFF, com busca por cliente e filtro por status;
- linha que abre e mostra as parcelas.

**Resultado:** ele usou o `scaffold.mjs` da skill `new-page`. A conferência
rodei eu, sem corrigir nada:

| Item | Resultado |
|---|---|
| `check-patterns.mjs` | nada a apontar (15 verificações, 1.133 arquivos) |
| `validate.sh` (`SKIP_AUDIT=1`) | build ok, lint ok, 1.841 testes passando (21 novos) |
| Smoke | claro, celular, escuro e outra marca, sem erro |

**Lacunas que ele achou na `.ai/`.** Vão para a 17 em commits pequenos:
- **Formato da resposta do BFF:** o repo mistura lista solta, `{items}` e
  `{records, pagination}`. A `.ai/` passa a dizer como descobrir o formato.
- **Idioma:**
  - a rota fica em inglês, como as que já existem;
  - os comentários do scaffold passam para o inglês.
- **Dados de teste:** o scaffold passa a usar `features/<área>/testing/`.
- **Permissões de tela só de leitura:** o `iamGuard` mais a entrada
  `{escopo}:read` no BFF.
- **Passo no BFF** na skill `new-page`, para a rota de dados e a
  permissão.
- **Menu:** critério de seção.
- **Textos da auditoria:** dizem o que já existe e o que chega com a 18.
- **Smoke:** ganha a opção de abrir uma linha antes do print.
- **Feature nova:** atualiza as tabelas de `bff.md` e `domain.md`.
- **Datas:** não havia utilitário comum para data sem hora. Fica com a
  camada de formatação da 13, e a regra de datas da `.ai/` é atualizada na
  junção.

**Lacunas corrigidas** (12 commits a mais, 33 no total):
- **`bff.md`:** a tabela dos formatos de resposta e como descobrir o de um
  endpoint. No scaffold, o envelope fica só no `data-access`.
- **Idioma:** pasta, classe e rota em inglês, e texto de tela em PT-BR. Os
  comentários dos modelos estão em inglês, e o legado não se traduz.
- **Dados de teste:** em `testing/<área>.fixtures.ts`.
- **Tela só de leitura:** o `iamGuard` mais
  `FRONTEND_ROUTE_PERMISSIONS` com `admin:read` e `{escopo}:read`.
- **Skill `new-page`:** ganhou o passo "No BFF" e manda atualizar as tabelas
  de `bff.md` e `domain.md`.
- **Menu:** seções e critério em `architecture.md#menu`.
- **`security.md`:** mostra o que existe hoje e o que chega com a 18.
- **Smoke:** o `SCENES` abre uma linha da tabela antes do print.
- **Regra D55:** escopo por página e por contexto, com `admin:{ação}` em
  tudo menos no `access-control`.

**Validação:**
- `check-patterns` limpo;
- `validate.sh` (`SKIP_AUDIT=1`) ok, com 1.820 testes;
- o scaffold gera uma tela que passa em tipos, Prettier, lint,
  `check-patterns` e specs.

