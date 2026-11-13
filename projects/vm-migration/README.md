Status: rascunho
Data: 04/11/2026
Tags: operações, EC2, transição

# Migração das telas de operações

> Nome provisório. A pasta usa o slug em inglês da regra do repositório
> (`vm-migration`); o nome definitivo é a D1 de [decisions.md](decisions.md).

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

Uma tarefa por arquivo em `tasks/`; esta tabela é o índice. As tarefas 02 a 12, do envio de
relatórios, ficam no épico "Migração VM" do Jira.

| # | Tarefa | Status |
|---|---|---|
| 01 | [Inventário da EC2 de automações](tasks/01-ec2-inventory.md) | a começar (05/11) |
| 02 | [Envio de relatórios pela tela Envio de Relatórios](tasks/02-report-sending-plan.md) | planejada (13/11) |
| 03 | [Especificação do catálogo de consultas](tasks/03-query-catalog-spec.md) | a começar |
| 04 | [Rotas de consulta no platform-cessao](tasks/04-cessao-report-queries.md) | a começar |
| 05 | [Posição de ativos no data-lake-api](tasks/05-lake-stock-position.md) | a começar |
| 06 | [Shared: conexão de API e catálogo](tasks/06-shared-api-connection.md) | a começar |
| 07 | [Shared: Origem com consulta e Gerar Arquivo](tasks/07-shared-query-source-and-file.md) | a começar |
| 08 | [Shared: conexão de e-mail e envio](tasks/08-shared-email-destination.md) | a começar |
| 09 | [Shared: calendário, agenda e aviso de falha](tasks/09-shared-calendar-schedule-alerts.md) | a começar |
| 10 | [BFF da tela Envio de Relatórios](tasks/10-bff-report-sending.md) | a começar |
| 11 | [Front da tela Envio de Relatórios](tasks/11-front-report-sending.md) | a começar |
| 12 | [Migração em ondas e desligamento dos scripts](tasks/12-report-migration-waves.md) | a começar |

<!-- ws:items -->
<!-- /ws:items -->

## Situação

04/11/2026: projeto criado com o contexto da saída do Rafael. Em 05/11 começa o inventário da
máquina, base para quebrar o trabalho em tarefas.
