# 25 — Refinamento visual e de design

- **TS:** TS-5395 · **Branch:** `refact/TS-5395-refinamento-visual` (da `release/20261016` do front)
- **Status:** **rodada 1 em andamento** (16/10): itens R1 a R12 em correção, auditoria em paralelo
- **Depende de:** todas as branches do front (a junção: 13, 17, 18, 19, 20,
  21, 22 e 23, com as áreas dentro da 13)
- **Vai antes da 24:** o deploy leva o refinamento junto.

## Por quê

Pedido do Pietro em 16/10: revisar tudo o que o épico fez em estilo e design
e ajustar, em rodadas. Ele aponta, a tarefa corrige, e ele revisa de novo.

## Base: a release

Decidido em 16/10 (Pietro): juntar tudo numa release, criar o refinamento a
partir dela e subir no ambiente. A release é a da 24 (`release/20261016`),
com todas as branches do front juntas, uma por merge. Por que não branch por
branch:
- o que a pessoa vê só existe junto: a 13 tirou o Material, a 23 pôs as
  ilustrações, e a 19 e a 21 fizeram a tela de acesso;
- as peças comuns (`shared/ui`, tokens) vêm da 03 e da 04, alteradas pela 13;
- corrigir na origem obrigaria a propagar cada ajuste por merge em cadeia.

**Como fica:**
- os commits do refinamento ficam na `refact/TS-5395-refinamento-visual`,
  atômicos, um por peça ou tela;
- cada rodada volta para a release por PR (ou merge), e a release segue
  para a sandbox;
- ajuste que vier da revisão de uma tarefa entra na branch dela, e a release
  faz merge de novo.

## Para começar (outro chat)

- **Worktree:** `~/repos/apl-credit-whitelabel-wt/25`, branch
  `refact/TS-5395-refinamento-visual`, igual à `release/20261016` (`082111a5`),
  com `node_modules` e build prontos.
