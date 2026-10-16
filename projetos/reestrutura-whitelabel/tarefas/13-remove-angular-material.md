# 13 — Remove Angular Material

- **TS:** TS-5370 · **Branch:** `chore/TS-5370-remove-angular-material`
- **Status:** **commits feitos, sem push** (16/10)
- **Depende de:** 01–12, 14 e 15

## Como está sendo feita (15/10)

- **Base `2dbb699`:** a 04 (com `e031e31`) mais o merge, nesta ordem, da
  14, da 15 e das áreas 05 a 12.
  - Cada merge é um commit `chore(TS-5370): junta a NN (...)`.
  - A 08 entra já com a master (`dabea02`).
  - O conflito conhecido da 11 com a 10 usa a resolução de sempre.
- **Números da base:**
  - build ok, com bundle inicial de 587,87 kB (156,06 kB na rede);
  - lint com 20 erros e 166 avisos;
  - 1.822 testes, com 1 falha ("App should render title").
- **Duas metades em paralelo, com fronteira de arquivos:**
  - **13a**, na própria branch: tira o Material e as bibliotecas, migra ou
    apaga as sobras de `components/`, `interfaces/` e `constants/`, cuida
    da configuração, das variáveis antigas, do seletor de tema, do A13, do
    A18, do lint e da documentação no repo;
  - **13b**, em `wip/TS-5370-consistencia`: faz a passada de consistência,
    com `app-kpi`, `app-card`, `app-code-block`, id do tooltip, A19,
    `app-search-field`, `kpi-grid`, Formalização, Report Transfer, A14, A15
    e o "baixar imagem" no `app-chart`.
  - Cada ajuste em peça comum fica num commit isolado.
  - No fim, os commits da 13b entram por cima da 13a.

## Escopo

1. Remover `@angular/material`, `@angular/material-moment-adapter`, `ngx-skeleton-loader`, `apexcharts` e `ng-apexcharts` (D10; a 09 já tira o script do `angular.json`) do
   `package.json` e do lockfile. O `@angular/cdk` fica. Avaliar se o
   `moment` ainda é usado fora do adapter.
2. Remover o `azure-blue.css` do `angular.json`, os `<link>` das fontes
   Material Icons e Material Symbols do `index.html` e os overrides
   `.mat-*` de `styles.scss`.
3. Apagar o `<app-layout>` antigo, as variáveis CSS antigas
   (`--color-primary`...) e os aliases de entradas mantidos na 03.
4. **Ligar o seletor Claro / Escuro / Sistema no menu do usuário.**
5. Lint:
   - `no-restricted-imports` para `@angular/material` e para imports entre
     features;
   - uma checagem que barra cor hex nova em `.scss` fora de
     `styles/_tokens.scss`.
6. Documentação no repo: `docs/architecture.md` (estrutura, regras de
   dependência, rotas, tokens, como criar uma feature nova) e `AGENTS.md`
   (regras estáveis para quem mexer no repo).

## Validação

- `grep -r "@angular/material\|mat-icon\|material-icons" src` sem resultado.
- Build de produção: comparar o tamanho do bundle inicial com o baseline da 01.
- Volta completa no navegador: todas as rotas, em Poliedro e Dots, claro e
  escuro, e no celular.

- Ao tirar `azure-blue.css` do `angular.json`, incluir `@angular/cdk/overlay-prebuilt.css` (diálogo, menu e tooltip próprios usam o overlay do CDK).

## O que foi feito (15 e 16/10/2026)

Branch `chore/TS-5370-remove-angular-material`, sem push. Sobre a base
`2dbb699` (a 04 mais o merge de todas as áreas) estão:
- 24 commits da 13a;
- 25 commits da 13b, trazidos com cherry-pick por cima. A correção
  repetida do spec do histórico do Pré-Trade ficou só a da 13a;
- o merge da 08 nova (`ebdcffd`), com o ajuste dos filtros;
- 2 commits de revisão (`fda2bd8`, `caf049b`): os 7 textos que usavam a
  `--brand-secondary` crua passam ao `--brand-ink`, que fica em AA na Dots.

### 13a: Material fora, tema ligado

