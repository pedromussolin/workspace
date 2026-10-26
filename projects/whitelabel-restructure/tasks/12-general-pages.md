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

## O que foi feito (15/10/2026)

Branch `refact/TS-5369-paginas-gerais-nova-arquitetura`, criada da 04 com as
três correções de 15/10. São 24 commits.

| Commits | O quê |
|---|---|
| `e732bad` | specs da área que falhavam na base voltam a passar, antes da refatoração (login, Poli Chat, chat, bolha, knowledge base e o cabeçalho do Poli) |
| `8db7725`, `6113f20` | move login, home, acesso negado e não encontrada para `features/general/` e o Poli Chat para `features/poli-chat/` (+ `data-access/`). Rotas com `loadChildren`; URLs, guards (`plgnGuard` só no chat) e `data.department` iguais. Login, páginas de erro e Poli Chat continuam fora do shell, como na 04 |
| `a460411`, `5c4e550` | cópias (cherry-pick) da 05, com conteúdo idêntico: pílula/KPI/estado vazio e valor vazio |
| `e47273a` | ícone `more-vertical` novo (os três pontinhos do menu da conversa) e `iconSvg()`, que gera o SVG como texto para HTML montado fora de template |
| `6333fb5`, `0e28f49`, `d4e92f9` | o botão de copiar código do markdown usa o SVG próprio no lugar do `span.material-icons`; a diretiva vira `appMarkdownCopy` com `inject()` |
| `7b516f2` … `67ce958` | páginas gerais, barra lateral, markdown, Poli Chat e base de conhecimento sem Material, com `shared/ui`, tokens, signals e regras puras. O chat caiu de 1.573 para cerca de 500 linhas; o stream SSE foi para `data-access/` |
| `7a27651` | o estilo do markdown e do botão de copiar sai do `styles.scss` e vai para `features/poli-chat/components/markdown-content`, com `ViewEncapsulation.None` e todos os seletores presos à classe do host (o HTML entra por `innerHTML`, onde o encapsulamento não chega) |
| `daa9eca`, `dac473c`, `6983cb0`, `a368fb2` | defeitos que já existiam, cada um num `fix` (ver abaixo) |
| `c826400`, `b90824e` | limpeza: skeleton sem uso e nomes de saída |
| `e5dae8b`, `b4c3a16` | revisão: filtros da base de conhecimento com a mesma altura; aviso do rodapé do chat em texto corrido no celular |

**Defeitos que já existiam, corrigidos:**
- a conversa guardada na sessão usava a chave
  `poli-chat-conversation-id:[object Object]`, então todos os departamentos
  dividiam a mesma conversa;
- o histórico era pedido duas vezes ao abrir a tela;
- a conversa aberta pelo histórico não rolava até a última mensagem;
- os anexos de uma pergunta feita na Home se perdiam no caminho para o chat.

**Mudanças visíveis para listar na PR:**
- **Poli Chat:**
  - ícones SVG próprios;
  - menu da conversa: o painel solto virou o menu comum, abaixo do botão,
    com teclado e Esc, e "Excluir" em vermelho;
  - a conversa aberta no histórico ganha fundo tonal (a classe `active` não
    tinha estilo); títulos cortados ganham tooltip;
  - a barra lateral é uma superfície com linha separadora; recolher usa
    `chevrons-left`/`chevrons-right`;
  - links de download do markdown: o botão azul sólido virou tom sobre tom;
  - "Ver payload" usa o mesmo bloco de código das respostas, com copiar;
  - "Resposta de interrupção" virou pílula; avisos viraram toast;
  - responsivo: abaixo de 1200 px saem as margens fixas; abaixo de 900 px o
    histórico começa recolhido e abre por cima do chat; abaixo de 600 px o
    cabeçalho esconde o nome do usuário.
- **Base de conhecimento:**
  - filtro de departamento com o select comum (sem filtro, "Poliedro -
    Geral" aparece marcado);
  - "Novo arquivo" foi para o cabeçalho da página, com spinner;
  - tabela comum com skeleton; estado vazio comum no lugar da imagem;
  - departamento em pílula ("Geral" neutro); excluir é botão de ícone de
    perigo com tooltip; o diálogo de envio é o diálogo comum.
- **Login:** o erro deixou de ser o `app-alert` e virou texto com
  `role="alert"`.
- **Acesso negado e não encontrada:** página de status comum, com botão.

**Para decidir:**
- ícone `more-vertical`: o inventário de ícones não pegou o `more_vert`
  (estava numa linha separada da tag), e o conjunto não tem equivalente. O
  conjunto vai a 149;
- envio na base de conhecimento com só "Poliedro - Geral" liberado: o
  diálogo comparava com `'__all__'`, que nunca existe, e manda
  `department=all` ao BFF, enquanto a lista trata `all` como "sem filtro".
  Mantido; confirmar com o BFF;
- o voltar do cabeçalho do chat usa `window.location.href = '/home'`, que
  recarrega o app. Mantido;
- anexo sem texto não é enviado (o campo comum só envia com texto), nem na
  Home nem no chat. Mantido.

**Encontro com a 18:** a 18 nasce da `master` e mexe nas bibliotecas do
markdown (`dompurify`, `markdown-it`). A 12 mexeu no
`shared/pipes/markdown.pipe.ts` (ícone do copiar e diretiva). Conferir o
merge desse arquivo quando as duas se encontrarem.

**Validação** (base: a 04 com as três correções, 678 testes com 77 falhando e lint 59/281):

| Item | 12 |
|---|---|
| Build | ok |
| Lint | 47 erros / 259 avisos |
| Testes | 792, com 70 falhando, nenhuma falha nova. 7 falhas da base, da área, corrigidas. O `App should render title` continua falhando: é do app raiz |
| Commits | todos compilam sozinhos (`tsc` de app e specs em cada um) |
| Smoke | login (sem sessão), home, Poli Chat, um departamento, base de conhecimento e páginas de erro: claro, escuro, Dots e celular, sem erro de página nem de console |
| Merge | entra sem conflito com 05, 06, 07, 08 e 11 |

Não deu para exercitar com o BFF real: streaming, envio de arquivo à base
de conhecimento e download pelo iframe. Ficam cobertos por specs e
precisam ser conferidos na sandbox.
