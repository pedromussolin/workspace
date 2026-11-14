+++
card = "TS-5366"
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
# 09 — Controladoria e Consolidação de Caixa

- **TS:** TS-5366 · **Branch:** `refact/TS-5366-controladoria-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** em andamento (15/10, 3ª leva)
- **Depende de:** 04
- **Passos e critério de pronto:** [area-playbook.md](area-playbook.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/cerc-reconciliation` | `pages/controllership/cerc-reconciliation/` |
| `/pdd` | `pages/controllership/pdd/` |
| `/portfolio-performance` | `pages/controllership/portfolio-performance/` |
| `/cash-consolidation` | `pages/management/cash-consolidation/` |
| `/cash-consolidation/:fundName/analytic` | `pages/management/cash-consolidation/analytic/` |

## O que vai para `features/`

- `features/controllership/`: as três telas, com `services/controllership/*`
  e `interfaces/controllership/*` (incluindo os `*.mock.ts`, ver abaixo).
- `features/cash-consolidation/`: as duas telas, com
  `services/management/cash-consolidation.service.ts` e a interface.

Inventário (`d0bc3de`): 31 arquivos, 7.812 linhas, 291 cores fixas, 6
`::ng-deep`, 2 specs. Material: icon, snack-bar, menu, tooltip, table,
spinner, paginator, dialog e button.

## Fluxos críticos

- Gráficos do CERC (barras agrupadas por data) e da Performance (barras e
  linhas com dois eixos): saem do ApexCharts e viram componentes próprios em
  `shared/ui/charts`, em SVG, com cores dos tokens e redimensionamento pelo
  contêiner (D10, confirmada em 15/10). Com as duas telas migradas, saem o
  `apexcharts.min.js` do `angular.json` e a diretiva `apx-chart-resize` (A7).
  Os pacotes saem na 13.
- Alternância de visualização: dashboard, tabela e pendências; gráfico e
  tabela.
- Exportações e filtros por fundo e produto.

## Pontos de atenção

- `cerc-reconciliation.mock.ts` e `stock.mock.ts`: confirmar se ainda são
  usados. Se só servem a teste, vão para junto do spec.

## O que foi feito (15/10/2026)

Branch `refact/TS-5366-controladoria-nova-arquitetura`, criada da 04 com as
três correções de 15/10. São 34 commits.

| Commits | O quê |
|---|---|
| `e59f542`, `4e399a4` | specs do CERC e da Performance que falhavam na base voltam a passar, antes da refatoração; o limite do eixo sem dados fica como antes |
| `9b6b799`, `ad0bccf` | move as três telas para `features/controllership/` e o caixa para `features/cash-consolidation/` (+ `data-access/`), com rotas `loadChildren`. URLs e guards iguais; o `/pdd` continua sem `iamGuard` (A10) |
| `60418cc` … `3d6f73f` | cópias (cherry-pick) da 05, com conteúdo idêntico: select com limpar, multiselect com busca, pílula/KPI/estado vazio e valor vazio |
| `80be663`, `6a8146d`, `4891677`, `944443f`, `9a316bd` | `app-chart` em `shared/ui/charts` (D10): barras e linhas em SVG, dois eixos, legenda clicável, tooltip escuro (também por teclado e toque), redimensiona com o contêiner, tabela para leitor de tela, movimento reduzido; esqueleto de carregando; cor por barra; rótulos do eixo X em passo regular |
| `5851b1b` | `app-ratio-donut` (rosca de proporção) e `app-meter` (barra de participação) em `shared/ui/charts` |
| `5fb2767` | tabela comum ganha rodapé (`appFooterCell`) e cabeçalho que agrupa colunas (`appHeaderGroup`) |
| `de2c7f5`, `c355bb5`, `4a77b75` | peças novas em `shared/ui`: aviso em faixa (`app-notice`), botão com menu (`app-split-button`) e cartão com título (`app-card`) |
| `c8f1be7`, `0d7f00d` | Performance com o gráfico próprio, signals e regras puras; a troca Gráfico/Tabela vai para a linha de filtros |
| `74db497`, `3bc4dda` | CERC sem Material e com o gráfico próprio; o `apexcharts.min.js` sai dos `scripts` do `angular.json` e a diretiva `apx-chart-resize` é apagada (A7). Os pacotes saem na 13 |
| `8c3e637`, `7518709`, `06295ce` | Consolidado de Caixa e Analítico sem Material, com regras puras; `fix`: as duas telas consultavam o dia seguinte depois das 21h (usavam o dia UTC) |
| `15a372d` | PDD: a tela de 1.535 linhas vira página mais quatro abas, com os gráficos à mão trocados pelo `app-chart` e pelas peças novas |
| `5ecf40d` … `a53099f` | revisão: KPIs cabem no cartão e no celular; composição do PDD mostra VP e PDD sem rolar; tabela do CERC cabe em 1440 px; acentos do PDD; largura da provisão consolidada; spec da tabela do caixa; no celular, o gráfico não alarga mais a página (a tabela oculta para leitor de tela crescia com o conteúdo) e os títulos dos eixos empilham quando não cabem |

**Mudanças visíveis para listar na PR:**
- **Todas as telas:** toast no lugar do snackbar; estado vazio comum no lugar
  das imagens; spinner e skeletons próprios.
