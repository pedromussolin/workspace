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
- **Alinhamento das colunas, em todas as tabelas:** texto, nomes e datas à esquerda; valores,
  quantidades e percentuais à direita; status e etapa no centro; ações à direita, com a ação
  mais comum por último. O `align` padrão do `appColumn` passa a ser `start`.
- **Paginador:** fica como está (a caixa de tamanho só aparece onde a tela oferece mais de um).
- **Seletor de visão:** dentro do cartão de filtros, com o rótulo "Visualização".
- **Tabela dentro da linha que abre:** até 5 linhas por página por padrão
  (`NESTED_TABLE_PAGE_SIZE`); a tela pode mudar.
- **Ações da página:** na linha do título, à direita; a trilha fica sozinha no topo.
- **Abrir accordion ou linha:** se o conteúdo aberto não cabe na área visível, rola até o começo
  dele; se cabe, nada se mexe.

| # | Tela ou peça | O que muda | Onde | Situação |
|---|---|---|---|---|
| R1 | Pré-Trade, lista | A 1440 px, Status e Ações ficam fora da tela (A34): nomes longos em uma linha, com reticências e dica | `features/pre-trade` | em correção |
| R2 | Tabela comum | Erro "ResizeObserver loop" (A32): a largura passa a ser gravada no quadro seguinte | `shared/ui/table` | em correção |
| R3 | Sidebar e áreas que rolam | Barra do Windows, com setas: `scrollbar-width` desligava o estilo do portal. Mixin `ui.scrollbar-discreet` (fina, sem trilha) na sidebar, no segmentado, na lista da docs da API e na tabela | `styles/_mixins.scss`, `.ai` | feito (tabela: em correção) |
| R4 | Formalização e Pré-Trade | Margem branca de 16 px em volta da tabela: `.card` global antigo com `padding: 1rem`, somado ao recuo de dentro. Regra removida | `src/styles.scss` | feito |
| R5 | Lotes de Liquidação | Segmentado sem rótulo ao lado dos filtros: ganha "Visualização" | `features/liquidation-batches` | feito |
| R6 | Lotes de Liquidação | Tabela diferente da Formalização: ainda era o `config-table` legado. Migra para `app-table` (Fechamento e Conciliação), ações à direita, linha aberta pela chave do lote | `features/liquidation-batches` | feito |
| R7 | Segmentado | Esticado num campo, as opções ficavam do tamanho do texto e sobrava espaço: agora dividem a largura igualmente | `shared/ui/toggle-group` | feito |
| R8 | Desempenho da Carteira | Filtros sem o cartão branco | `features/controllership/portfolio-performance` | feito |
| R9 | PDD | Abas fora do cartão de filtros: viram o campo "Visualização" dentro dele | `features/controllership/pdd` | feito |
| R10 | Tabela comum | Primeira e última coluna a 10 px da borda, e o título do cartão a 20 px: recuo `--app-table-edge` | `shared/ui/table` | em correção |
| R11 | Todas as tabelas | Alinhamento por tipo de dado (ver decisões); no Pré-Trade, ações à direita com o "ver" por último. Fluxos, Conexões e Unidades: "Excluir" ficou colado em "Editar" (a revisar) | `shared/ui/table`, telas | telas feitas; Pré-Trade e padrão em correção |
| R12 | Lotes de Cessão | Filtros e tabela sem cartão, filtros sem ocupar a largura, `config-table` legado. Feito: cartões, filtros na largura toda, "Limpar filtros", `app-table` (lotes e contratos da linha aberta, com 5 por página). Status segue em texto: o BFF manda o estado livre, sem conjunto fechado | `features/assignment-batches` | feito |
| R13 | Tabelas dentro da linha que abre | Padrão de 5 linhas por página. O exemplo dos Lotes já pedia 5; o BFF falso do portal local ignorava `per_page` (corrigido no `smoke.mjs`). Faltam as que não paginam (grupos, pessoas, execuções) | `shared/utils/local-pagination.ts`, telas | peça comum feita; telas em correção |
| R14 | Seletor de período | "Data inicial – Data final" desalinhado: as duas datas dividem a caixa ao meio, centradas | `shared/ui/date-picker` | feito |
| R15 | Cabeçalho da página | Botões (Exportar, Cadastrar) na linha da trilha, longe do título: vão para a linha do título | `shared/ui/page-header` | feito |
| R16 | Accordion | Conteúdo a 4 px do cabeçalho: passa a 16 px | `shared/ui/accordion` | feito |
| R17 | Accordion e linha que abre | Ao abrir pelo clique, rola até o começo se não couber | `shared/utils/reveal.ts`, accordion, tabela | accordion feito; tabela depois da R1/R2 |
| R18 | Formalização, Onboarding BGT, Caixa | A 1440 px a tabela passa da tela e Ações fica fora de vista (como o R1) | telas | a fazer |
| R19 | Envio de relatórios, detalhe da execução | Pastas coladas, sem separador | `features/report-transfer` | em correção |
| R20 | Tabela comum | Filtro de coluna (botão no cabeçalho e popover) ainda mora no `config-table` e cada tela repete o estilo: levar para `shared/ui/table` | `shared/ui/table` | a decidir |
| R21 | Lotes de Cessão | Status como pílula exige um enum de status no BFF (hoje `estado_atual` livre) | BFF + tela | a decidir |
