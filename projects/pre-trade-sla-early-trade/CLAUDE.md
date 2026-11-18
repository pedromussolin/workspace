Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# pre-trade-sla-early-trade: regras do projeto

SLA por etapa, trade antecipado e 2ª aprovação genérica no fluxo do Pré-Trade. Aqui ficam as
decisões, as tarefas e o desenho; o código vive nos repositórios da empresa.

As regras comuns (sigilo, commits, idioma e sincronização) estão no `AGENTS.md` e em
`docs/conventions/` da raiz do repositório. Aqui ficam só as regras específicas deste projeto.

## Regras deste projeto

- O motor de workflows é genérico: SLA, pulo de aprovações e avisos novos entram nele sem citar o
  Pré-Trade; o módulo `pre_trade` só integra (avisos, rótulos, regras do fluxo). Nada de FK, import
  ou chamada entre as features genéricas (workflows, e-mail, agendamento).
- Mudança de arquitetura (camadas, contrato entre shared, BFF e front, `test_arch`, wiring) só com
  o desenho aprovado pelo usuário.
- Migration já aplicada não se altera: mudança de configuração do fluxo vai em migration nova.
- Agendamento só pelo banco (`scheduler.scheduled_jobs`), nunca horário fixo no código.
- A configuração do fluxo que vale é a da sandbox: conferir lá antes de afirmar como o fluxo está.

## Valores reais fora do repo

Hosts, URLs, credenciais e nomes reais ficam no arquivo local
`~/.config/workspace/private/pre-trade-sla-early-trade.md`, fora do controle de versão. Aqui entra só
a referência genérica, como "banco da shared na sandbox".

## Dados locais fora do repo

Worktrees, logs, travas, arquivos de deploy e evidências com dados reais ficam em
`~/.local/share/workspace/projects/pre-trade-sla-early-trade/`, criada pelo `ws project new`. Nada
dali entra no repo; aqui entra só o caminho.

## Repositórios envolvidos

- `apl-shared-service`: motor de workflows (`src/shared/business/workflows.py`), módulo
  `src/modules/pre_trade`, migrations e o agendador em banco.
- `apl-credit-whitelabel-api`: BFF; listas de permissões e páginas do controle de acesso, rotas do
  Pré-Trade.
- `apl-credit-whitelabel`: front; `src/app/features/pre-trade` (trilha de etapas, chip de prazo,
  histórico, ações).
