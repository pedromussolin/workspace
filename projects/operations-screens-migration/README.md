Status: rascunho
Data: 04/11/2026
Tags: operações, EC2, transição

# Migração das telas de operações

> Nome provisório. A pasta usa o slug em inglês da regra do repositório
> (`operations-screens-migration`); o nome definitivo é a D1 de [decisions.md](decisions.md).

## Visão geral

O Rafael Frankl está saindo da empresa. Numa máquina EC2 (servidor virtual da AWS) dedicada a
ele, a "EC2 de automações", ele construiu telas, rotinas e outras ferramentas que o time de
operações usa no dia a dia. Essas frentes passam para o Pietro Nett, possivelmente com apoio de
outros devs.

- **Problema:** o que roda nessa máquina não está nos repositórios da empresa e só o Rafael
  conhece. Sem ele, quebra sem dono e sem ninguém que saiba consertar.
- **Objetivo:** mapear o que existe, decidir o destino de cada item e levá-lo para um lugar
  mantido pelo time, sem interromper a operação.
- **Fora deste projeto:** a liquidação do Mercato Libero, que roda na mesma máquina mas vai para
  a Artemis V2 (`projects/artemis-v2/tasks/13-mercato-libero-settlement.md`).
- **Fase atual:** só a estrutura. A implementação ainda não está definida.

## Tarefas

Uma tarefa por arquivo em `tasks/`; esta tabela é o índice.

| # | Tarefa | Status |
|---|---|---|
| 01 | [Inventário da EC2 de automações](tasks/01-ec2-inventory.md) | a começar (05/11) |

## Situação

04/11/2026: projeto criado com o contexto da saída do Rafael. Em 05/11 começa o inventário da
máquina, base para quebrar o trabalho em tarefas.