| Commits | O quê |
|---|---|
| `3fdb7dc`…`85d078f` | migra o que ainda usava o Material: avisos pelo `ToastService`, tabelas antigas com `app-skeleton`/`appIconButton`/`appTooltip`, `confirm-dialog` e `date-formats` sem Material, e ícones com nomes próprios |
| `05411af` | só move (68 renomeações). `components/`, `interfaces/` e `constants/` vão para `shared/ui` (`confirm-dialog`, `error`, `textbox`, `file-chip`, `config-table`), `shared/utils`, `core/config` e `core/auth`, ou para a feature dona |
| `0700914` | apaga os adaptadores antigos e o mapa de ícones do Material |
| `59e19fd`, `f5472be` | overlay do CDK no lugar do `azure-blue.css`, sem as fontes de ícone. Saem `@angular/material`, `material-moment-adapter`, `ngx-skeleton-loader`, `apexcharts`, `ng-apexcharts` e `moment` |
| `1b722bd` | apaga as variáveis antigas (`--color-*`) e o `vars` das marcas |
| `e9733d6` | seletor Claro / Escuro / Sistema no menu do usuário. O padrão passa a ser "Sistema" |
| `563328b` | A13: contraste das marcas (tabela abaixo) e spec de AA nas 4 marcas e nos 2 esquemas |
| `8760894` | vitrine com confirmação, erro, anexo e caixa de mensagem |
| `9892477` | o script do esquema de cor sai do inline para `assets/color-scheme.js`, por causa da CSP da 18 |
| `54662d9`, `8e6f827`, `2d93da1` | A18: logo claro da Poliedro; placa clara atrás do logo nas outras marcas; robô do Poli, ícone da OpenAI e ilustração do 404 clareados; fundo do login sem a ilustração no escuro |
| `b952a10` | o login preserva a aparência escolhida ao limpar o armazenamento |
| `46b6d9e`, `17014ac`, `bbee97e`, `68c8066` | lint: barra Material, import entre features (exceção: barril de `products/data-access`, D7), entre camadas, feature importando o shell, e cor fixa nos `.scss` (`scripts/check-scss-colors.mjs`) |
| `12a4a01` | `docs/architecture.md` e `AGENTS.md`, com a nota do `config-table` legado (A22) |
| `8bd45bf` | spec do histórico do Pré-Trade que falhava entre 0h e 1h |

**Contraste (A13), tema claro.** Segue a regra do A20: a cor mais próxima
que atende AA, mudando só a luminosidade.

| Marca | Cor | Antes | Depois | Contraste |
|---|---|---|---|---|
| Dots | primária | `#e04508` | `#d34108` | sobre `--bg` 4,07 → 4,51; branco sobre ela 4,18 → 4,64 |
| Dots | texto da marca (`--brand-ink`) | mistura `#c6623e` | `#ae5433` | sobre `--bg` 3,92 → 4,97; sobre a pílula 3,56 → 4,51 |
| Dots | secundária | `#ee7342` | sem mudança (fundos) | — |
| Cerys | texto sobre a primária | `#ffffff` | `#1e1e1e` | 2,28 → 7,30 |
| Cerys | primária como texto (`--brand-primary-text`) | `#ff8f1c` | `#b65c00` | sobre `--bg` 2,22 → 4,52 |
| Cerys | primária (fundos) | `#ff8f1c` | sem mudança | — |

A Poliedro e a Viva passam em todos os pares sem ajuste.

### 13b: passada de consistência

