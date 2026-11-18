Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Decisões

Uma decisão por linha, com dono e data. Quando uma pendente fechar, ela vai para "Tomadas" com o motivo.

## Pendentes

Em "Quem", quem decide.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|

## Tomadas

Em "Quem", quem decidiu.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| D1 | SLA opcional por etapa do fluxo | usuário | 18/11/2026 | Pedido inicial |
| D2 | SLA conta em horas úteis: seg. a sex., horário comercial, sem os feriados da B3 | usuário | 18/11/2026 | Sem isso, um SLA curto vence no fim de semana |
| D3 | SLA estourado aparece na tela (lista e detalhe), separado do chip de prazo da solicitação, e gera e-mail para quem age na etapa | usuário | 18/11/2026 | Frequência em D14 |
| D4 | Trade antecipado: Operações pode executar na 1ª e na 2ª aprovação | usuário | 18/11/2026 | Quem executa o trade não pode depender da fila de aprovações |
| D5 | As aprovações que faltavam são puladas de vez; a solicitação vai para o Trade, e Operações faz tudo do fluxo normal (editar, anexar, enviar para a Conferência) | usuário | 18/11/2026 | Revisto após a revisão do desenho: "precisa fazer tudo que faria no fluxo normal, mas ignorando as aprovações" |
| D6 | Trade antecipado exige motivo em texto, que vai para o histórico e para o aviso na tela | usuário | 18/11/2026 | Auditoria |
| D7 | As áreas puladas recebem e-mail informativo, no estilo do aviso de aprovação automática | usuário | 18/11/2026 | Ciência das áreas |
| D8 | A tela deixa claro que as aprovações foram puladas (trilha, detalhe e lista) | usuário | 18/11/2026 | Pedido inicial |
| D9 | 2ª aprovação genérica: permissão `portfolio-manager-pre-trade:approve`, exibida como "Gestão (Aprovação trade)", para quem tem a CGA | usuário | 18/11/2026 | Não é só o CEO; o diretor também aprova |
| D10 | O usuário cria a app role nova no Azure e a atribui antes do deploy; a `ceo-pre-trade:approve` sai só depois | usuário | 18/11/2026 | Quem aprova não fica sem role no meio da troca |
| D11 | Exceção à regra de prefixo dos scopes do BFF: `ceo-pre-trade` sai e `portfolio-manager-pre-trade` entra na lista `SCOPES_OUTSIDE_THE_PREFIX_RULE`, sem crescer | usuário | 18/11/2026 | O padrão `{grupo}-pre-trade` da shared não segue o prefixo da página |
| D12 | Fast track fica fora da primeira entrega | usuário | 18/11/2026 | Será implementado no futuro |
| D13 | Horário comercial das horas úteis do SLA: 9h às 18h, America/Sao_Paulo | usuário | 18/11/2026 | Horário de trabalho das áreas |
| D14 | E-mail do SLA estourado sai uma vez só, no momento em que estoura (diferente do aviso de prazo, que é diário) | usuário | 18/11/2026 | O SLA conta em horas; repetir todo dia não ajuda |
| D15 | Trade antecipado no motor: transição com `skips_approvals`, vagas abertas viram `SKIPPED`, evento com as etapas puladas | usuário | 18/11/2026 | Histórico coerente e reaproveitável por outro fluxo |
| D16 | SLA com vencimento gravado na entrada da etapa | usuário | 18/11/2026 | Lista e job em SQL simples; mudar o SLA vale para as próximas entradas |
| D17 | As tarefas do Pré-Trade no TS ficam no épico TS-5046 | usuário | 18/11/2026 | Épico do Pré-Trade |
| D18 | SLA padrão de 3h úteis (180 min) nas etapas 1ª aprovação, 2ª aprovação, Trade, Conferência e Ajustes; Rascunho sem SLA (escolha técnica, ajustável) | usuário | 18/11/2026 | "3 horas uteis de SLA por default, qualquer coisa eu mudo" |
