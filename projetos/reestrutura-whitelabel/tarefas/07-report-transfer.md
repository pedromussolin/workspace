# 07 — Report Transfer

- **TS:** TS-5364 · **Branch:** `refact/TS-5364-report-transfer-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** a iniciar
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