| Commits | O quê |
|---|---|
| `535bbd7` | `app-kpi`: KPI simples e filtrável lado a lado com a mesma altura |
| `1584258` | `app-card`: `flush` como atributo sem valor |
| `bc31f5d`, `e4009cd`, `9443eef` | `app-code-block` copia pelo Clipboard do CDK e anuncia; o JSON do onboarding usa o `app-code-block`; o copiar do chat usa o CDK e avisa a falha |
| `51d4cad` | tooltip com id do painel único por instância |
| `9e7a738`, `c353522`, `b83c33d` | `app-search-field` (peça nova), usado em 7 telas |
| `a8e0685` | `app-kpi` com forma curta do valor (`compactValue`) no cartão estreito |
| `a00cb34`, `7215c3f` | `app-kpi-grid` (peça nova): colunas equilibradas (`fit` → `rows` → `cols`), última linha sem esticar. Usado no Pré-Trade, no Report Transfer, na Formalização, na Controladoria e na vitrine |
| `7d6ca04`, `971526e`, `0ae4f9e` | D11: `app-switch` no Report Transfer e na Formalização; Exportar da Formalização com `app-split-button` |
| `34bdc63`, `8299d9b` | A15: títulos e descrições padronizados |
| `75a05b0`, `2f7a280`, `e6bddbd`, `baa7cfb` | A14: a margem lateral vem do shell, e as páginas e o `page-header` ficam em 100% |
| `7e85e3a`, `2cceb1b` | `app-chart` baixa PNG com as cores do tema; ligado na Performance e no CERC |
| `8db2761` | tabela da Formalização mais estreita: as 11 colunas passam de ~1530 para ~1120 px |
| `3d91ece` | A19: o spec da tabela espera dois quadros e mede só o que a tabela acrescenta. Passou com 5 seeds diferentes |

### Mudanças visíveis para listar na PR

- **Material fora:**
  - sessão expirada: o snackbar embaixo, no centro, vira toast no canto
    inferior direito;
  - o esqueleto das tabelas antigas segue o tema e fica escuro no esquema
    escuro;
  - o fundo da página passa a `--bg` (`#fbfcfd`) e o texto herdado passa
    a `--text`, mais escuro;
  - as fontes Material Icons/Symbols não são mais baixadas.
- **Menu do usuário:**
  - o Sair vai para o menu, junto com a Aparência (Claro / Escuro /
    Sistema);
  - no trilho, o avatar abre o menu;
  - quem usa o sistema no escuro passa a ver o portal escuro.
- **Marcas no claro:** a primária da Dots fica um pouco mais escura, e o
  texto da marca, um pouco mais escuro. Na Cerys, o texto sobre a laranja
  fica escuro e a laranja como texto fica `#b65c00`.
- **No escuro:** logos, robôs do Poli, ícone da OpenAI e o 404 ficam
  legíveis.
- **KPIs:**
  - o simples e o filtrável têm a mesma altura;
  - Pré-Trade em 1440 com a sidebar aberta: 4 colunas → 2×2 (antes cortava
    "Operações em andamento");
  - Report Transfer em ~1280: 3+1 → 2×2, com espaço de 12 → 16 px.
- **Busca:** na Formalização e no Onboarding, o ícone vai para a esquerda
  e ganha o X de limpar. No diálogo de arquivos do Report Transfer, ganha
  o X.
- **Formalização:**
  - a Coobrigação do cadastro vira interruptor;
  - Exportar usa o botão com menu comum;
  - Editar vira ícone de lápis com tooltip;
  - a tabela fica mais estreita, com reticências mais cedo e quebras
    quando falta espaço.
- **Report Transfer:** os liga/desliga dos diálogos viram interruptor.
- **Margem (A14):** no celular, tudo fica a 14 px da borda. No desktop, o
  visual não muda. O CERC fica alinhado ao título.
- **Títulos (A15):** "Acompanhamento de clientes" e "Simular proposta",
  com descrição, e a descrição do detalhe do Onboarding.
- **Gráficos:** ícone de baixar PNG na Performance e no CERC.
- **Copiar:** funciona fora de HTTPS.
- **Textos na cor da marca:** passam ao `--brand-ink`, um pouco mais
  escuro.

### Achados novos (não corrigidos)

- **Tooltip de ação desabilitada:** sempre diz "Botão desabilitado" e nunca
  mostra o motivo, que o fechamento de lote monta. Fica nas tabelas
  antigas (`config-table`) e já vem da master.
- **Menu recolhido:** o login apaga a preferência (`localStorage.clear()`).
- **Ícones com a `--brand-secondary` crua:** ficam abaixo de 3:1 na Dots
  (2,93). São cerca de 25, em `shared/ui`, na sidebar e em telas.
