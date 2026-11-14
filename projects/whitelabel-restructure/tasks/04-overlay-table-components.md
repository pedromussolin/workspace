+++
card = "TS-5361"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 04 — Componentes: overlay e tabela

- **TS:** TS-5361 · **Branch:** `feature/TS-5361-componentes-overlay-tabela` (da 03)
- **Status:** commits feitos, sem push (11/10)
- **Depende de:** 03. Decisão D5 (tabela).

## Escopo

| Novo (`shared/ui`) | Substitui | Componentes atuais reescritos em cima dele |
|---|---|---|
| `DialogService` + `app-dialog` (cabeçalho, corpo, ações) | `MatDialog` | `confirm-dialog`, `column-filter-dialog`, `entity-drawer` |
| `ToastService` + `app-toast` | `MatSnackBar` | `snackbar` (e o 401 do `authInterceptor`) |
| `appTooltip` | `matTooltip` | — |
| `app-menu` | `mat-menu` | — |
| `app-table` (sobre `@angular/cdk/table`) + `appSort` + `app-paginator` | `mat-table`, `mat-sort`, `mat-paginator` | `table`, `expandable-table`, `generic-table`, `search-table` |
| `app-spinner` | `mat-progress-spinner` | `loading-status` |
| `app-skeleton` (linha, bloco, círculo; respeita reduced motion) | `ngx-skeleton-loader` (90 usos em 19 templates) | os `*-skeleton` dos componentes |
| `app-accordion` | `mat-expansion` | `accordion` |

Inventário (`d0bc3de`): 63 arquivos, 185 cores fixas, 25 `::ng-deep` e 15
specs.

### Shell novo (prévia v5)

Entra aqui porque precisa dos ícones (03) e do tooltip e do menu (acima):
- sidebar de ponta a ponta, fundo `--sidebar-bg` com linha à direita; marca
  e botão de recolher no topo; seções Geral / Módulos / Administrativo que
  abrem e fecham; grupos com árvore de subitens; rodapé com Docs da API,
  Design system e o cartão do usuário (menu com Aparência e Sair, o
  seletor de Aparência escondido até a 13);
- recolhida (68 px) com submenu flutuante no hover; gaveta no celular;
- cabeçalho com voltar (telas de detalhe), trilha com ícones e a ação
  principal da página; título com a descrição visível embaixo;
- aberturas animadas (grupos e seções), com movimento reduzido respeitado;
- comportamento de hoje mantido: menu filtrado por `iam/paths`, grupo da
  rota aberto, header e sidebar sem recriar na navegação.
- Specs: abrir/fechar grupo e seção, recolher, flyout, gaveta, menu do
  usuário, trilha por rota, ação da página.

## Regras

- O `DialogService` mantém a forma de uso do `MatDialog`: `open(Component,
  { data })`, `afterClosed()` e o token de `data`. Assim as telas trocam o
  import sem reescrever a lógica.
- O `ToastService` mantém os tipos `success`, `error`, `warning` e `info`,
  a duração e a ação "Fechar".
- O visual da tabela segue Lotes de Liquidação: cabeçalho de 11 px em
  maiúsculas, linhas sem borda pesada e card com raio 12. A tabela aninhada
  da linha expandida não pode herdar estilo da tabela de fora (hoje isso é
  resolvido com seletores de filho em `_batches-shell.scss`).

## Validação

- Diálogo: foco preso, `Esc` fecha, o foco volta ao botão que abriu e a
  rolagem do fundo trava. Hoje existe um ajuste do `cdk-global-scrollblock`
  em `styles.scss` que precisa continuar funcionando.
- Tabela: ordenação, paginação, linha expandida, tabela aninhada e estado
  vazio.

## O que foi feito (11/10/2026)

| Commit | O quê |
|---|---|
| `def1b05` feat | tooltip próprio com overlay único e modo truncado |
| `6b1357c` feat | menu próprio com gatilho, itens e navegação por teclado |
| `abbf463` feat | app-spinner com tamanhos, diameter e progressbar acessível |
| `424ebf2` feat | app-skeleton com brilho e entradas do ngx-skeleton-loader |
| `8fbae3a` refact | menu do portal num arquivo só, com os ícones próprios |
| `3558978` feat | cabeçalho da página com trilha, voltar e descrição |
| `7da78b8` feat | sidebar de ponta a ponta, com trilho e gaveta no celular |
| `ce9f178` refact | sidebar e cabeçalho usam o tooltip próprio |
| `eddf441` feat | acordeão próprio, com abertura animada e teclado |
| `15c3656` refact | loading-status sobre os componentes próprios |
| `b0815ca` refact | accordion sobre os componentes próprios |
| `24c91bf` feat | diálogo próprio sobre o CDK, no formato do MatDialog |
| `2ca5b56` feat | toast próprio com tipos, duração e ação de fechar |
| `6001a30` fix | ações da gaveta no rodapé do diálogo lateral |
| `5b28098` refact | confirm-dialog sobre o diálogo próprio |
| `28e16e8` refact | snackbar sobre o toast próprio |
| `de19cf0` refact | entity-drawer sobre o diálogo próprio |
| `7eacae2` refact | column-filter-dialog sem Material e com botões próprios |
| `a2d3681` fix | confirm-dialog e snackbar abertos pelo Material ainda funcionam |
| `c810607` feat | ordenação e paginador próprios para a tabela |
| `f46f164` feat | tabela própria no cdk/table, com ordenação e paginação |
| `3d21506` refact | tabela sobre a tabela própria |
| `75812b3` refact | tabela expansível sobre a tabela própria |
| `8be0811` refact | tabela genérica sobre a tabela própria |
| `fad6041` refact | tabela com busca sobre a tabela própria |
| `b6fc2b2` test | specs de tela fornecem a rota pedida pelo cabeçalho |

