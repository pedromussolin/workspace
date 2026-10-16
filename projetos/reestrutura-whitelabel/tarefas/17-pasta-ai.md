# 17 — Pasta `.ai`: repositório pronto para desenvolver com IA

- **TS:** TS-5389 · **Branch:** `chore/TS-5389-pasta-ai` (da 13)
- **Status:** em andamento (6ª leva, 16/10)
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
- [arquitetura-alvo.md](../arquitetura-alvo.md),
  [design-system.md](../design-system.md) e [decisoes.md](../decisoes.md)
  → `regras/` e `referencias/`;
- [roteiro-de-area.md](roteiro-de-area.md) → `receitas/nova-tela.md` e
  `regras/`;
- `anexos/scripts/smoke.mjs` → `scripts/`, sem URL da sandbox nem dado
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
