Status: concluída
Data: 29/10/2026
Tags: segurança, hooks

# 01 — Fase 1: portão no Claude Code

## O que ficou pronto

- **Portão** `hooks/approval_gate.py` (hook `PreToolUse` com matcher `Bash|mcp__.*`), regras em
  `hooks/gate/`: `bash_rules.py` (push, `gh`, `curl`/`wget`, `ws card apply`, leitura de
  credencial, proteção, comando não lido), `mcp_rules.py` (catálogo, resumos, conferência de
  sigilo do GitHub pessoal), `branches.py` (branches de ambiente), `decision.py` (texto da caixa;
  linhas `ATENÇÃO:` nunca são cortadas). Prazo interno de 5 s: se não decidir, pergunta.
- **Cópia protegida** em `~/.claude/hooks/workspace/` (arquivos 0444, pastas 0555, manifesto
  SHA-256), registrada com `python3 -I -B` e prazo de 30 s. Só muda por `ws setup` rodado à mão,
  com diff por arquivo e `s/N`. `hooks/ask_card_apply.py` ficou como ponte para clones antigos.
- **`ws setup`**: confere registro, cópia, `python3` dos hooks (3.11+), variáveis secretas no
  ambiente, servidor MCP do GitHub e servidores MCP fora do catálogo.
- **Card**: o resumo entra no código de aprovação; à mão no terminal pergunta `Gravar no Jira?
  [s/N]` (não vale com um agente entre os processos-pai).
- **Segredos**: `ws config token github`, `ws mcp-headers github` (o `headersHelper` do servidor MCP
  `github`), `env` do settings com `GITHUB_PERSONAL_ACCESS_TOKEN` e `AZURE_OPENAI_API_KEY` vazias.
- **Config local** `[gate]`: `push_without_asking`, `push_remotes`, `personal_github_owners`,
  `environment_branches`, `direct_push_repos` (tabela no README da raiz).
- **Modo manual**: `docs/manual.md`.

## Como foi feito

Cinco agentes na primeira leva, depois três rodadas de revisão (Opus) com correções em paralelo.

## O que atrasou (para não repetir na fase 2)

- Os worktrees dos agentes nasciam do GitHub, não da `main` local: contrato e spec precisam estar
  no GitHub antes de disparar.
- Dois reinícios do Claude Code derrubaram agentes no meio: pedir para não reiniciar, e commit por
  item.
- Revisões sucessivas caçando truques de shell num portão que lê texto; a fase 2 usa comandos e
  ferramentas estruturadas.
- O hook antigo saiu do repo antes do registro novo e bloqueou todo Bash: trocar registro e
  arquivo em ordem segura (ponte primeiro).

## Limites aceitos

"Known limits of phase 1" na spec: script em arquivo, `xargs`, `find -exec`, `ssh`, fork duplo,
nomes montados em tempo de execução, comando entregue ao shell por pipe, `GIT_CONFIG_GLOBAL`,
palavra com espaços acima de 4 KB, e as ferramentas Edit e Write fora do matcher. Fecham na fase 3.
