Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

09/11/2026. Frente atual: o produto (o `ws` como assistente do dev para vender a devs do mundo
todo) e a base dele. Passagem completa, com o desenho em aberto:
`~/.local/share/workspace/projects/workspace/HANDOFF-20261109-base-do-produto.md`.

- Sincronização do board concluída e na `main`; evals `out-of-sync-card` e `daily-detailed`
  passam 3 de 3.
- Documento de descoberta de produto reescrito em 07/11 (assistente em sete frentes, núcleo
  hexagonal, concorrentes, lançamento, riscos): https://claude.ai/artifact/NLmKWGPFbZQcyjGez78G5U
- Tarefa 05 registrada: segredos por adaptador, para depois.
- Desenho da base (organização, memória, busca, nuvem) em andamento: decisões D14 a D23;
  pendentes P14 (três camadas com busca e grafo) e P15 (estrutura do repo de cada espaço).
- A fase 2 dos portões (P1 a P7) fica depois da base (D17).

Estado de 30/10, abaixo. Frente da época: portões de aprovação. Fase 1 concluída, instalada e conferida nesta máquina (detalhe na
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

1. Leia inteira a passagem `HANDOFF-20261109-base-do-produto.md` (caminho em "Onde parei").
2. Peça o ok do usuário em P14 e P15 numa pergunta só.
3. Siga o desenho da base uma seção por vez, com o ok dele: tipos de arquivo e campos, memória
   por nível, índice e busca, nuvem e sigilo, migração, portas do núcleo.
4. Escreva a spec em `docs/specs/`, commit e push; depois o plano.
5. Depois da base: a seção "Base" no documento de descoberta e a fase 2 dos portões.
