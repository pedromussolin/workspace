Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# workspace

## Visão geral

O projeto do próprio workspace: o CLI `ws`, as skills e os hooks do Claude Code deste repo. O
backlog geral está em [docs/backlog.md](../../docs/backlog.md); as specs e os planos, em
`docs/specs/` e `docs/plans/`. A frente atual são os **portões de aprovação**, descritos abaixo; a
próxima no backlog é a skill de release, que espera a fase 2b.

### Portões de aprovação

Nenhuma escrita fora da máquina (Jira, GitHub, portal de GMUD) acontece sem uma caixa de aprovação
que diga em PT-BR o que muda, onde e com qual conteúdo. A estrutura funciona com qualquer harness
(o programa que roda o modelo: Claude Code agora, opencode e modelos locais depois) e todo fluxo
também roda à mão, sem IA.

Prioridades do usuário, nesta ordem: **A** nada grava fora sem o sim de verdade (erro do modelo ou
instrução escondida num texto, a *prompt injection*); **C** sigilo (nomes reais e segredos no GitHub
pessoal); **B** aprovação que se entende.

Fases dos portões:

1. **Portão no Claude Code** — concluída e instalada em 29/10 ([tarefa 01](tasks/01-phase1-gate.md)).
2. **Aprovação no `ws`** — próxima: 2a (registro de pedidos, painel `ws approvals`, servidor MCP
   `ws`, card migrado), 2b (escritas do GitHub pelo `ws`), 2c (GMUD) ([tarefa 02](tasks/02-phase2-approvals.md)).
3. **Nosso sandbox** (caixa com bubblewrap em volta do agente inteiro; chaves e aprovação fora dela).
   O teste de viabilidade deu "vai" com quatro condições.
4. **Outros harnesses** (adaptador do opencode, links das skills, teste com modelo local).

Documentos:

- Desenho: [docs/specs/2026-10-28-approval-gates-design.md](../../docs/specs/2026-10-28-approval-gates-design.md)
  (inclui "Known limits of phase 1" e "Environment branches").
- Plano da fase 1: [docs/plans/2026-10-28-approval-gates-phase1.md](../../docs/plans/2026-10-28-approval-gates-phase1.md).
- Teste de viabilidade do sandbox: [docs/research/2026-10-28-sandbox-spike.md](../../docs/research/2026-10-28-sandbox-spike.md).
- Modo manual: [docs/manual.md](../../docs/manual.md). Comandos e hooks: [README.md](../../README.md).

## Máquina nova (passo a passo)

O que fica fora do git precisa ser montado em cada máquina. Nesta ordem:

1. Python 3.12, `uv` e o `python3` do sistema 3.11 ou mais novo (os hooks rodam com ele).
   `git clone` do repo em `~/repos/workspace`, depois `uv tool install --editable .`.
2. Traga da máquina antiga, por um canal seguro e nunca pelo git: `~/.config/workspace/names.toml`,
   `private/` e `config.toml` (este não tem segredo; ajuste `[gate] push_without_asking` e
   `push_remotes` se o caminho do clone ou o remoto mudarem). O `credentials` não se copia.
3. No seu terminal, fora do Claude: `ws config token jira` e `ws config token github`. Token do
   GitHub *fine-grained*: Contents e Pull requests leitura e escrita, Metadata leitura (Actions e
   Commit statuses leitura, opcionais). Nenhum token em `export` no `~/.bashrc`.
4. `ws setup` no seu terminal: liga os hooks do git, as skills, os dicionários e a cópia protegida
   dos hooks do Claude (mostra o diff e pede `s/N`). Ele imprime o bloco JSON para o
   `~/.claude/settings.json` (hooks a partir da cópia, regras `ask`, `env` com as variáveis
   secretas vazias): peça ao Claude para aplicar e aprove a caixa.
5. Rode o comando `claude mcp add-json github ...` que o `ws setup --check` imprime (servidor MCP
   do GitHub com o token buscado pelo `ws mcp-headers`).
6. Reinicie o Claude Code e confira: `ws setup --check` sem pendências (o aviso do servidor
   `higgs-hub`, fora do catálogo, é conhecido), o MCP do GitHub responde (`get_me`) e um `git push`
   num repo da empresa mostra a caixa em PT-BR.

## Tarefas

Uma tarefa por arquivo em `tasks/`; esta tabela é o índice.

| # | Tarefa | Status |
|---|---|---|
| 01 | [Fase 1: portão no Claude Code](tasks/01-phase1-gate.md) | concluída (29/10) |
| 02 | [Fase 2: aprovação no `ws`](tasks/02-phase2-approvals.md) | decisões pendentes |

## Situação

30/10/2026: fase 1 instalada e conferida nesta máquina; a fase 2 espera a resposta às sete decisões
pendentes do `decisions.md` para virar spec e plano.
