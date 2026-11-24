Status: rascunho
Data: {{data}}
Tags:

# {{slug}}: regras do projeto

As regras comuns (sigilo, commits, idioma e sincronização) e as regras de trabalho em `instructions/` estão no `AGENTS.md` e em `docs/conventions/` da raiz do repositório. Aqui ficam só as regras específicas deste projeto.

## Valores reais fora do repo

Hosts, URLs, credenciais e nomes reais ficam no arquivo local `~/.config/workspace/private/{{slug}}.md`, fora do controle de versão. Aqui entra só a referência genérica, como "host da réplica".

## Dados locais fora do repo

Worktrees, logs, travas, arquivos de deploy e evidências com dados reais ficam em `~/.local/share/workspace/projects/{{slug}}/`, criada pelo `ws project new`. Nada dali entra no repo; aqui entra só o caminho.

## Repositórios envolvidos

Uma linha por repositório: o nome e para que ele serve neste projeto. O código vive lá; aqui ele se cita por `arquivo:linha`.