- **Gráficos:**
  - cores pelos tokens: Performance (Aquisição `--chart-1`, Liquidação
    `--chart-2`, VP `--success`, PDD `--danger`), CERC (Cessões `--chart-1`,
    Registrado `--chart-4`) e PDD (VP `--success`, vencido
    `--warning-strong`, PDD `--danger`);
  - o eixo X deixou de ser de tempo proporcional e virou categorias com o
    mesmo espaço, sem repetir o rótulo do mês;
  - linhas suaves; o VP ganha área em degradê; legenda clicável;
  - a barra de ferramentas do ApexCharts na Performance (zoom e baixar a
    imagem) sai.
- **KPIs (CERC e PDD):**
  - KPI comum com ícone; em 1440 px ficam em 2×2, com o valor inteiro (4
    colunas só a partir de ~1580 px de contêiner);
  - no celular, valores em reais na forma curta ("R$ 19,16 mi"), com o
    valor completo no tooltip;
  - negativo com o sinal colado ("−R$ 356.219,00");
  - CERC: o "% Registrado" deixa de ser uma pílula grande; o GAP positivo
    fica em tom de perigo;
  - PDD: seguindo a decisão do KPI simples, saem o detalhe e a variação
    contra o período anterior; a faixa, o nº de contratos e o % do VP vão
    para o rótulo.
- **Performance:** select, calendário e atalhos comuns; a troca de visão só
  com ícones, embaixo à direita, virou "Gráfico/Tabela" na linha de filtros.
- **CERC:**
  - a faixa amarela virou o aviso comum; dropdown, tabela e paginador
    comuns; status em pílula com ícone; botões com carregando no lugar da
    ampulheta;
  - na tabela, as colunas "(R$)" mostram só o número (o cabeçalho diz a
    moeda) e os cabeçalhos quebram em duas linhas, para caber em 1440 px.
- **Consolidado de Caixa:**
  - Atualizar e Exportar vão para o cabeçalho; Exportar vira botão com
    menu (Excel no clique; Excel/CSV no menu), com carregando e aviso de
    erro (antes só ia para o console);
  - o filtro de fundos ganha busca; o "?" vira ícone com tooltip; o
    cabeçalho "Fundo" aparece;
  - "NaN", "NaN%" e o "-" do total viram "—".
- **Analítico:** cabeçalho comum com trilha e voltar; seções em accordion
  ("1. Título" no lugar do selo); "-" vira "—".
- **PDD:**
  - o seletor de fundo saiu do título e virou o campo "Fundo" nos filtros;
  - as abas viraram o controle segmentado com ícones;
  - textos com acento ("Visão Geral", "Histórico", "Mov. Estoque",
    "Análise de migração", "Data de referência", "Provisão consolidada",
    "Ticket médio" etc.); ids e valores enviados ao BFF não mudaram;
  - "Composição da carteira": colunas Fundo, VP, PDD e Adm, e o card desce
    para largura total abaixo de 1200 px de contêiner;
  - waterfall sem os rótulos "Sem dado" e sem legenda; "Evolução mensal"
    sem dados mostra o estado vazio com os meses do recorte;
  - rating: a pílula com degradê cônico virou a rosca comum, as barras de
    participação viraram o `app-meter`, e as cores das faixas vêm dos
    tokens, do verde ao vermelho; a linha do fundo escolhido na
    composição fica em negrito.
- **Código morto removido no PDD:** os "insights" calculados (template
  comentado), o menu "Monitoramento" (item comentado) e o
  `pdd.spec.page.ts`, todo comentado.

**Mocks:** `cerc-reconciliation.mock.ts` e `stock.mock.ts` ficam no
`data-access`. O do CERC é usado em produção pelas pendências
(`useMockPending = true`, aba ainda desligada); o do PDD fica atrás de
flags de dev local. Tirar mudaria o comportamento.

**Para decidir:**
- a barra de ferramentas do ApexCharts (zoom e baixar imagem) saiu da
  Performance. Se fizer falta, o "baixar imagem" pode entrar no `app-chart`;
- a `kpi-grid` (grade de KPIs por contêiner) ficou em
  `features/controllership/shared/`. É candidata a subir para `shared/ui`
  na passada de consistência, junto com as grades de KPI das outras áreas;
- a Formalização (08) tem um Exportar com menu feito na tela; agora existe
  o `app-split-button`.

Na montagem da branch, o commit de teste do limite do eixo (`4e399a4`) foi
separado: no histórico do agente ele levava junto a remoção dos arquivos
antigos do gráfico e dos skeletons do CERC, o que deixava aquele commit sem
compilar. A remoção foi para o commit do CERC (`74db497`). O resultado
final é idêntico, arquivo por arquivo.

**Validação** (base: a 04 com as três correções, 678 testes com 77 falhando e lint 59/281):

| Item | 09 |
|---|---|
| Build | ok. Bundle inicial de 1,20 MB para 622 kB (295 → 164 kB na rede), sem o ApexCharts |
| Lint | 51 erros / 272 avisos |
| Testes | 830, com 75 falhando, nenhuma falha nova. As 2 falhas da base da área foram corrigidas |
| Commits | todos compilam sozinhos (`tsc` de app e specs em cada um) |
| Smoke | com dados fictícios (`attachments/smoke-data/controllership.json`): as cinco telas e as abas do PDD e do CERC, em claro, escuro, Dots e celular, sem erro de página, de console nem rolagem lateral |
| Merge | entra sem conflito com todas as outras áreas |

Não deu para exercitar com o BFF real: exportação do caixa (Excel/CSV),
conciliação do CERC e a aba de pendências (desligada). Ficam cobertos por
specs e precisam ser conferidos na sandbox.
