# Reestrutura Whitelabel — workspace

Planejamento e acompanhamento do épico que reestrutura o front do portal
(apl-credit-whitelabel). O épico cobre:
- temas de marca em todas as páginas;
- dark mode;
- componentes próprios no lugar do Angular Material;
- a arquitetura `core/shared/layouts/features`.

Aqui ficam as tarefas, as decisões, o design system, as evidências e os
protótipos próprios. O código vive no repositório da empresa, não aqui.

As regras comuns (sigilo, mascaramento, commits, idioma e sincronização) estão no `CLAUDE.md`
da raiz do repositório, `~/repos/workspace/CLAUDE.md`. Aqui ficam só as regras específicas deste
projeto.

## Análogos e placeholders deste projeto

- Os nomes reais viram análogos: "Poliedro" para a empresa e as marcas "Dots", "Cerys" e "Viva".
  Vale também em nomes de arquivo, chaves de tema e caminhos citados.
- Endereços internos viram `<url-da-sandbox>`, "host da sandbox" etc.
- Protótipos próprios em `anexos/` (prévia, ícones, scripts) são permitidos. Os dados de cliente
  da prévia são fictícios.

## Valores reais fora do repo

Alguns valores ficam no arquivo local
`~/.config/workspace/private/reestrutura-whitelabel.md`, fora do controle de versão:
- a URL da sandbox;
- a tabela de nomes reais × análogos;
- onde estão os logs brutos.

Leia esse arquivo quando um documento daqui usar um nome análogo ou um
marcador como `<url-da-sandbox>`. Valor sensível novo vai para lá, e aqui
entra só a referência genérica. Fora deste repo (conversa, repos da
empresa), use os nomes reais.

## Como manter

- **Status:**
  - O README tem a tabela de tarefas e a "Situação" (o que está pronto e o
    que falta).
  - Cada tarefa tem "Status" no topo e "O que foi feito" quando sai do
    papel.
- **Decisões:** decisão tomada vai para `decisoes.md`, com data, quem
  decidiu e o motivo.
- **Validação:** o passo a passo e os números de base ficam em
  `tarefas/roteiro-de-area.md`.

As regras de git dos repos da empresa (branch e commit com `TS-…`, sem push
pelo Claude) estão no `~/repos/CLAUDE.md` e não valem para este repo.
