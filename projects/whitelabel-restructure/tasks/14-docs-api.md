+++
card = "TS-5371"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Highest"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 14 — Docs da API autenticada

- **TS:** TS-5371 · **Branch:** `feature/TS-5371-docs-api-autenticada` (da 04)
- **Status:** commits feitos, sem push (15/10)
- **Depende de:** 04 (componentes). Decisão D8.

## Objetivo

Quem tem permissão consulta a documentação OpenAPI do BFF de dentro do
portal, com a própria sessão, e pode executar qualquer chamada.

## BFF

- Hoje `openapi_url`, `docs_url` e `redoc_url` só existem com `expose_docs`
  ligado (`src/infra/fastapi/__init__.py:38-58`). Em produção devem estar
  desligados.
- Proposta:
  - rota nova `GET /docs/openapi` que devolve `app.openapi()`;
  - protegida pela sessão (cookie) e por um escopo novo (ex.:
    `api-docs:read`) no `check_authorized_roles`, com o `admin:read` como
    override;
  - entrada em `FRONTEND_ROUTE_PERMISSIONS` para a rota do front (`/api-docs`).
- As rotas públicas `/docs` e `/redoc` continuam controladas pelo
  `expose_docs`.

## Front

- Rota `/api-docs` dentro do shell, com o `iamGuard` e item de menu filtrado
  por `iam/paths`.
- `features/api-docs/`:
  - lista de tags e rotas com busca;
  - detalhe com parâmetros, corpo, schemas (com `$ref` resolvido) e
    respostas;
  - painel "Executar": monta a chamada pelo `HttpClient` com
    `withCredentials`, mostra status, tempo, headers e corpo da resposta.
- **Executar qualquer método** (decisão de 10/10). Proteções de UI:
  - POST, PUT, PATCH e DELETE pedem confirmação no diálogo, mostrando
    método, URL e corpo;
  - a página avisa o ambiente atual (produção ou sandbox).
- A permissão de verdade continua no BFF: cada chamada passa pelas mesmas
  checagens de quando é feita pela tela.

## Testes

- Spec do parser de OpenAPI (resolver `$ref`, agrupar por tag) e do montador
  de request.
- Spec da confirmação para métodos que alteram dados.
- BFF: teste da rota nova com e sem permissão.

## O que foi feito (15/10/2026)

Duas branches, as duas sem push:
- **front:** `feature/TS-5371-docs-api-autenticada`, criada da 04 com as
  três correções de 15/10 (`779aa13`), com 18 commits;
- **BFF:** `feature/TS-5371-docs-api-autenticada`, criada da
  `origin/master` (`946dce3`), com 3 commits.

**BFF**

| Commit | O quê |
|---|---|
| `2f307cf` | módulo `api_docs` com `GET /api-docs/openapi`, que devolve o `app.openapi()` mesmo com o `expose_docs` desligado. Pede sessão e `check_authorized_roles(["api-docs:read", "admin:read"])` (D14). `/docs`, `/redoc` e `/openapi.json` continuam presos ao `expose_docs` |
| `e80631b` | `/api-docs` no fim do `FRONTEND_ROUTE_PERMISSIONS` |
| `0dbb0ab` | testes com o middleware real: 200 com o escopo e com o admin, 401 sem sessão, 403 sem o escopo, 404 nas docs públicas desligadas e o caminho no `iam/paths` só para quem pode |

**Front**

