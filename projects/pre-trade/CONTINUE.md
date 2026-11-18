Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Continuar em outro chat

Leia antes: o `AGENTS.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

18/11/2026: os três cards (TS-5846 SLA, TS-5847 trade antecipado, TS-5848 2ª aprovação pela Gestão)
estão em andamento, implementados por cinco agentes em paralelo, revisados (código e revisão visual
das telas) e com as correções da revisão aplicadas. **Nada commitado**: tudo está no working tree das
sete worktrees. SLA padrão de 3h úteis (D18) já na migration do TS-5846. Decisões da revisão em D19 a
D24. Passagem de chat em
`~/.local/share/workspace/projects/pre-trade/HANDOFF-20261118-teste-do-front-e-commits.md`.

## Próximo passo

Ler o handoff inteiro. Montar uma worktree de teste do front a partir da master com os diffs dos três
cards (TS-5846, TS-5847, TS-5848) e subir com o mock para o usuário testar. Depois do ok: commits por
card e repositório, junção da corrente de migrations, push das branches e PRs.

## Branches e worktrees

Sete worktrees em `~/repos/.worktrees/` (`<repo>-TS-<id>`), uma por repositório de cada card, todas
sem upstream e sem commit. Lista completa no handoff.
