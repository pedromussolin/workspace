# Design system

Este documento é a proposta inicial. Os valores fecham na tarefa 02. O ponto
de partida é o que as páginas de referência (Pré-Trade e Lotes de
Liquidação) já usam hoje.

## O que as páginas de referência usam

Contagem em `pages/pre-trade` e `pages/operations/liquidation-batches`, só
nos arquivos `.scss`:

| Uso | Valores mais frequentes |
|---|---|
| Neutros (escala "slate") | `#0f172a` (35×), `#334155`, `#475569`, `#64748b` (51×), `#94a3b8` (45×), `#cbd5e1`, `#e2e8f0` (40×), `#f1f5f9`, `#f8fafc` (39×), `#fff` (65×) |
| Marca | `#0d8291` (secundária, 46×), `#0f3443` (primária, 19×) |
| Sucesso | `#15803d` / `#16a34a`, fundo `#dcfce7` |
| Perigo | `#b91c1c` / `#c62828`, fundo `#fee2e2` / `#fef2f2` |
| Atenção | `#b45309`, fundo `#fef3c7` / `#fffbeb` |
| Raio | 8 px (30×), pílula 999 px (29×), card 12 px (14×), 10 px (11×) |
| Foco | anel de 3 px com a secundária a 10–25% |
| Sombra de card | `0 1px 6px rgba(15, 52, 67, .05)` e `0 2px 10px rgba(15, 23, 42, .09)` |
| Cabeçalho de tabela | 11 px, maiúsculas, `letter-spacing` .6 px, fundo `#f8fafc`, texto `#64748b` |

Na prática, as duas telas já seguem um mesmo sistema. Ele só não foi
escrito em lugar nenhum: as cores estão fixas em cada arquivo, e por isso
nenhum tema chega nelas.

## Camadas de token

1. **Marca:** muda por deploy (`THEME_KEY`). São só as cores principais, nas
   versões clara e escura.
2. **Semânticos:** comuns a todas as marcas. Mudam entre claro e escuro.
3. **Componente:** quando um componente precisa de um ajuste próprio (ex.:
   `--table-header-bg`), ele aponta para um semântico. Nunca para uma cor
   solta.

### Marca

| Token | Poliedro claro | Dots claro | Cerys claro | Viva claro |
|---|---|---|---|---|
| `--brand-primary` | `#0f3443` | `#e04508` | `#ff8f1c` | `#79009d` |
| `--brand-secondary` | `#0d8291` | `#ee7342` | `#1e1e1e` | `#9333ea` |
| `--brand-on-primary` (texto sobre a primária) | `#fff` | `#fff` | a medir | `#fff` |