| Commits | O quê |
|---|---|
| `c31647c`, `4f12702`, `5ba38d2` | cópias (cherry-pick) da 05 e da 09, com conteúdo idêntico: pílula/KPI/estado vazio, aviso em faixa e cartão |
| `336db24` | `app-code-block` em `shared/ui`: bloco de código com título, copiar, quebra opcional e altura máxima. É a versão única; a 15 usa a mesma, copiada |
| `5f20362`, `c17f5c5`, `cdd6995`, `91739ce` | funções puras com spec: leitura do OpenAPI (`$ref` resolvido, inclusive circular; `allOf`/`anyOf`; grupos por tag; busca sem acento), montador de request (path, query, headers, JSON, urlencoded e multipart) e aviso do ambiente; serviço que lê o OpenAPI e executa com a sessão |
| `711afbe`, `969ec00`, `1b7d36e` | a página: lista com busca à esquerda, detalhe com parâmetros, corpo e respostas (schema em árvore ou exemplo), e o painel "Executar" com confirmação no diálogo para POST, PUT, PATCH e DELETE. A rota aberta fica na URL (`?operation=`) |
| `7fc8c03`, `6ca728c`, `08a948e`, `3ef9b14` | ajustes vistos nos prints: caminho quebra nas barras; schema grande começa fechado; pílula do método não encolhe; no celular, rota aberta mostra o detalhe primeiro, com "Todas as rotas" |
| `da6aead` | o ambiente vem do campo `ENVIRONMENT` do `env.js`, gravado pelo `entrypoint.sh` (production, sandbox, staging ou local). Sem ele, a página deduz pelo endereço, como antes |
| `916a25a`, `211275a` | cópia dos commits da 15: atalhos "Docs da API" e "Design system" no rodapé da sidebar, com selo "Nova" e só para quem tem o caminho; trilha no cabeçalho das páginas dos atalhos |

**Mudanças visíveis para listar na PR:**
- página nova "Docs da API" (`/api-docs`), para quem tem `api-docs:read`
  ou `admin:read`;
- rodapé da sidebar com os atalhos "Docs da API" e "Design system", cada
  um só para quem tem acesso;
- nenhuma tela existente mudou.

**Antes do deploy** (o Pietro cria): a app role `api-docs:read` no app
registration do BFF e a variável `ENVIRONMENT` do front em cada ambiente. Até lá, só quem tem `admin:read` vê a página.

**Pontos abertos:**
- **Ambiente:** resolvido no `da6aead` (Pietro concordou). Falta definir a
  variável `ENVIRONMENT` no deploy de cada ambiente; enquanto não houver, a
  página deduz pelo endereço.
- **Comentários:** no front ficaram em PT-BR, como o resto do repo e as
  peças da 04; no BFF, em inglês. O padrão anotado na memória é inglês.
  Decidir na passada de consistência.
- **Contagem:** a página diz "127 rotas", contando método + caminho (o
  OpenAPI tem 106 caminhos). Dá para trocar por "operações".
- **Para unificar depois** (passada de consistência): o `json-payload` da 11
  e o botão de copiar do markdown da 12 podem usar o `app-code-block`; a
  busca com ícone se repete em 4 telas e é candidata a `app-search-field`;
  o editor JSON é um `appInput` com fonte mono, que caberia como variante.

**Validação** (base da 04: 678 testes, 77 falhando, lint 59/281; base do
BFF: 512 testes, 8 falhando):

| Item | 14 |
|---|---|
| Build | ok |
| Lint | 59 erros / 281 avisos |
| Testes | 804, com 77 falhando, nenhuma falha nova. Specs da feature: 96, mais 4 do `app-code-block` |
| Commits | todos compilam sozinhos |
| Smoke | com o OpenAPI real do BFF (106 caminhos, guardado fora do repo): lista e rota aberta, mais `/home` e `/pre-trade`, em claro, escuro, Dots e celular, sem erro de página, de console nem rolagem lateral |
| Fluxo "Executar" | Playwright próprio com BFF falso: POST com confirmação e "201 Created", GET direto e GET com parâmetros |
| BFF | 518 testes, com as mesmas 8 falhas da base; `ruff` e `black` sem nada novo |

Não deu para exercitar com o BFF real: chamada executada com 401/403,
upload multipart e download de binário. Ficam cobertos por specs e
precisam ser conferidos na sandbox.