- **Assets sem uso:** `no-data.svg`, `welcome.svg` e `email-sent.png`.
- **`.app-input-icon`** de `_forms.scss`: ficou sem uso.
- **Cache do `color-scheme.js`:** o nginx guarda `.js` por 1 h.

### Validação (16/10)

| Item | 13 final | Base `2dbb699` |
|---|---|---|
| Commits | 53 sobre a base, todos compilam sozinhos (`tsc` com o `node_modules` que ainda tem o Material, porque os primeiros commits migram antes de remover) | — |
| Build | ok | ok |
| Bundle inicial | **493,61 kB** (137,74 kB na rede) | 587,87 kB (156,06 kB) |
| Lint | 20 erros, 163 avisos (as regras novas não acham nada) | 20 / 166 |
| Testes | 1.820, só a falha da base | 1.822, 1 falha |
| Smoke | 19 rotas, em claro (desktop e celular), escuro e Dots, sem erro de página, de console nem rolagem lateral. Sem sessão (login), claro e escuro, também sem erro | — |
| Prints | escuro sem pedaço claro em nenhuma tela; logos das 4 marcas no escuro (sidebar, trilho e menu); KPIs 2×2 no Pré-Trade; busca e filtros da Formalização no celular | — |

**Junção com a 18 e a 20** (worktree descartável, com os scripts de
resolução de `$PRIV/resolucoes/`):
- build ok, com bundle inicial de 497,49 kB;
- lint 20/163;
- 1.823 testes, só a falha da base;
- `npm audit --omit=dev` com 0 falhas.
- O spec de rotas da 18 confirma que toda rota autenticada do épico tem
  `iamGuard`, e que o `/pdd` sem permissão vai para `/unauthorized`.

### Depois da revisão (16/10)

- `4bd8380f`: a margem lateral das páginas passa a 26 px no desktop, sem os
  2,5% extras.
  - Com isso, a tabela inteira da Formalização cabe em 1440 px com a
    sidebar aberta.
  - **O Pietro pode querer voltar atrás:** `git revert 4bd8380f`. Ver
    `decisoes.md`.
  - **Mudança visível para a PR:** no desktop, as páginas ficam um pouco
    mais largas.
- O smoke continua sem erro (Formalização, Pré-Trade, Lotes de Liquidação,
  Report Transfer e CERC).

### Datas e formatadores (16/10)

- **`f903fd9c`** corrige a data `AAAA-MM-DD` que aparecia com um dia a menos
  (A26):
  - o `new Date('2026-10-01')` lê a data como meia-noite em UTC, que no
    Brasil ainda é 30/09;
  - o `parseApiDate` lê a data sem hora como dia do calendário;
  - corrige os formatadores das tabelas antigas e o `formatDateToISO`.
- **`fd987f8c`:** a data de nascimento de Usuários também deixa de voltar
  um dia.
- Os specs falhavam antes da correção, num fuso -03.

**Camada de formatação (D49 a D53, em andamento):**
- um formatador por tipo de dado em `shared/utils/format/`, com um
  catálogo fechado de formatos;
- pipes por tipo;
- lint contra formatação solta;
- página "Formatos" na vitrine;
- migração de todas as telas.

**Catálogo** (o primeiro formato de cada tipo é o padrão):

| Tipo | Formatos |
|---|---|
| Data | `dd/mm/aaaa`, `dd/mm/aaaa HH:mm`, `dd/mm/aaaa HH:mm:ss`, `HH:mm`, `HH:mm:ss`, `mmm/aaaa`, `dd/mmm` |
| Período | `dd/mm/aaaa a dd/mm/aaaa` |
| Tempo relativo | `relativo`: "há 5 min", "há 2 h", "ontem às 14:30" e, depois, `dd/mm/aaaa HH:mm` |
| Dinheiro | `R$ 0,00`, `R$ 0`, `compacto` |
| Número | `0`, `0,00`, `compacto` |
| Percentual | `0%`, `0,0%`, `0,00%` |
| Documento | `completo`, `mascarado` |
| Telefone | `completo` |
| CEP | `completo` |
| Sim/Não | `Sim/Não` |
| Tamanho de arquivo | `automático` |
| Duração | `curta`, `relógio` |

