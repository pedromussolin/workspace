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
| 01 | [Inventário da EC2 de automações](tasks/01-ec2-inventory.md) | preenchido, destinos à espera da D2 (16/11) |
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
| # | Tarefa | Card | Tipo | Responsável | Status |
|---|---|---|---|---|---|
| 01 | [Inventário da EC2 de automações](tasks/01-ec2-inventory.md) | TS-5706 | Tarefa | dev-a0893bc9a2 | concluída |
| 02 | [Envio de relatórios pela tela Envio de Relatórios](tasks/02-report-sending-plan.md) | TS-5717 | Tarefa | dev-a0893bc9a2 | concluída |
| 03 | [Especificação do catálogo de consultas](tasks/03-query-catalog-spec.md) | TS-5726 | Tarefa | dev-a0893bc9a2 | concluída |
| 10 | [BFF da tela Envio de Relatórios](tasks/10-bff-report-sending.md) | TS-5718 | Nova função | dev-a0893bc9a2 | em validação |
| 13 | [Liquidação do Mercato Libero: absorção pela V2](tasks/13-mercato-libero-settlement.md) | TS-5565 | Tarefa | dev-ae95329f82 | concluída |
| 14 | [Desligar o fechamento de lotes da VM](tasks/14-ts-5738.md) | TS-5738 | Tarefa | dev-ae95329f82 | a fazer |
| 15 | [Desligar o ajuste de produto (PATCH /produto) da VM](tasks/15-ts-5750.md) | TS-5750 | Tarefa | dev-ae95329f82 | a fazer |
| 16 | [Levantar e migrar os alertas do Mercato Libero da VM](tasks/16-ts-5751.md) | TS-5751 | Tarefa | dev-ae95329f82 | a fazer |
| 17 | [Desligar a correção de aptos (reprocessamento) da VM](tasks/17-ts-5752.md) | TS-5752 | Tarefa | dev-ae95329f82 | a fazer |
| 18 | [Desligar a autocorreção do upload da VM](tasks/18-ts-5753.md) | TS-5753 | Tarefa | dev-ae95329f82 | a fazer |
| 19 | [Desligar a baixa de cancelamentos incompletos da VM](tasks/19-ts-5754.md) | TS-5754 | Tarefa | dev-ae95329f82 | a fazer |
| 20 | [Desligar a baixa de parcelas zeradas da VM](tasks/20-ts-5755.md) | TS-5755 | Tarefa | dev-ae95329f82 | a fazer |
| 21 | [Rota de consulta de contratos no platform-cessao](tasks/21-ts-5729-cessao-report-queries.md) | TS-5729 | Nova função | dev-a0893bc9a2 | em andamento |
| 22 | [Rota de consulta de liquidação no platform-cessao](tasks/22-ts-5730-cessao-report-queries.md) | TS-5730 | Nova função | dev-a0893bc9a2 | em andamento |
| 23 | [Validar as rotas do platform-cessao contra o SQL dos scripts](tasks/23-ts-5731-cessao-report-queries.md) | TS-5731 | Tarefa | dev-a0893bc9a2 | a fazer |
| 24 | [Posição de ativos no data-lake-api: lista opcional, VLTS I e prévia SQL](tasks/24-ts-5742-lake-stock-position.md) | TS-5742 | Melhoria | dev-a0893bc9a2 | em andamento |
| 25 | [Posição de ativos e consulta do OCR no data-lake-api: ramos Dayvale e FBRX3](tasks/25-ts-5743-lake-stock-position.md) | TS-5743 | Melhoria | dev-a0893bc9a2 | a fazer |
| 26 | [Validar as rotas do data-lake-api contra o SQL dos scripts](tasks/26-ts-5732-lake-stock-position.md) | TS-5732 | Tarefa | dev-a0893bc9a2 | a fazer |
| 27 | [Shared: conexão do tipo API para os microsserviços, a GalaPay e a CVM](tasks/27-ts-5707-shared-api-connection.md) | TS-5707 | Nova função | dev-a0893bc9a2 | em validação |
| 28 | [Shared: catálogo fixo de consultas e prévias de dados e SQL](tasks/28-ts-5708-shared-api-connection.md) | TS-5708 | Nova função | dev-a0893bc9a2 | em validação |
| 29 | [Calendário de dias úteis: rota no data-lake-api e uso no shared](tasks/29-ts-5709-shared-calendar-schedule-alerts.md) | TS-5709 | Nova função | dev-a0893bc9a2 | em validação |
| 30 | [Shared: Origem com consulta e Gerar Arquivo no motor de fluxos](tasks/30-ts-5710-shared-query-source-and-file.md) | TS-5710 | Nova função | dev-a0893bc9a2 | em validação |
| 31 | [Shared: execução da rota de dados e ajustes de linhas](tasks/31-ts-5711-shared-query-source-and-file.md) | TS-5711 | Nova função | dev-a0893bc9a2 | a fazer |
| 32 | [Shared: regras nomeadas em código no catálogo, também sobre arquivos de entrada](tasks/32-ts-5712-shared-query-source-and-file.md) | TS-5712 | Nova função | dev-a0893bc9a2 | a fazer |
| 33 | [Shared: agenda por dia útil e aviso de falha de execução](tasks/33-ts-5713-shared-calendar-schedule-alerts.md) | TS-5713 | Nova função | dev-a0893bc9a2 | a fazer |
| 34 | [Shared: conexão do tipo E-mail e cadastro de contatos](tasks/34-ts-5714-shared-email-destination.md) | TS-5714 | Nova função | dev-a0893bc9a2 | em andamento |
| 35 | [Shared: resolução de destinatários e envio pelo Graph com anexos](tasks/35-ts-5715-shared-email-destination.md) | TS-5715 | Nova função | dev-a0893bc9a2 | em validação |
| 36 | [Shared: destino e-mail no bloco, item da execução e teste de conexão](tasks/36-ts-5716-shared-email-destination.md) | TS-5716 | Nova função | dev-a0893bc9a2 | a fazer |
| 37 | [Front: conexões API e E-mail e aba Contatos](tasks/37-ts-5719-front-report-sending.md) | TS-5719 | Nova função | dev-a0893bc9a2 | a fazer |
| 38 | [Front: Origem com consulta, filtros e prévias](tasks/38-ts-5720-front-report-sending.md) | TS-5720 | Nova função | dev-a0893bc9a2 | a fazer |
| 39 | [Front: Gerar Arquivo, destino e-mail e agenda por dia útil no editor](tasks/39-ts-5721-front-report-sending.md) | TS-5721 | Nova função | dev-a0893bc9a2 | a fazer |
| 40 | [Cadastrar URLs, tokens e credenciais dos envios no Parameter Store](tasks/40-ts-5722-report-migration-waves.md) | TS-5722 | Tarefa | dev-a0893bc9a2 | em andamento |
| 41 | [Migrar as listas de destinatários dos envios da mv_mail_list para contatos](tasks/41-ts-5723-report-migration-waves.md) | TS-5723 | Tarefa | dev-a0893bc9a2 | em andamento |
| 42 | [Onda 1: migrar e desligar os envios do FIDC Fornecedores e o aviso do Jurídico](tasks/42-ts-5724-report-migration-waves.md) | TS-5724 | Tarefa | dev-a0893bc9a2 | a fazer |
| 43 | [Onda 2: migrar e desligar Relação de baixas (Vektor) e os envios de liquidação do Mercato Pago](tasks/43-ts-5725-report-migration-waves.md) | TS-5725 | Tarefa | dev-a0893bc9a2 | a fazer |
| 44 | [Onda 3: migrar e desligar Estoque (VLTS I), Base de operações e estoque (FBRX3) e report do OCR](tasks/44-ts-5740-report-migration-waves.md) | TS-5740 | Tarefa | dev-a0893bc9a2 | a fazer |
| 45 | [Onda 4: migrar e desligar os envios com regra em código e fontes externas](tasks/45-ts-5741-report-migration-waves.md) | TS-5741 | Tarefa | dev-a0893bc9a2 | a fazer |
| 46 | [Migrar e desligar Valor conciliado e Resultado do processamento (Mercato Pago)](tasks/46-ts-5727-report-migration-waves.md) | TS-5727 | Tarefa | dev-a0893bc9a2 | a fazer |
| 47 | [GMUDs dos deploys da migração de relatórios](tasks/47-ts-5728-report-migration-waves.md) | TS-5728 | Tarefa | dev-a0893bc9a2 | a fazer |
<!-- /ws:items -->

## Situação

04/11/2026: projeto criado com o contexto da saída do Rafael. Em 05/11 começa o inventário da
máquina, base para quebrar o trabalho em tarefas.

16/11/2026: inventário preenchido (tarefa 01). São 153 itens, cada um com destino proposto: 50
já têm cartão, 44 ainda não. Os achados urgentes da passagem são o alarme de falha na caixa
pessoal do Rafael e a rotação das credenciais. Nada fica na EC2 (T19), e os 25 scripts de envio
de relatórios migram nos cards que já existem, sem card novo (T20).

17/11/2026: os envios de e-mail vão para uma tela nova, Automações, montada com blocos e com abas
por natureza (T21). Consultar API e Disparar e-mail viram blocos separados (T22, substitui T12 e
T16), o disparo reaproveita o módulo de e-mail do shared com cópia e anexo (T26), e os fluxos de
e-mail ficam na mesma tabela do Envio de Relatórios (T25). Os blocos de arquivo viram "Buscar
arquivos" e "Gravar arquivos" (T27), e os destinatários, inclusive clientes, ficam no Entra ID
(T28). Em aberto: nome da tabela (D10) e como o cliente entra no Entra ID (D11).
