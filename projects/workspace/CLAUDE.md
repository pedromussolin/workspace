Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# workspace: regras do projeto

As regras comuns (sigilo, commits, idioma e sincronização) estão no `AGENTS.md` e em `docs/conventions/` da raiz do repositório. Aqui ficam só as regras específicas deste projeto.

## Valores reais fora do repo

Hosts, URLs, credenciais e nomes reais ficam no arquivo local `~/.config/workspace/private/workspace.md`, fora do controle de versão. Aqui entra só a referência genérica, como "host da réplica".

## Dados locais fora do repo

Worktrees, logs, travas, arquivos de deploy e evidências com dados reais ficam em `~/.local/share/workspace/projects/workspace/`, criada pelo `ws project new`. Nada dali entra no repo; aqui entra só o caminho.

## Repositórios envolvidos

- `workspace` (este repo): o código vive em `src/ws/` (CLI `ws`), `hooks/` (portão e hooks do
  Claude Code) e `tests/`; o desenho em `docs/specs/`, os planos em `docs/plans/`.

## Regras deste projeto

- Mudança no portão ou nos hooks só chega à cópia protegida por `ws setup` rodado pelo usuário no
  terminal dele; nunca peça ao usuário para pular a revisão do diff.
- Nunca leia `~/.config/workspace/credentials` nem imprima valor de variável secreta; para testar
  um token, passe-o por pipe e mostre só status e login.
- Teste de portão alimenta o hook com texto (JSON no stdin); nada de `git push`, `gh` de escrita ou
  `curl` de envio de verdade.
