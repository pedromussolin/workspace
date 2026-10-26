# 10 — Orquestrador

- **TS:** TS-5367 · **Branch:** `refact/TS-5367-orquestrador-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** em andamento (15/10, 3ª leva)
- **Depende de:** 04
- **Passos e critério de pronto:** [area-playbook.md](area-playbook.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/orchestrator` | `pages/orchestrator/orchestrator/` (com funil e detalhe de processo) |
| `/orchestrator/flow/:flowId` | `pages/orchestrator/flow-detail/` |
| `/orchestrator/product-config` | `pages/orchestrator/product-config/list/` |
| `/orchestrator/product-config/:id` | `pages/orchestrator/product-config/edit/` |

## O que vai para `features/orchestrator/`

- As quatro telas.
- `services/orchestrator.service.ts` e `interfaces/orchestrator.interface.ts`.
- `components/entity-drawer`: só é usado pelo `product-config-edit` e
  depende do `product.service`. É componente da feature, não genérico.
- `services/product.service.ts` e `interfaces/product-config.interface.ts`
  são usados também por onboarding-bgt e users. Ver a decisão D7.

Inventário (`d0bc3de`): 18 arquivos, 6.743 linhas, **382 cores fixas**, 1
`::ng-deep`, **0 specs**. Material: tooltip (5), spinner (5), icon (5),
snack-bar (4), select (3), table, paginator, form-field e expansion.

## Fluxos críticos

- Listagem e funil por status. O mapa status → ícone e classe passa a usar
  `IconName` e os semânticos.
- Detalhe de fluxo com subfluxos e processos.
- Config de produto: os toggles (`toggle_on` e `toggle_off` desenhados como
  ícone viram o `app-switch` de `shared/ui`, com `role="switch"`, criado
  nesta tarefa pela D11) e o salvamento.

## Pontos de atenção

- Sem nenhum spec. Antes de mexer, escrever specs mínimos para o mapeamento
  de status e para o salvamento da config de produto, e só então refatorar.

## O que foi feito (15/10/2026)

Branch `refact/TS-5367-orquestrador-nova-arquitetura`, criada da 04 com as
três correções de 15/10. São 18 commits.

| Commits | O quê |
|---|---|
| `0e143a3` | D7: `product.service` e a interface vão para `features/products/data-access/`, com um `index.ts` público. Em onboarding e usuários, só o import muda |
| `1a3743d`, `c005aac` | move o orquestrador, a config de produto e o `entity-drawer` para `features/orchestrator/` e cria a rota com `loadChildren`. URLs, guards e trilhas ficam iguais |
| `f0c9de5`, `2a0d83e`, `bf5f429`, `f4e757f` | cópias (cherry-pick) da 05 e da 11, com conteúdo idêntico: select com limpar, pílula/KPI/estado vazio, valor vazio e `search-table` sem tipo do Material |
| `c59a570` | specs de base, escritos antes de refatorar: mapa de status, payload do salvamento e carga/filtro da listagem. A área tinha 0 specs |
| `4583226`, `a49b988` | `app-switch` em `shared/ui` (D11): `role="switch"`, teclado, formulário e rótulo ligado ao botão |
| `980443c` … `a5cb0cf` | status com `IconName` e tons semânticos, tela principal em componentes (barra de filtros, KPIs, funil, listas), detalhe do flow com accordion, lista e edição de produto em componentes. Tudo com signals, OnPush e tokens, sem Material |
| `06a90a7` | limpeza: `FunnelPage` sem uso apagada (A11), `any` → `unknown` e valor vazio comum |
| `9947363` | revisão: as telas de detalhe ganham o voltar no cabeçalho (pai "Orquestrador" e "Produtos") |
| `0a58922` | revisão: config do orquestrador sem `webhooks` ou processo sem `settings` não quebra mais a edição. Antes, um `Object.keys` em `undefined` parava a tela no meio |

