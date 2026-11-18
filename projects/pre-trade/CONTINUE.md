Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Continuar em outro chat

Leia antes: o `AGENTS.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

18/11/2026: levantamento feito no código (shared, BFF, front) e na configuração do fluxo na
sandbox (`README.md`, "Como o fluxo está hoje"). Regras de negócio decididas em D1 a D14; abordagem técnica em D15 e D16; desenho em
`attachments/design.md`, revisado por um agente. Ainda sem
card no TS, sem branch e sem código.

## Branches e worktrees

Nenhuma ainda.

## Próximo passo

Desenho aprovado em 18/11. Plano em `attachments/plan.md` (16 tarefas em 3 cards, por entrega).
Cards criados em 18/11 no épico TS-5046, com prazo 19/11: TS-5846 (SLA), TS-5847 (trade
antecipado), TS-5848 (2ª aprovação). Execução escolhida: por agentes (subagent-driven), um por
card, em paralelo, cada um na sua branch. Próximo: `/card iniciar` de cada card (branches e
movimento para em andamento) e disparar os agentes com o plano. O TS-5848 depende da app role nova
no Azure, criada pelo usuário, antes do deploy. Só depois: plano de implementação, cards no TS e branches.