- **Portal local:** `anexos/scripts/portal-local.sh ~/repos/apl-credit-whitelabel-wt/25`
  (http://localhost:4300), com os dados fictícios de acesso, liquidação e
  Pré-Trade. `BUILD=1` refaz o build depois de cada rodada.
  - Pare o portal antes do `validar-leva.sh`, que usa as mesmas portas.
- **Validação da rodada:** `validar-leva.sh` com
  `BASE=082111a5`, `BASE_FALHAS=$PRIV/base-vazia-falhas.txt`,
  `BASE_LINT=20/163` e os dados `todas-acesso-21.json`. A base passa com
  2.210 testes, audit 0 e smoke ok.

## Como funciona a rodada

1. **Revisão:** o Pietro navega no portal local, com dados fictícios
   (`anexos/scripts/portal-local.sh`, ver o README), e anota o que mudar.
   - Pode ser por tela, por componente ou geral (cor, espaçamento,
     tipografia, densidade).
   - Print com marcação ajuda.
2. **Lista:** cada item entra na tabela abaixo, com tela, o que muda, onde
   (token, componente comum ou tela) e decisão.
3. **Correção:**
   - mudança em token ou componente comum vale para todas as telas e
     entra primeiro;
   - em lote, com agentes, um por grupo de telas.
4. **Validação:** junção completa (`validar-leva.sh` com smoke), prints
   antes e depois nas 4 marcas, claro e escuro e celular.
5. **Volta para o Pietro** com os prints e o portal local já atualizado.

## Regras

- Valem as da `.ai/`, sobretudo:
  - cor só por token, sem cor fixa;
  - contraste AA, conferido pelos specs de contraste;
  - responsivo em 390 px;
  - sem Angular Material;
  - ícones próprios.
- Mudança de padrão muda a `.ai/` no mesmo commit, e a vitrine
  (`/design-system`) mostra o novo.
- Nada de mudar URL, contrato com o BFF ou permissão: aqui é só aparência.

## Itens

Decisões da rodada 1 (16/10, Pietro):
- **Alinhamento das colunas, em todas as tabelas:** por tipo de dado (16/10), **revisto em 19/10**:
  colunas de dados centralizadas; ações à direita, com o excluir isolado na ponta; texto corrido de
  várias linhas à esquerda. O `align` padrão do `appColumn` volta a ser `center`.
- **Paginador:** fica como está (a caixa de tamanho só aparece onde a tela oferece mais de um).
- **Seletor de visão:** dentro do cartão de filtros, com o rótulo "Visualização".
- **Tabela dentro da linha que abre:** até 5 linhas por página por padrão
  (`NESTED_TABLE_PAGE_SIZE`); a tela pode mudar.
- **Ações da página:** na linha do título, à direita; a trilha fica sozinha no topo.
- **Abrir accordion ou linha:** se o conteúdo aberto não cabe na área visível, rola até o começo
  dele; se cabe, nada se mexe.

| # | Tela ou peça | O que muda | Onde | Situação |
|---|---|---|---|---|
| R1 | Pré-Trade, lista | A 1440 px, Status e Ações ficam fora da tela (A34): nomes longos em uma linha, com reticências e dica | `features/pre-trade` | feito |
| R2 | Tabela comum | Erro "ResizeObserver loop" (A32): a largura passa a ser gravada no quadro seguinte | `shared/ui/table` | feito |
| R3 | Sidebar e áreas que rolam | Barra do Windows, com setas: `scrollbar-width` desligava o estilo do portal. Mixin `ui.scrollbar-discreet` (fina, sem trilha) na sidebar, no segmentado, na lista da docs da API e na tabela | `styles/_mixins.scss`, `.ai` | feito |
| R4 | Formalização e Pré-Trade | Margem branca de 16 px em volta da tabela: `.card` global antigo com `padding: 1rem`, somado ao recuo de dentro. Regra removida | `src/styles.scss` | feito |
| R5 | Lotes de Liquidação | Segmentado sem rótulo ao lado dos filtros: ganha "Visualização" | `features/liquidation-batches` | feito |
| R6 | Lotes de Liquidação | Tabela diferente da Formalização: ainda era o `config-table` legado. Migra para `app-table` (Fechamento e Conciliação), ações à direita, linha aberta pela chave do lote | `features/liquidation-batches` | feito |
| R7 | Segmentado | Esticado num campo, as opções ficavam do tamanho do texto e sobrava espaço: agora dividem a largura igualmente | `shared/ui/toggle-group` | feito |
| R8 | Desempenho da Carteira | Filtros sem o cartão branco | `features/controllership/portfolio-performance` | feito |
| R9 | PDD | Abas fora do cartão de filtros: viram o campo "Visualização" dentro dele | `features/controllership/pdd` | feito |
| R10 | Tabela comum | Primeira e última coluna a 10 px da borda, e o título do cartão a 20 px: recuo `--app-table-edge` | `shared/ui/table` | feito |
| R11 | Todas as tabelas | Alinhamento por tipo de dado (ver decisões); no Pré-Trade, ações à direita com o "ver" por último. Fluxos, Conexões e Unidades: "Excluir" ficou colado em "Editar" (a revisar) | `shared/ui/table`, telas | feito |
| R12 | Lotes de Cessão | Filtros e tabela sem cartão, filtros sem ocupar a largura, `config-table` legado. Feito: cartões, filtros na largura toda, "Limpar filtros", `app-table` (lotes e contratos da linha aberta, com 5 por página). Status segue em texto: o BFF manda o estado livre, sem conjunto fechado | `features/assignment-batches` | feito |
| R13 | Tabelas dentro da linha que abre | Padrão de 5 linhas por página. O exemplo dos Lotes já pedia 5; o BFF falso do portal local ignorava `per_page` (corrigido no `smoke.mjs`). Faltam as que não paginam (grupos, pessoas, execuções) | `shared/utils/local-pagination.ts`, telas | feito |
| R14 | Seletor de período | "Data inicial – Data final" desalinhado: as duas datas dividem a caixa ao meio, centradas | `shared/ui/date-picker` | feito |
| R15 | Cabeçalho da página | Botões (Exportar, Cadastrar) na linha da trilha, longe do título: vão para a linha do título | `shared/ui/page-header` | feito |
| R16 | Accordion | Conteúdo a 4 px do cabeçalho: passa a 16 px | `shared/ui/accordion` | feito |
| R17 | Accordion e linha que abre | Ao abrir pelo clique, rola até o começo se não couber | `shared/utils/reveal.ts`, accordion, tabela | feito (tabela confere de novo enquanto o detalhe carrega dados, até 2 s) |
| R18 | Formalização, Onboarding BGT, Caixa | A 1440 px a tabela passa da tela e Ações fica fora de vista (como o R1) | telas | Formalização e Caixa cabem a 1440; Onboarding fica com rolagem (decisão de 19/10) |
| R19 | Envio de relatórios, detalhe da execução | Pastas coladas, sem separador | `features/report-transfer` | feito |
| R20 | Tabela comum | Filtro de coluna (botão no cabeçalho e popover) ainda mora no `config-table` e cada tela repete o estilo: levar para `shared/ui/table` | `shared/ui/table` | a decidir |
| R21 | Lotes de Cessão | Status como pílula exige um enum de status no BFF (hoje `estado_atual` livre) | BFF + tela | a decidir |
| R22 | Accordion | Itens colados: o `:host + :host` do espaço não compila no Angular (vira seletor inválido). O espaço vai para o `app-accordion`; lista numerada ganha o número num quadrado (`marker`), usado no analítico do Consolidado | `shared/ui/accordion`, `features/cash-consolidation` | feito |
| R23 | Docs da API | Layout novo no estilo do exemplo de 16/10: um painel com navegação (combobox da documentação, busca, grupos com método + nome) e conteúdo (barra do endpoint com copiar, parâmetros em tabela, corpo com Exemplo/Esquema/cURL, respostas por status, "Testar chamada"). Só o BFF por enquanto, pronto para outros serviços. Proposta: artifact "Docs da API: proposta" | `features/api-docs` | feito (pacote B; 207 specs) |
| R24 | Onboarding BGT, lista | Filtros com largura fixa e linhas pela metade; atalhos de período menores que os campos (V33) | `features/onboarding-bgt` | feito |
| R25 | Onboarding BGT, monitoramento | Filtros desencontrados (período à esquerda, produto na ponta); sem dados: o BFF falso não tem o monitoramento, e a tela fica carregando para sempre (V40) | `features/onboarding-bgt`, dados fictícios | feito |
| R26 | Ações da linha | Excluir colado em Editar (Fluxos, Conexões, Unidades): a ação destrutiva fica sempre por último, isolada na ponta direita (exceção à "mais usada por último"), em todas as tabelas | telas com excluir, `.ai` | feito (classe app-table__destructive-action; também na vitrine) |
| R27 | Home | Conteúdo no topo, não centrado: a área do shell (`.shell__content`) virou coluna com a altura da tela, e a Home ocupa e se centra nela. Portal local ganhou `ORG` para ver a home de parceiro | `layouts/app-shell`, `features/general/home`, `smoke.mjs` | feito |
| R28 | Indicadores na cor da marca | Com a secundária laranja da Cerys (V24), checkbox, rádio, switch, borda de foco, dia de hoje e área de soltar arquivo ficavam a 2,28:1 (a Dots já ficava a 2,93). Passam a `--brand-icon` (3:1 garantido); nas outras marcas, a cor não muda. Falta o paginador | `shared/ui`, `styles/_mixins.scss`, `.ai` | feito |
| R29 | Marca Dots | `ink` a 4,25 no hover do botão principal e 4,29–4,34 no avatar e no fundo suave forte; logo ainda com margem (~42×14 px; recortado daria ~92×30) | `core/theme/themes.ts`, `assets/dots` | feito (ink da Dots #a24e30; avatar com 22% de tinta, AA nas 4 marcas) |
| R30 | Pré-Trade | Chip "xlsx" do anexo a 4,27 | `features/pre-trade` | feito |
| R31 | Logos e favicons | Padrão: qualquer logo vira SVG sem fundo, recortado e normalizado (caixa de 180×32), com versão escura gerada; símbolo e favicon em SVG com reserva PNG. Script em `.ai/scripts/brand-logo` (Python, vtracer e Pillow) e passo a passo na skill `new-brand`. Aplicado às 4 marcas. Favicon único para todas as marcas (o `.ico` de 32×32 entregue em 19/10); o trilho da sidebar usa o símbolo de cada marca. Recebidos em 19/10: símbolo da Dots (68 px) e logo longa da Cerys (2000 px, fundo preto; o símbolo sai dela). Faltam: logo longa da Dots (chegou toda preta) e, se houver, a da Cerys com fundo transparente ou em SVG | `.ai`, `assets`, `core/theme` | feito (pacote C: 4 marcas em SVG, escuro gerado, favicon único; script e skill na .ai) |
| R32 | Login | "Entrar com Microsoft" segue as diretrizes da Microsoft (claro e escuro, logo oficial) | `features/general/login`, tokens | feito (texto "Entrar com Microsoft" mantido: a frase oficial em PT-BR não foi confirmada) |
| R33 | Accordion | Variação sem moldura para dentro de cartão (detalhes do contrato) | `shared/ui/accordion` | feito (accordion flush nos detalhes do contrato) |
| R34 | Estado vazio | Variação compacta para vazio dentro de cartão (detalhe do usuário e outros) | `shared/ui/empty-state` | feito (vazio compacto no detalhe do usuário, Pré-Trade e controle de acesso) |
| R35 | Tabelas | Colunas de volta ao centro (ações à direita, texto longo à esquerda) e cabeçalhos de uma linha com a mesma altura (o funil de filtro e o botão de ordenar não aumentam a linha) | `shared/ui/table`, telas, `.ai` | feito (colunas no centro; números com `numeric`; cabeçalho de uma linha com 38,8 px em todas as tabelas) |
| R36 | Barra de filtros | Distribuição equilibrada em qualquer zoom: linhas = ceil(n / cabem), colunas = ceil(n / linhas) (5 campos → 3 + 2), cada linha ocupando a largura toda; campo de status com o mesmo tamanho dos outros | `shared/ui/filter-bar` | feito (app-field-grid: 5 → 3 + 2; zoom e larguras conferidos) |
| R37 | Paginador | "Itens por página" abria a lista nativa do navegador: passa a usar o select do portal | `shared/ui/table/paginator` | feito (lista do portal no "Itens por página") |
| R38 | Gráficos | Exportar em PNG (imagem), Excel e JSON (dados brutos), num menu "Exportar"; o .xlsx é gerado sem dependência nova | `shared/ui/charts`, `shared/utils` | feito (pacote G: menu Exportar com PNG, Excel e JSON; .xlsx sem dependência; título e cabeçalho por gráfico) |
| R39 | Formulários | Mesma distribuição equilibrada dos filtros nas seções de formulário (Editar Produto do Orquestrador ficava 6 + 1, com espaço vazio): a regra vira peça comum de grade de campos | `shared/ui`, `features/orchestrator` | feito (pacote I2: diálogos do Pré-Trade, Formalização, Envio, Controle de acesso e Docs da API; Orquestrador e vitrine na barra comum) |
| R40 | Consolidado de Caixa, analítico | A tabela dentro do accordion ficava com margem e faixa cinza solta: `contentFlush` no `app-accordion-item`, tabela de borda a borda | `shared/ui/accordion`, `features/cash-consolidation` | feito |
| R41 | Detalhes do contrato | "Grosseira": topo com os fatos principais, dados gerais em grupos numa grade de rótulo e valor, mesmo estilo nos acordeões; dados fictícios para validar | `features/assignment-batches/contract-details` | feito (pacote H: resumo no topo, grupos em app-detail-list, mesmo estilo nos acordeões; dados fictícios) |
| R42 | Usuários | Rodapé da paginação mais alto e em outro formato: paginador padrão, mesma altura em todas as tabelas | `shared/ui/table`, `features/users` | feito (rodapé de paginação com 52 px no desktop e 88 px no celular em todas as tabelas) |

## Auditoria da rodada 1 (V3 a V41)

345 prints (marca padrão em claro, escuro, 1440 e 390 px; as outras três marcas num recorte),
feitos no build de 16/10, antes das correções. Detalhe, medidas e prints na pasta privada
(`evidencias/25-rodada1/achados.md`). Sem rolagem lateral, sem cor fixa e sem erro de
ResizeObserver nos prints.

**Já cobertos pelos itens R:** V8 (R18), V9 alinhamento (R11; falta `tabular-nums`, ver V9b),
V13 (R7), V28 (R12), V29 (R6), V12 tamanho de página (decidido: fica), parte da V30 (R18).

| # | Onde | O que | Proposta | Grav. | Situação |
|---|---|---|---|---|---|
| V3 | Tokens | Tom sobre tom de sucesso e atenção abaixo de AA no claro (4,17 e 4,08:1), em pílulas, avisos e toasts | `--tonal-fg` de 78% para 70% (4,8 e 4,7:1) | alta | feito |
| V24 | Marca Cerys | Tons de marca saem da secundária, quase preta: botão principal, segmentado ativo e ícones ficam cinza | Tons de marca pelo `accent` laranja que o tema já declara | alta | feito |
| V7 | Campos, checkbox, radio | Contorno de 1,23:1 (claro) e 1,43:1 (escuro); o mínimo para contorno é 3:1 | Token `--control-border` só para controles | média | fica (decisão de 16/10) |
| V4 | Sidebar | Rótulos de seção e e-mail a 4,43:1 (3,99 com hover) | `--text-secondary` | média | feito |
| V5 | Superfície rebaixada ou tingida | Texto apagado a 4,19–4,40:1 (trilha do Pré-Trade, linha aberta em três marcas) | Texto mais escuro nessas superfícies | média | feito |
| V6 | Pílula de status de lote | No escuro, três status abaixo de AA; na Dots, "Concluído" a 3,82:1 | Clarear os status no escuro; "Concluído" sem a cor da marca | média | feito |
| V9b | Tabela comum | Números sem algarismos de largura fixa | `tabular-nums` nas colunas `end` | média | feito |
| V10 | Tabela comum | Altura da linha de 47 a 67 px entre telas | Espaçamento vertical único na célula | média | feito (célula com --space-3; chevron não aumenta a linha) |
| V14 | Segmentado no celular | Com 4 ou 5 opções, rola sem indicação e corta opções (PDD, Envio) | Abaixo de 600 px, grade de 2 colunas ou fade na borda | média | feito (grade de 2 colunas quando não cabe) |
| V15 | KPI | Rótulo cortado sem dica ("Operações em andam…") | Dica no rótulo cortado ou 2 linhas | média | feito (título em até 2 linhas) |
| V16 | Grade de KPIs | Celular: um por linha (até 475 px antes da lista); desktop: 2 ou 4 colunas conforme a tela | Celular em 2 colunas; regra única no desktop | média | feito: celular 2 por linha; desktop com 240 px em toda tela (4 por linha, inclusive a controladoria), forma curta com o valor inteiro no tooltip (decisão de 19/10) |
| V17 | Select | Valor cortado sem dica; lista aberta estreita corta opções | Dica no valor; lista com largura mínima maior | média | feito |
| V18 | Campo de data | Placeholder e período cortados em campo estreito | Largura mínima que caiba a data; placeholder "dd/mm/aaaa" | média | feito (largura mínima da data) |
| V19 | "Limpar filtros" | Três tamanhos e ausente em 7 telas | Uma peça só, no fim de toda toolbar | média | feito (pacote D) |
| V20 | Cartão de filtros | Cada tela com a própria classe e recuo (16/16, 16/20, 20/20) | Uma toolbar de filtros comum | média | feito (app-filter-bar) |
| V25 | Logo Cerys | PNG com margem transparente: o desenho fica com ~50×10 px | Logo recortado | média | feito |
| V31 | Usuários | "APPROVED" cru numa pílula neutra; vazio dentro de pílula | Mapa de status em PT-BR; vazio sem pílula | média | feito |
| V11 | Seta de ordenar | Inativa a 2,13:1 | Inativa em `--text-faint` | baixa | feito |
| V21 | Raios | Checkbox 5 px, menu e anexo 12 px, fora da escala | Raios da escala | baixa | feito |
| V22 | Mensagem do campo | Texto longo sem quebra vaza do campo (docs da API) | `overflow-wrap: anywhere` | baixa | feito |
| V23 | Gráfico no celular | Último rótulo do eixo X cortado | Último rótulo alinhado pelo fim | baixa | feito |
| V26 | Logo Dots | Fundo branco opaco vira um retângulo na sidebar clara | PNG transparente | baixa | feito |
| V27 | Login | "Entrar com Microsoft" sólido, fora do tom sobre tom | Tom sobre tom ou registrar a exceção | baixa | feito |
| V30 | Formalização | KPI com percentual ("18 · 37,5%"), fora da regra de KPI simples | Percentual fora do valor | baixa | feito (percentual no caption do KPI: "37,5% do total") |
| V32 | Usuários e Produtos | Busca com 36 px e "Buscar" em tamanhos diferentes | 40 px e md nos dois | baixa | feito |
| V33 | Onboarding BGT | Atalhos de período com 34 px ao lado do campo de 40 | Mesmo tamanho | baixa | feito |
| V34 | Onboarding BGT, Simular, Clientes | Cabeçalho sem trilha | Trilha na rota | baixa | feito |
| V35 | PDD, composição | Nome do fundo cortado e colunas de valor largas | Largura pelo conteúdo | baixa | feito |
| V36 | Detalhes do contrato | Título "- undefined" sem parâmetro; sombra diferente; acordeão em cartão dentro de cartão | Vazio padrão, `--shadow-card`, acordeão sem moldura | baixa | feito |
| V37 | Detalhes do usuário | Cartão repete o título; descrição da lista; vazio próprio | Título com o nome, vazio padrão | baixa | feito |
| V38 | Trilha de etapas do Pré-Trade | Animação de 600 e 2.400 ms | Registrar a exceção (é progresso) | baixa | feito (exceção na .ai) |
| V39 | Poli Chat | Conversa sem estado inicial; vazio em texto solto | Estado inicial e vazio padrão | baixa | feito |
| V40 | Monitoramento BGT | Com dado incompleto, fica carregando para sempre | Estado de erro ou vazio; completar o dado fictício | baixa | feito |
| V41 | Vitrine | Marca "viva" em minúsculo no seletor | Nome com maiúscula | baixa | feito |

## Commits da rodada 1 (plano para revisão)

455 arquivos. Vários arquivos misturam itens (o mesmo `table.component.scss` tem centro, recuo,
densidade, cabeçalho e barra de rolagem), e o `git add -p` interativo não roda aqui. Por isso o
plano agrupa por arquivo, na ordem em que cada commit compila sozinho: peças comuns primeiro, telas
depois, `.ai` no fim. O `validar-leva.sh` confere a compilação de cada commit.

| # | Commit | Arquivos | Itens |
|---|---|---|---|
| 1 | `feat(TS-5395): utilitários de rolagem, paginação local e planilha` | `shared/utils` (reveal, local-pagination, xlsx), `shared/testing` | R13, R17, R38 |
| 2 | `refact(TS-5395): tokens de contraste, código e do botão Microsoft` | `styles/` (tokens, base, mixins, `styles.scss`) | R3, R4, V3–V6, R23, R32 |
| 3 | `feat(TS-5395): marcas em SVG com escuro gerado e favicon único` | `core/theme`, `assets/{default,dots,cerys,vivo,general}`, `src/favicon.ico` | R29, R31, V24–V26, V41 |
| 4 | `refact(TS-5395): shell em coluna, sidebar e cabeçalho da página` | `layouts/`, `shared/ui/page-header` | R3, R15, R27, R28 |
| 5 | `refact(TS-5395): tabela comum no centro, com recuo e mesma altura` | `shared/ui/table`, specs do `config-table` | R2, R10, R11, R17, R26, R35, R37, V9–V11 |
| 6 | `refact(TS-5395): campos, segmentado, KPI e indicadores revistos` | `shared/ui/{toggle-group,select,date-picker,kpi,checkbox,radio,switch,textbox,field,menu}` | R7, R14, R28, V14–V18, V21–V22 |
| 7 | `feat(TS-5395): acordeão, vazio compacto e lista de detalhes` | `shared/ui/{accordion,empty-state,detail-list}` | R16, R17, R22, R33, R34, R40, R41 |
| 8 | `feat(TS-5395): barra de filtros e grade de campos comuns` | `shared/ui/{filter-bar,field-grid}` | R36, R39, V19, V20 |
| 9 | `feat(TS-5395): code-block com abas e gráfico com menu Exportar` | `shared/ui/{code-block,charts}` | R23, R38, V23 |
| 10–24 | `refact(TS-5395): <tela> no padrão do refinamento` | uma por tela: Pré-Trade, Formalização, Lotes de Liquidação, Lotes de Cessão e contrato, Controladoria, Consolidado de Caixa, Envio de Relatórios, Controle de acesso, Onboarding BGT, Usuários, Orquestrador, Docs da API, Poli Chat, Home e login, Simular e Clientes | por tela |
| 25 | `refact(TS-5395): vitrine com as peças e padrões novos` | `features/design-system` | — |
| 26 | `chore(TS-5395): .ai com os padrões da rodada 1 do refinamento` | `.ai/` (regras, contexto, scripts, skills) | — |

Se algum commit não compilar sozinho, ele se junta ao seguinte, e o relatório diz qual.