Versão escura proposta (D2, aprovada para eu propor em 10/10; valores em
avaliação na [prévia](https://claude.ai/artifact/5rUQj8R3zYrg3Zry4U9Bod)).
Contraste medido contra `--bg` escuro `#0e171e` e `--surface` escuro `#141f27` (o spec `themes.spec.ts` confere a cada mudança):

| Marca | Primária escuro | Secundária escuro | Texto sobre a primária | Primária/fundo | Secundária/superfície | Texto/primária |
|---|---|---|---|---|---|---|
| Poliedro | `#5fb8c6` | `#4fc3d0` | `#062029` | 7,9 | 8,0 | 7,4 |
| Dots | `#ff7a45` | `#ff9a6e` | `#1a0a03` | 7,0 | 8,1 | 7,5 |
| Cerys | `#ffa64d` | `#d4d4d4` | `#1f1300` | 9,3 | 11,3 | 9,4 |
| Viva | `#c77dff` | `#b98cff` | `#1f0029` | 6,7 | 6,6 | 7,2 |

Todos passam AA (4,5:1). **No claro**, os valores de hoje não mudam
(regra de não alterar o visual), mas cinco pares ficam abaixo de 4,5:1 e
vão como achado A13 (Dots e Cerys).

Os tokens implementados estão em `src/styles/_tokens.scss` (TS-5359). A
tabela de semânticos abaixo é a proposta inicial; vale o arquivo.

### Semânticos (proposta)

| Token | Claro | Escuro (rascunho) |
|---|---|---|
| `--bg` (fundo da página) | `#f8fafc` | `#0d151b` |
| `--surface` (card, tabela, diálogo) | `#ffffff` | `#141f27` |
| `--surface-muted` (cabeçalho de tabela, áreas secundárias) | `#f1f5f9` | `#1a2731` |
| `--border` | `#e2e8f0` | `#26353f` |
| `--border-strong` | `#cbd5e1` | `#34454f` |
| `--text` | `#0f172a` | `#e6edf2` |
| `--text-secondary` | `#475569` | `#b4c2cc` |
| `--text-muted` | `#64748b` | `#93a3b0` |
| `--text-disabled` | `#94a3b8` | `#5f707c` |
| `--success` / `--success-soft` | `#15803d` / `#dcfce7` | `#5cc98f` / `#16301f` |
| `--warning` / `--warning-soft` | `#b45309` / `#fef3c7` | `#f0a648` / `#33250f` |
| `--danger` / `--danger-soft` | `#b91c1c` / `#fee2e2` | `#f07a7a` / `#3a1a1a` |
| `--info` / `--info-soft` | `#1d4ed8` / `#dbeafe` | `#7aa7f5` / `#172741` |
| `--focus-ring` | secundária a 25% | secundária a 40% |
| `--shadow-card` | `0 1px 6px rgb(15 52 67 / .05)` | `0 1px 2px rgb(0 0 0 / .3)` |

Outros tokens: raio (`--radius-sm` 6, `--radius` 8, `--radius-lg` 12,
`--radius-pill` 999), espaçamento em passos de 4 px e a escala de fonte
(11 / 12 / 13 / 14 / 16 / 18 / 20 / 24).

As cores de status de lote, pré-trade e orquestrador (cadastrado, liquidando,
liquidado...) passam a apontar para esses semânticos. Hoje cada tela tem
cores próprias para o mesmo significado.

## Navegadores

Os navegadores-alvo são Chrome, Edge e Safari, nas duas últimas versões, e
o iOS Safari no celular. Antes de usar algum recurso de CSS, confirmar que o
Safari tem suporte:

| Recurso | Safari | Uso |
|---|---|---|
| `color-mix()` | 16.2+ | variações da cor de marca |
| `light-dark()` | 17.5+ | evitar; usar os blocos de `:root` por esquema |
| `:has()` | 15.4+ | pode usar |
| `::-webkit-scrollbar` | sim | o Firefox não é alvo |
| `scrollbar-color` | só em versões muito recentes (conferir) | só como complemento |
| `<dialog>`, `popover` | 15.4+ / 17+ | o overlay vem do CDK, não do nativo |
| `100dvh` | 15.4+ | usar no celular no lugar de `100vh` |

O E2E roda no WebKit, que é o motor do Safari (tarefa 16).

## Claro, escuro e sistema

- O `:root` recebe `data-scheme="light|dark"` só quando o usuário escolhe.
  Sem escolha, vale `prefers-color-scheme`.
- A escolha fica no `localStorage`, sempre dentro de `try/catch`.
- Um script mínimo no `index.html` aplica a escolha **antes** do Angular
  subir. Sem ele, a tela piscaria clara antes de ficar escura.
- `color-scheme: light dark` no `:root` faz barras de rolagem e controles
  nativos acompanharem o tema.
- Gráficos: componentes próprios em `shared/ui/charts`, desenhados em SVG
  pelo código do componente (D10). As cores vêm dos tokens no CSS, então a
  troca de esquema não precisa redesenhar o gráfico.
- O seletor fica no menu do usuário (rodapé da sidebar), com Claro / Escuro / Sistema. Ele só aparece na
  tarefa 13 (ver [decisoes.md](decisoes.md)).

## Componentes próprios (`shared/ui`)

O `@angular/cdk` entra só por baixo: overlay, foco, teclado, drag-drop e a
estrutura de tabela. O visual é todo nosso.

| Componente | Substitui | Tarefa |
|---|---|---|
| `app-icon` | `mat-icon`, fonte Material Icons/Symbols | 03 |
| `app-button`, `app-icon-button` | `mat-button`, `mat-icon-button` | 03 |
| `app-field` (rótulo, ajuda, erro) + `input`/`textarea` | `mat-form-field`, `matInput` | 03 |
| `app-select`, `app-multiselect`, `app-combobox`/autocomplete | `mat-select`, `mat-autocomplete` | 03 |
| `app-checkbox`, `app-radio`, `app-toggle-group` | `mat-checkbox`, `mat-radio`, `mat-button-toggle` | 03 |
| `app-date-picker` | `mat-datepicker` (+ moment adapter) | 03 |
| `app-dialog` (serviço + casca) | `MatDialog` | 04 |
| `app-toast` (serviço) | `MatSnackBar` | 04 |
| `appTooltip` (diretiva) | `matTooltip` | 04 |
| `app-menu` | `mat-menu` | 04 |
| `app-table` + ordenação + `app-paginator` | `mat-table`, `mat-sort`, `mat-paginator` | 04 |
| `app-spinner`, skeleton | `mat-progress-spinner` (o `ngx-skeleton-loader` fica) | 04 |
| `app-accordion` | `mat-expansion` | 04 |

Os componentes que já existem em `components/` são reescritos sobre essas
peças, sem mudar as entradas e saídas que as telas usam, e ficam como
adaptadores até as telas trocarem para `shared/ui` (tarefas de área). A 13
apaga os que sobrarem.

## Ícones

- São 148 SVGs próprios: grade de 24 px, traço de 1,75, pontas e junções
  arredondadas, cor `currentColor`.
- Eles substituem os 179 nomes do Material usados no front.
- Fonte e scripts ficam em [anexos/icones/](anexos/icones/). A página de
  revisão é https://claude.ai/artifact/Hi6hgNKrGGRgofWWHh3Dds.
- O nome é um tipo fechado (`IconName`). Nome inexistente dá erro de
  compilação.
- Na migração de cada área, [material-para-novo.json](anexos/icones/material-para-novo.json)
  diz qual ícone novo usar para cada nome antigo.
- Para regenerar os SVGs e a página: `cd anexos/icones && node build.mjs`.
