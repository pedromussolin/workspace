Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# pre-trade

## Visão geral

Evolução do fluxo do Pré-Trade (tela `features/pre-trade` do portal, motor de workflows do
`apl-shared-service`). A primeira entrega são três mudanças:

1. **SLA por etapa, opcional.** SLA é o tempo máximo combinado para uma etapa ser concluída. Cada
   etapa do fluxo pode ter o seu ou nenhum. Conta em horas úteis. Quando estoura, a tela mostra e
   quem age na etapa recebe e-mail.
2. **Trade antecipado.** Operações pode executar o trade enquanto a solicitação ainda está na 1ª ou
   na 2ª aprovação. As aprovações que faltavam são puladas de vez, com motivo obrigatório, e a
   solicitação vai para a etapa Trade, onde Operações faz tudo do fluxo normal. A tela deixa claro que as aprovações foram
   puladas, e as áreas puladas recebem um e-mail informativo.
3. **2ª aprovação genérica.** Deixa de ser do CEO e passa a ser do time de gestão: quem tem a
   certificação de gestor (CGA, Certificação de Gestores ANBIMA), hoje o diretor e o CEO. O nome
   exibido passa a ser "Gestão (Aprovação trade)".

Fora da primeira entrega: o *fast track*, que fica para uma entrega futura deste projeto.

## Como o fluxo está hoje (sandbox, 18/11/2026)

Configuração lida do banco da shared na sandbox (migrations na `c3f81d5a92e7`, a mesma da master):

```
Rascunho (Gestão)
  → 1ª aprovação: Compliance + Risco (Jurídico com a config inativa; Compliance aprovado
                  pelo Sistema pela regra previous_approved_vehicles)
  → 2ª aprovação: CEO (ceo-pre-trade:approve)
  → Trade: Operações (operations-pre-trade:update) envia para a conferência
  → Conferência final: Jurídico (legal-pre-trade:review) conclui ou devolve para o Trade
  → Concluída
Nas aprovações: recusar → Rejeitada; devolver → Ajustes (Gestão) → 1ª aprovação
```

Avisos ligados: `STAGE_CHANGED`, `ACTION_REQUIRED`, `DEADLINE_OVERDUE` e `BYPASS_APPROVAL`. O aviso
de prazo vencido roda pelo agendador em banco (`0 9 * * 1-5`, America/Sao_Paulo): um e-mail por dia
útil enquanto a solicitação estiver com o prazo vencido. As consultas usadas estão em
`attachments/sandbox-config.sql`.

## O que já existe no código

- `workflows.process.stage_entered_at`: quando o processo entrou na etapa atual. É a base para contar
  o SLA (`apl-shared-service/src/infra/postgres/models/workflows.py:541`).
- `workflows.process.deadline_date`: prazo da solicitação inteira, com o chip "vence em X dias"
  (`apl-credit-whitelabel/src/app/features/pre-trade/components/deadline-chip/`) e o e-mail diário
  (`apl-shared-service/src/modules/pre_trade/business.py:733`). O SLA por etapa é um segundo relógio:
  a tela precisa diferenciar os dois.
- "Bypass" atual: aprovação automática pelo usuário Sistema quando uma regra é verdadeira
  (`workflows.rule`, `rule_permission`, `approval.rule_id`). O trade antecipado é outra coisa (pulo
  manual feito por uma pessoa) e não usa esse nome.
- O motor já aceita sair de uma etapa de aprovação por uma transição sem decisão (`on_decision`
  nulo), autorizada por permissão (`apl-shared-service/src/shared/business/workflows.py:767`). Ao
  sair assim, as vagas pendentes da rodada continuam `PENDING`: falta marcá-las como puladas.
- `uq_transition_workflow_id_stages`: uma transição por par de etapas. "2ª aprovação → Trade" já
  existe (é a aprovação); o antecipado para o Trade exige trocar essa regra (desenho, seção 5.3).
- O nome da permissão é calculado: `{grupo}-pre-trade:{ação}` e é o value da app role no Azure.
  "ceo" aparece no BFF (`src/shared/utils/permissions.py`, `src/modules/access_control/business/pages.py`,
  `src/modules/pre_trade/business/__init__.py`) e no front (`core/auth/groups.constants.ts`,
  `features/pre-trade/pre-trade.permissions.ts`, `core/auth/iam/write-needs-read.ts`).
- Calendário de dias úteis: o `data-lake-api` usa a biblioteca `holidays` com o calendário da B3
  (`src/shared/utils/business_days.py`). A shared ainda não tem calendário.

## Tarefas

Uma tarefa por arquivo em `tasks/`; esta tabela é o índice, preenchida por `ws item table`. As
tarefas entram depois de a abordagem técnica ser aprovada.

<!-- ws:items -->
| # | Tarefa | Card | Tipo | Responsável | Status |
|---|---|---|---|---|---|
| 01 | [[PRE-TRADE] SLA por etapa do fluxo](tasks/01-sla-per-stage.md) | TS-5846 | Nova função | dev-ae95329f82 | em andamento |
| 02 | [[PRE-TRADE] Trade antecipado com as aprovações puladas](tasks/02-early-trade.md) | TS-5847 | Nova função | dev-ae95329f82 | em andamento |
| 03 | [[PRE-TRADE] 2ª aprovação pela Gestão (Aprovação trade)](tasks/03-second-approval-portfolio-manager.md) | TS-5848 | Melhoria | dev-ae95329f82 | em andamento |
<!-- /ws:items -->

## Situação

18/11/2026: regras de negócio fechadas (D1 a D14). Próximo: apresentar as abordagens técnicas e
escrever o desenho.
