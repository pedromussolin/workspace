# 12 — Páginas gerais

- **TS:** TS-5369 · **Branch:** `refact/TS-5369-paginas-gerais-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** em andamento (15/10, 3ª leva)
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/` e `/login` | `pages/general/login/` |
| `/home` | `pages/general/home/` |
| `/poli-chat` e os 11 `*-poli-chat` (por departamento, via `data.department`) | `pages/general/poli-chat/poli-chat` |
| `/knowledge-base` | `pages/general/poli-chat/knowledge-base/` |
| `/unauthorized`, `/not-found` | `pages/general/*` |

## O que vai para `features/`

- `features/poli-chat/`:
  - tela, knowledge-base, `poli-header`, skeletons;
  - `components/chat` e `components/chat-bubble`, que só o Poli Chat usa e
    que dependem do `ai-assistant.service`;
  - `services/ai/ai-assistant.service.ts` → `data-access/`.
- `features/general/`: login, home, unauthorized e not-found.

Inventário (`d0bc3de`): 30 arquivos, 4.435 linhas, 163 cores fixas, 6
`::ng-deep`, 6 specs (mais os do chat). Material: icon, dialog, snack-bar,
button, tooltip, table, paginator, input e form-field.

## Fluxos críticos

- Login (`authGuard`), `returnUrl` e sessão expirada.
- Poli Chat:
  - envio, streaming e histórico;
  - bloco de código com botão copiar (o `markdown.pipe` hoje escreve
    `content_copy` num `span.material-icons` direto no DOM; isso vira SVG);
  - cada departamento por rota.
- Knowledge base.

## Pontos de atenção

- `styles.scss` tem o estilo global do botão de copiar código
  (`.code-block-wrapper`). Ele vai para o Poli Chat e passa a usar tokens.
- O `plgnGuard` continua só nas rotas do Poli Chat.
