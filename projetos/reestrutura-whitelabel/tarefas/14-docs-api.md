# 14 — Docs da API autenticada

- **TS:** TS-5371 · **Branch:** `feature/TS-5371-docs-api-autenticada` (da 04)
- **Status:** a iniciar
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