Diferenças visíveis e de comportamento (para a descrição da PR):
- Shell novo: sidebar de ponta a ponta (aberta empurra o conteúdo e não
  recolhe mais a cada navegação; recolher fica salvo), usuário e Sair no
  rodapé, sem header no topo; trilha com o módulo, voltar nas telas de
  detalhe e descrição visível embaixo do título (no lugar do "?").
- Tabelas: visual novo (cabeçalho, hover, linha aberta sem cartão e com
  barra à esquerda, detalhe preso à largura visível), linha abre por teclado,
  paginador próprio com primeira/última página, texto longo com reticências.
- Diálogos e gaveta: animação curta; no celular, botões empilhados. Gaveta
  fecha com Esc e fica travada enquanto salva.
- Toast: duração padrão por tipo (4–8 s) quando a tela não define, pausa no
  hover, até 4 empilhados, sempre embaixo à direita.
- Acordeão e loading-status sobre os componentes próprios; duas inscrições
  que nunca eram encerradas agora são.
- `confirm-dialog` e `snackbar` aceitam ser abertos pelo Material ou pelos
  serviços novos até as telas migrarem.
- Regras `::ng-deep` de Pré-Trade, Lotes e Envio de Relatórios que miravam
  classes do Material viraram inócuas (limpeza nas tarefas de área).

Para a 13: ao tirar o tema do Material do `angular.json`, incluir
`@angular/cdk/overlay-prebuilt.css`.

### Validação

| Checagem | Resultado |
|---|---|
| `npm run build` | passa |
| `npm run lint` | 59 erros / 281 avisos (03: 64 / 278; nenhum erro novo) |
| Testes | 674 testes, 76 falhando. Nenhuma falha nova em relação à 03 |
| Smoke com BFF falso | 29 rotas em desktop e celular, sem erro no console; o shell persiste na navegação |


### Correções depois da publicação (15/10)

Os problemas apareceram na revisão das áreas 07 e 08. Cada correção tem um
teste que falha sem ela. Os três commits foram publicados em 15/10.

| Commit | O quê |
|---|---|
| `d1c63b0` | **Seta de ordenar sobrepunha o nome da coluna** quando a tabela fica justa. Causa: o botão do cabeçalho tinha `max-width: 100%`. Para o navegador, um botão com largura máxima em porcentagem pode encolher até zero, então a coluna ficava mais estreita que o texto. |
| `3ea9153` | **No celular, o controle segmentado cortava as opções** em "T…" e "P…" quando tem muitas, como os 5 status da Formalização. Agora a opção nunca encolhe abaixo do texto e o grupo rola na horizontal. Com poucas opções, elas continuam ocupando a largura toda. |
| `779aa13` | **Rolagem lateral na página do celular** quando a tabela é mais larga que a tela. Causa: o texto que só o leitor de tela lê (`position: absolute`) escapava do recorte do wrapper da tabela. O wrapper agora é `position: relative`. A correção veio da 07 e subiu para a 04 |

O controle segmentado veio da 03, mas a correção entrou na 04 para não
mexer em duas branches publicadas. As áreas 07, 08 e 11 nascem desta 04
nova.

### Correção de contraste (15/10, sem push)

| Commit | O quê |
|---|---|
| `e031e31` | **Texto discreto e status "pendente" com contraste AA** (A20; Pietro: "escolha a cor mais próxima que atenda a regra"). Cada cor foi escurecida (no claro) ou clareada (no escuro) só na luminosidade, mantendo o tom, até 4,5:1 sobre a superfície e o fundo: `--text-faint` `#94a3b8` → `#667488` e `#6b7d8a` → `#798c99`; `--st-pendente` `#f57c00` → `#c55000` e `#c76a0a` → `#ca6c10`. O desabilitado fica fora da regra e mantém o cinza de antes. Spec novo `core/theme/tokens-contrast.spec.ts` mede os tokens de texto nos dois esquemas e falha sem a correção |

- **Visível:** placeholders, ícones discretos e textos de apoio "faint"
  ficam mais escuros no claro. No claro, o `--text-faint` fica quase igual
  ao `--text-muted` (`#64748b`). O laranja do status "pendente" fica mais
  fechado.
- **Para publicar:** a 04 ganha esse commit. As áreas não precisam ser
  refeitas: elas recebem a correção quando a 04 entra na `sandbox`.
