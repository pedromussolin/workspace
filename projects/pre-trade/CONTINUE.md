Status: rascunho
Data: 18/11/2026
Tags: pre-trade, workflows, sla, aprovacoes, portal

# Continuar em outro chat

Leia antes: o `AGENTS.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

18/11/2026: a release 20261118, com os três cards (TS-5846 SLA, TS-5847 trade antecipado, TS-5848 2ª
aprovação pela Gestão), está na sandbox e validada. Teste manual feito, versões novas no ar e sem
erro nas rotas. Os cards foram commitados e encadeados (TS-5846 → TS-5847 → TS-5848), e a corrente de
migrations é única. As PRs de produção estão abertas, uma por repositório. Na sandbox, a primeira
migration do pulo de aprovações falhou porque o usuário da aplicação não era dono de um tipo enum. A
DBA trocou o dono, e o mesmo ajuste é pré-requisito em produção. A GMUD (não programada) está pronta,
fora do repo, e ainda não foi criada no portal. Os cards estão na sprint atual, em validação. Passagem
de chat em
`~/.local/share/workspace/projects/pre-trade/HANDOFF-20261118-deploy-producao-release-20261118.md`.

## Próximo passo

Ler o handoff inteiro. Criar a GMUD no portal com o início, o fim e o escopo confirmados pelo usuário.
Depois, acompanhar o deploy em produção na ordem shared → BFF → front, preparando as tags de produção
no argocd para o usuário subir. Por fim, ligar o job do aviso de SLA e mover os cards para concluído.

## Branches e worktrees

Sete worktrees em `~/repos/.worktrees/` (`<repo>-TS-<id>`), uma por repositório de cada card, todas
sem upstream e sem commit. Lista completa no handoff.
