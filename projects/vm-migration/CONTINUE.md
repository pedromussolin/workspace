Status: rascunho
Data: 04/11/2026
Tags:

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

### 25/11/2026

Tela Automações implementada nos quatro repositórios, em branches locais por card (commit local
autorizado; sem push, sem upstream). Regra de branch: card independente sai da master atualizada,
dependente herda da branch de que depende. Detalhes, commits e pendências no handoff local
`~/.local/share/workspace/projects/vm-migration/handoff-2026-11-25.md` e no contrato
`~/.local/share/workspace/projects/vm-migration/automations-contract.md`.

- shared: TS-5710 → 5711 → 5709 → {5713 → 5716; 5707 → 5708}; TS-5715 da master.
- data-lake-api: TS-5709 (rota de dias úteis sobre a tabela de calendário do lake).
- BFF: TS-5718. Front: TS-5721 → {5720, 5719}.
- Decisões até a T54 (escolhas da implementação aceitas). GMUD atualizada; o deploy de 25/11 não
  cabe: faltam as rotas de consulta do platform-cessao e do data-lake-api e a D5.
- Pedido em aberto, não executado: mover para "Em homologação" os cards implementados que estão
  com o Heitor na sprint atual, pelo `/card`.

### 04/11/2026

Projeto criado com o contexto: o Rafael Frankl sai da empresa e as telas, rotinas e ferramentas
que ele fez para o time de operações na EC2 de automações passam para o Pietro Nett. A liquidação
do Mercato Libero, na mesma máquina, foi para a Artemis V2 (tarefa 13 de lá), só do sistema em
diante; a chegada dos dados (arquivos, transformação, carga) o Pietro decide com o time, ainda sem
projeto. Nada mapeado ainda; implementação fora de escopo por enquanto.

## Branches e worktrees

Locais, sem upstream (25/11): no apl-shared-service, `feature/TS-5710-motor-automacoes`,
`-5711-blocos-de-dados`, `-5709-calendario-dias-uteis`, `-5713-gatilho-dias-uteis`,
`-5716-disparar-email`, `-5707-consultar-api`, `-5708-catalogo-de-consultas`,
`-5715-email-unico-com-anexos`; no data-lake-api, `feature/TS-5709-calendario-dias-uteis`; no BFF,
`feature/TS-5718-automacoes`; no front, `feature/TS-5721-tela-automacoes`,
`-5720-paineis-dados-automacoes`, `-5719-conexoes-automacoes`.

## Próximo passo

1. **25/11:** mover no Jira os cards implementados da sprint atual para "Em homologação" (`/card`).
2. Push e PRs na ordem dos conflitos; revisão; ensaio da migration no sandbox.
3. Rotas de consulta: catálogo (TS-5726), platform-cessao (TS-5729, 5730, 5731) e data-lake-api
   (TS-5742, 5743, 5732), depois da D5; decidir se a posição de ativos ganha o namespace
   `/reports/queries` ou amplia a rota existente.
4. Atualizar no Jira as descrições antigas (TS-5707, 5710, 5714–5716, 5719–5721) e a da TS-5709.

### Histórico

1. **05/11:** começar a tarefa 01 (inventário da EC2), primeiro a data de saída do Rafael e a
   sessão de passagem com ele. O inventário serve também à tarefa 13 da Artemis V2.
2. Com o inventário, quebrar o trabalho em tarefas (`tasks/NN-*.md`) e fechar D1 e D2.
