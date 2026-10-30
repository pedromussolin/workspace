Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

30/10/2026. Frente atual: portões de aprovação. Fase 1 concluída, instalada e conferida nesta máquina (detalhe na
[tarefa 01](tasks/01-phase1-gate.md)):

- portão único `hooks/approval_gate.py` (regras em `hooks/gate/`), rodando da cópia protegida
  `~/.claude/hooks/workspace/`, que só muda por `ws setup` rodado à mão, com diff e `s/N`;
- caixa em PT-BR; catálogo MCP que lista leituras (`ws gate catalog` para classificar);
- card à mão no terminal (`Gravar no Jira? [s/N]`); token do GitHub fora do ambiente
  (`ws mcp-headers` + servidor MCP `github`); variáveis secretas vazias nas sessões;
- branches de ambiente: push e merge bloqueados fora dos repos `*-argocd`.

Três revisões de segurança; o usuário aceitou parar aí, porque um portão que lê texto nunca fecha.
O que sobrou está em "Known limits of phase 1" da spec. A suíte tem 2744 testes, todos passando.

Correção de 30/10 (`2e8430e`): no workspace, um push de `main` dentro de um comando maior era
bloqueado pela regra de branch de ambiente; agora pergunta. Ela só vale na cópia protegida depois
de um `ws setup` rodado pelo usuário no terminal (mostra o diff de `bash_rules.py`). Até lá, faça o
push do workspace sozinho no comando (`git push`, sem `-C` nem `cd`).

Pedi as sete decisões da fase 2 (`decisions.md`, P1 a P7) e o usuário ainda não respondeu: ele
mudou para outra máquina.

## Branches e worktrees

- `workspace`: tudo na `main`, sincronizada com o GitHub; nenhum worktree de agente aberto.

## Próximo passo

1. Máquina nova? Siga "Máquina nova" no `README.md` deste projeto antes de tudo.
2. Pergunte antes a ordem (P13): a reorganização dos projetos (tarefa 03, em proposta) vem antes
   ou depois da fase 2. Depois leve as decisões P1 a P7 (ou P8 a P12) do `decisions.md` numa pergunta só, com a recomendação de
   cada uma (ele pediu para acelerar: uma rodada de decisões, não uma pergunta por vez).
3. Com as respostas: escreva a spec curta da fase 2 em `docs/specs/`, o código do contrato comum
   (registro de pedidos e interface de executor) e faça o push antes de disparar os agentes.
4. Dispare 2a e 2b em paralelo, como diz "Processo" na [tarefa 02](tasks/02-phase2-approvals.md).
