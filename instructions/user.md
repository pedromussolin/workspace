<!-- Instruções globais do Claude Code. O `ws setup` liga este arquivo como `~/.claude/CLAUDE.md`; edite aqui, no repo (versionado, sem nome real). -->

# Regras para todo repo

## Comunicação

- Explique todo termo técnico que usar.
- Seja claro e objetivo: a conclusão primeiro, depois o porquê em poucos pontos. Nada de
  metáfora, menu de opções ou frase de efeito. Detalhe longo vai para o documento, não para o chat.
- Verifique antes de afirmar: rode o comando que comprova (`git reflog`, `git ls-remote`,
  `git log <ref>`) antes de escrever a frase. Sem como verificar, diga que vai verificar.
- Pergunte só regra de negócio e arquitetura, numerado, com opções e a sua recomendação. Ordem
  técnica (migrations, de que branch sai cada card, ordem das PRs) você recomenda e segue,
  dizendo o porquê em uma linha.
- Checagem do tamanho do risco: uma consulta, não varredura. Erro de serviço externo vira uma
  linha no relatório, não uma série de tentativas.

## Bash

Vale também para os agentes.

- Não guarde comando em variável para rodar depois (`A="git -C x"; $A diff`): o portão de
  aprovação não sabe qual programa vai rodar e pede confirmação. Use `git -C <pasta> diff` direto.
- `git push`, `gh` que grava (pr create/edit/comment, api com escrita) e `curl`/`wget` de envio vão
  numa chamada própria e curta, sem outros comandos encadeados: a caixa de aprovação mostra o
  comando inteiro e o usuário precisa ler só o envio.
- O `/tmp` é um tmpfs com limite de 1 milhão de inodes: pytest com
  `--basetemp=$HOME/.cache/ws-pytest/<tarefa>` (apague a pasta depois), rascunho e cópia isolada
  fora do `/tmp`.

## Leitura e contexto

Vale também para os agentes.

A qualidade vem primeiro; o objetivo é não encher o contexto com o que não ajuda a decidir.

- Para achar algo, use grep/rg e leia o trecho que importa com folga (a função ou a seção
  inteira). Leia o arquivo inteiro quando for alterá-lo ou quando o todo importar; não faça `cat`
  de vários arquivos de uma vez "para garantir".
- Não releia o que já está na conversa, a não ser que o arquivo tenha mudado.
- Saída longa (teste, build, log): mostre o que decide (`tail`, `grep -E 'FAIL|error'`) e guarde a
  íntegra num arquivo, se precisar consultar depois.
- Sessão longa: handoff deliberado numa pausa natural (skill `handoff`), não compactação
  automática cedo. Ao propor uma economia de tokens, diga o que ela pode custar em qualidade.

## Agentes

Como o controlador escreve o brief e como os agentes trabalham, em todo repo:

@~/repos/workspace/docs/conventions/agents.md
