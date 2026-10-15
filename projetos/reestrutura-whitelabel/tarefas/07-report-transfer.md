# 07 — Report Transfer

- **TS:** TS-5364 · **Branch:** `refact/TS-5364-report-transfer-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** publicada (15/10), sem merge em ambiente
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/report-transfer` | `pages/operations/report-transfer/` (abas de fluxos, agendamentos, conexões e execuções; diálogos de conexão e de editor de fluxo) |

## O que vai para `features/report-transfer/`

- Tela, `components/`, `dialogs/`, `report-transfer.blocks.ts`,
  `report-transfer.format.ts`.
- `services/operations/report-transfer/*` → `data-access/`.
- `interfaces/operations/report-transfer/*` → `data-access/`.

Inventário (`d0bc3de`): 42 arquivos, 9.939 linhas, **442 cores fixas**, 6
`::ng-deep`, 10 specs. Material: icon (12), dialog (7), tooltip (4), table e
snack-bar. Tem um dropdown próprio (`components/dropdown`) que pode virar o
`app-select` da 03.

## Fluxos críticos

- Fluxos: criar e editar no editor de blocos, ligar e desligar grupos e
  agendamentos.
- Conexões: testar conexão, variáveis presentes e ausentes.
- Execuções: lista paginada de arquivos por execução, rotas e totais.
- Permissões por escopo (`REPORT_TRANSFER_SCOPE`) com as ações `read`,
  `update` e `reprocess`.

## Pontos de atenção

- `toneColors` passa cores em hex direto no template (`[config]="{ color: ... }"`).
  Ele vira token ou variante do componente.
- A tela acabou de mudar (TS-5229, merge em 09/10). Começar da master
  atualizada.

## O que foi feito (15/10/2026)

Branch `refact/TS-5364-report-transfer-nova-arquitetura`, criada da 04 com as
três correções de 15/10. São 14 commits.

| Commit | O quê |
|---|---|
| `1c8f9ad`, `fea4388` | move para `features/report-transfer` (+ `data-access/`) e rota com `loadChildren`, mesma URL |
| `30f9432`, `85c19c8`, `bb82350`, `7edf040` | cópias (cherry-pick) da 05 e da 06: `dataSource` sem tipo do Material, select com limpar, multiselect com busca, pílula/indicador/estado vazio. O conteúdo é idêntico, então o merge não conflita |
| `7a6bb40` | combobox comum ganha a opção "Adicionar …" (`creatable`) |
| `5bb013c` | store, ações e regras da tela; diálogos e abas sobre `shared/ui`. Junta três commits do agente que não compilavam sozinhos |
| `32c154d`, `577cfb9` | specs de comportamento da tela, do store, das regras, dos componentes, das abas e dos diálogos |
| `3ebebfd` | parcial de estilo do detalhe e apoio de teste fora do build |
| `31851b5` | layout responsivo e remoção de código sem uso |
| `6a7ffb4` | sem nenhuma permissão, a barra de abas vazia não aparece (antes sobrava um traço) |
| `72af1d0` | spec da tabela de agendamentos |

**Mudanças visíveis para listar na PR:**
- **Cabeçalho:**
  - o cabeçalho do painel ("Envio de relatórios / Configure…") saiu;
  - "Atualizar" e a ação principal ("Novo agendamento", "Novo fluxo" ou
    "Nova conexão") foram para o cabeçalho da página, à direita, com o botão
    tonal.
- **Resumo:** os cards viraram o KPI comum, com "Clique para filtrar a lista"
  e "Filtrando a lista abaixo". Clicar de novo no card ativo tira o filtro;
  isso é novo.
- **Abas:** viraram o controle segmentado, com ícone e texto. No celular, as
  abas rolam na horizontal.
- **Filtros:**
  - usam o select, o multiselect e o calendário de intervalo comuns, e cada
    select tem o "Todos" para limpar;
  - o filtro de status mostra o resumo do multiselect no lugar de "Sucesso
    (+1)".
- **Visão por parceiro:** a troca de visão virou "Lista / Por parceiro". A
  visão por parceiro e o "Erro completo" usam o accordion.
- **Editor de fluxo:**
  - parceiro e produto usam o combobox com "Adicionar …";
  - conexões que não servem de origem ou destino aparecem desabilitadas,
    com "(só destino)" ou "(só origem)".
- **Diálogos:**
  - usam o diálogo comum, com cabeçalho e rodapé fixos;
  - os interruptores "Ativo/Ativa" viraram caixas de marcar (ver D10);
  - Origem e Destino são caixas de marcar;
  - a paginação dos arquivos é o paginador comum.
- **Pílulas:** status e situação são pílulas tonais. "Em andamento" tem um
  ícone que gira, parado com movimento reduzido.
- **Tabelas:** as ações da linha são botões de ícone tonais, com tooltip. O
  texto que não cabe termina em reticências e mostra o resto no tooltip.

Mantido como era: no primeiro ciclo da atualização ao vivo, o timer é
armado antes das cargas iniciais voltarem.

Não deu para exercitar com dados: criar e editar fluxo de ponta a ponta,
testar conexão com variáveis reais e reprocessar. Esses fluxos estão
cobertos por specs e precisam ser conferidos na sandbox.

**Validação** (base: a 04 com as três correções, 678 testes com 77 falhando e lint 59/281):

| Item | 07 |
|---|---|
| Build | ok |
| Lint | 59 erros / 270 avisos |
| Testes | 799, com 77 falhando, nenhuma falha nova. Specs da área: 171/171 |
| Smoke (mock) | rotas principais no desktop e no celular, sem erro de página |