**Mudanças visíveis para listar na PR:**
- **Filtro por status:** os chips com contador da barra de filtros viraram
  uma linha de KPIs filtráveis, com "Clique para filtrar a lista" e
  "Filtrando a lista abaixo". Clicar no ativo tira o filtro, como antes.
- **Funil:** os cards coloridos com barrinha de proporção viraram o KPI
  comum, sem a barrinha. O tooltip com contagem e percentual continua.
- **Status:**
  - o chip colorido virou pílula tonal com ícone;
  - nenhuma cor mudou de família (A4): pendente continua laranja, no tom
    de atenção;
  - no detalhe do flow, COMPLETED aparece "Sucesso", como na tela
    principal, e CANCELED aparece "Cancelado" (antes saía o código).
- **Abrir e fechar:** flows, subflows e processos usam o accordion animado;
  o chevron foi para a direita. Request/Response virou controle segmentado.
- **Re-run:** botão comum com spinner; no celular, só o ícone. Ele saiu de
  dentro do botão do cabeçalho do processo (era botão dentro de botão).
- **Avisos e estados:** toast no lugar do snackbar, spinner, estado vazio e
  paginador próprios.
- **Lista de produtos:** "Novo" foi para o cabeçalho da página.
- **Edição do produto:**
  - "Salvar/Criar Produto" no cabeçalho; o "Voltar" do topo virou a seta
    de voltar do cabeçalho; a barra de baixo continua;
  - os selects mostram "Nenhum"/"Nenhuma" quando vazios e têm o X de
    limpar, no lugar da opção "— Nenhum —". "Criar novo" ganhou ícone de +
    e, ao abrir a gaveta, o select volta para a escolha anterior (antes
    ficava mostrando "Criar novo");
  - as flags e os Ativado/Desativado (ícones `toggle_on`/`toggle_off`)
    viraram `app-switch`; o salvamento é o mesmo;
  - Formulário/JSON virou controle segmentado; o erro do JSON aparece
    logo abaixo do campo;
  - subflows e processos da config em accordion, com o título
    "S1 · nome"; "Opcional" virou caixa de marcar; o destino vazio virou
    "—".
- **Gaveta de entidade:** o select do pseudônimo é o select comum.

Mantido como era: o nome de uma webhook destination nova vem do `prompt()`
do navegador, e "Limpar filtros" aparece quase sempre, porque o período
padrão conta como filtro.

**Encontro com a 11 no merge:** a 11 já moveu onboarding e usuários para
`features/`, e a 10 troca o import do `product.service` nesses mesmos
arquivos, ainda em `pages/`. No merge das duas (quem entrar por último na
`sandbox`), dá conflito modify/delete em 3 arquivos
(`onboarding-bgt-listing.page.ts`, `onboarding-bgt-monitoring.page.ts` e
`users.page.ts`). Resolução:
1. ficar com a versão da 11 (apagar os de `pages/`);
2. nos arquivos da 11 em `features/onboarding-bgt/` e `features/users/`
   (inclusive specs), trocar o import de `services/product.service` e
   `interfaces/product-config.interface` pelo `features/products/data-access`;
3. rodar o build.

O passo a passo acima foi testado num merge descartável: todas as áreas
publicadas mais a 12 e a 10 juntas compilam (app e specs). No merge real,
vale juntar numa linha só os dois imports que passam a vir do mesmo módulo.

**Validação** (base: a 04 com as três correções, 678 testes com 77 falhando e lint 59/281):

| Item | 10 |
|---|---|
| Build | ok |
| Lint | 59 erros / 273 avisos |
| Testes | 771, com 77 falhando, nenhuma falha nova. Specs da área e do `app-switch`: 94/94 |
| Commits | todos compilam sozinhos (`tsc` de app e specs em cada um) |
| Smoke | com dados fictícios do orquestrador: claro, escuro, Dots e celular, sem erro de página nem de console |

Não deu para exercitar com o BFF real: re-run, salvamento da config e
criação de entidade pela gaveta. Ficam cobertos por specs e precisam ser
conferidos na sandbox.
