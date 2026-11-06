Status: a fazer
Data: 06/11/2026
Tags: tracker, skills, cards

# 04 — Gerenciador de cards genérico

## Contexto

Pedido do usuário em 06/11/2026, durante a sincronização do board
(`docs/specs/2026-11-05-board-sync-design.md`): a config diz qual ferramenta de cards está em uso,
e cada ferramenta é um adaptador com as próprias dependências e scripts; as skills (`daily`,
`card`) são só a interface.

## Desenho combinado (a detalhar numa spec própria)

- `[tracker] kind = "jira"` e a configuração do adaptador em `[tracker.<kind>]`.
- Contrato de todo adaptador: listar as minhas tarefas no formato neutro (`ws.taskmodel.Task`);
  aplicar os rascunhos neutros (criar, editar, mover, comentar, lançar horas); mapear os status da
  ferramenta para os canônicos.
- As skills só chamam `ws task` e `ws card`; nada nelas sabe qual ferramenta está por trás.

## A fazer antes de implementar

- Spec e plano próprios, depois que a sincronização do board estiver na `main`.
- Decidir se adaptadores de fora (outra linguagem, outras dependências) entram por um contrato de
  linha de comando em JSON, como a prova `command` do board.

## Pronto quando

- Trocar `kind` no config muda a ferramenta sem mexer nas skills.
