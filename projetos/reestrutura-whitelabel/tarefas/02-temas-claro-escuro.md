# 02 — Temas claro e escuro

- **TS:** TS-5359 · **Branch:** `feature/TS-5359-temas-claro-escuro` (da 01)
- **Status:** commits feitos, sem push (10/10)
- **Depende de:** 01. Decisões D2, D3 e D4.

## Escopo

1. Escrever os tokens de [design-system.md](../design-system.md) em
   `src/styles/` (`_tokens.scss`, `_base.scss`): semânticos claros e
   escuros, raio, espaçamento e escala de fonte.
2. Mudar o `ThemeService` (em `core/theme/`) para:
   - aplicar só os tokens de marca (claro e escuro) da marca do deploy;
   - controlar o esquema Claro / Escuro / Sistema, com a escolha salva no
     `localStorage`;
   - expor o esquema efetivo como signal, para gráficos e componentes.
3. Colocar no `index.html` o script que aplica o esquema antes do Angular
   subir, para a tela não piscar.
4. Converter `styles.scss` (scrollbar, `.card`, `.btn-primary`, snackbar)
   para tokens. O app-shell não é convertido aqui: ele é redesenhado na 04
   (sidebar, cabeçalho e cabeçalho da página da prévia v5), que já nasce em
   tokens e precisa dos ícones (03) e do tooltip e do menu (04).
5. Propor os valores escuros de cada marca, com contraste medido (D2).
6. Ficar só com Inter (D4) e tirar Roboto e Sora do `@import`, se aprovado.

## Fora do escopo

- O seletor de esquema (Claro / Escuro / Sistema) no menu do usuário, no rodapé da sidebar. Ele existe, mas fica escondido até a 13.
- Telas de área. Elas migram nas tarefas 05–12.

## Pontos de atenção

- O tema prebuilt do Material (`azure-blue.css` no `angular.json`) continua
  até a 13. No modo escuro forçado, os componentes do Material ficam claros.
  É esperado, e o motivo de o botão ficar escondido.
- Nomes de variáveis antigos (`--color-primary`, `--color-bg`...) seguem
  com os valores de hoje até cada área migrar (apontar para os tokens
  mudaria o visual das telas que ainda não migraram: `--color-text` é
  `#525252`, `--color-surface` é a cor da marca). A 13 apaga.

## Validação

- Poliedro, Dots, Cerys e Viva trocando o `themeKey` no `assets/env.js`.
- Esquema escuro forçado (`data-scheme="dark"` no `<html>`) no shell.
- Contraste AA (4,5:1 para texto) da primária e da secundária sobre `--bg`
  e `--surface`, em claro e escuro, por marca.

## O que foi feito (10/10/2026)

| Commit | O quê |
|---|---|
| `ebedc46` feat | `src/styles/_tokens.scss` (marca, semânticos claro/escuro, tom sobre tom, status, sidebar, gráficos, sombras, raio, espaço, fonte e movimento) e `_base.scss` (`color-scheme`, seleção e barra de rolagem). `styles.scss` usa os tokens em `.card`, `.btn-primary`, snackbar e na fonte |
| `fcfe7e4` feat | Cada marca declara primária, secundária e texto sobre a primária no claro e no escuro. O `ThemeService` grava `--brand-*-light` e `--brand-*-dark`; o CSS escolhe pelo `data-scheme`. Usa `inject(DOCUMENT)` |
| `527fe7d` feat | `ColorSchemeService`: preferência (claro, escuro, sistema) em signal, esquema efetivo em `computed`, escolha salva no `localStorage` (com `try/catch`), acompanha a troca do sistema e grava `data-scheme` no `<html>`. Script no `index.html` aplica o esquema antes do Angular subir |
| `af83519` test | Contraste AA das cores de marca, lendo os tokens reais do CSS |
| `22e7830` chore | Só Inter (D4): saem Roboto e Sora. O Material, que usava Roboto, passa a usar Inter até a 13 |

Como o escuro fica desligado até a 13: o `<html>` sai com
`data-scheme-default="light"`. Sem escolha salva, o portal fica claro mesmo
com o sistema no escuro. Na 13, basta trocar para `"system"` e mostrar o
seletor. Para testar o escuro agora: `localStorage.setItem('portal.color-scheme', 'dark')`
e recarregar.

Mudanças visíveis (para a descrição da PR):
- Campos do Material (rótulos e textos de `mat-form-field`, `mat-select`)
  saem de Roboto para Inter. Na regressão, só a tela de editar produto do
  Orquestrador mudou, e só por isso.
- Barra de rolagem: trilho `#e4e4e4` → `--surface-sunken` (`#f1f5f9`),
  alça `#cfcfcf` → `--border-strong` (`#cbd5e1`).
- `.card` global: raio 12 → 14 px e borda `--line`.
- Snackbar: verde, vermelho, laranja e azul passam aos tons de status dos
  tokens.

### Validação

| Checagem | Resultado |
|---|---|
| `npm run build` | passa |
| `npm run lint` | 71 erros / 285 avisos, igual à 01 (nenhum novo) |
| Testes | 283 testes, 88 falhando, as mesmas da 01. Os 20 novos passam |
| Regressão visual (29 rotas, desktop e celular, contra a 01) | 54 de 58 idênticos. Diferem: editar produto (fonte Inter no Material, esperado), Home e login celular (vídeo do robô) e Orquestrador (10 px, o mesmo ruído da 01) |
| Contraste no escuro (fundo `#0e171e`, superfície `#141f27`) | todas as marcas ≥ 6,2:1 em primária e secundária; texto sobre a primária ≥ 7,1:1 |
| Contraste no claro | 5 casos abaixo de AA, todos de hoje (A13, atualizado) |

Não validado: as quatro marcas no navegador com o escuro forçado. Como o
shell e as telas ainda não usam os tokens, o escuro não aparece em nada
além de controles nativos e barras de rolagem; a validação visual de verdade
vem com o shell novo (04).

