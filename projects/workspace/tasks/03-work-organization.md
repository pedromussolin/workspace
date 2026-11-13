+++
tracker = false
status = "todo"
+++
Status: proposta (o usuário pode mudar o plano)
Data: 30/10/2026
Tags: organização, projetos, kanban, ws

# 03 — Organizar os projetos em contexto, iniciativa, épico e item

> Atualização de 08/11/2026: o desenho da base do produto substitui parte desta proposta. Espaço
> por empresa, cliente ou pessoal no topo, com um repo git cada (D17, D20); "Contexto" vira sistema
> cadastrado (D19); a iniciativa vira projeto livre e a `sustentacao/` vira `inbox/` (D18). Itens
> planos com campos (P10) e migração por script (P12) seguem valendo. Ver o `decisions.md` e a
> passagem citada no `CONTINUE.md`.

## Por que

Hoje `projects/<slug>/` tem uma pasta `tasks/` plana e numerada à mão, e documentos de conhecimento
soltos na raiz: o whitelabel tem 48 tarefas (com números compostos como `02-03-...`) e
`findings.md`, `target-architecture.md` na raiz; o artemis-v2 tem GMUDs, estimativas e atas
misturadas na raiz. Projetos tocam vários repos, e não há lugar para bug, hotfix ou release. O
usuário quer um padrão de scrum/kanban: iniciativas (que podem ser do mesmo contexto), cada uma com
épicos, tarefas, bugs, hotfix e o que mais vier.

## Modelo proposto

Cinco conceitos, só três níveis de pasta; o resto são campos nos arquivos.

| Conceito | O que é | Exemplo | Onde mora |
|---|---|---|---|
| Contexto | domínio ou sistema estável, dono do conhecimento, dos repos e das releases | cessão, portal (whitelabel), workspace pessoal, estudos | pasta |
| Iniciativa | objetivo com início e fim, num contexto principal (pode tocar outros) | Artemis V2, Reestrutura whitelabel, Portões de aprovação | pasta |
| Épico | entrega grande dentro da iniciativa; casa com o épico do Jira quando houver | TS-5278, "fase 2 dos portões" | arquivo |
| Item | unidade de trabalho com tipo: história, tarefa, bug, hotfix, spike (investigação), chore | TS-5435, WS-0012 | arquivo |
| Release | pacote que vai a produção; junta itens de várias iniciativas por repo e gera a GMUD | release 27/10 da cessão | arquivo no contexto |

```
work/
  repos.toml                         registro: repo → contexto, tipo (front/BFF/argocd), branches de ambiente
  <contexto>/                        ex.: cessao/
    README.md  CLAUDE.md             regras do contexto (ex.: revisão da DBA, réplica só leitura)
    knowledge/                       arquitetura, domínio, glossário, runbooks, atas
    releases/2026-10-27.md           itens, PRs por repo, link da GMUD
    <iniciativa>/                    ex.: artemis-v2/, e uma permanente: sustentacao/
      README.md  CLAUDE.md  CONTINUE.md  decisions.md
      epics/<slug>.md                objetivo, chave do épico no Jira, status
      items/TS-5435-fechar-lote.md   front matter TOML: tipo, status, épico, repos, branches, PRs, datas
      evidence/  attachments/
```

Regras:

1. **Item é um arquivo só e nunca muda de lugar.** Épico, tipo e status são campos; mudar de épico
   é editar uma linha, nenhum link quebra.
2. **Quadros e índices são gerados.** `ws board` monta o kanban (com WIP, o limite de trabalho em
   andamento, por coluna) e `ws index` as tabelas dos arquivos README; ninguém edita tabela à mão, o que
   acaba com conflito entre chats.
3. **Status vem do Jira quando o item tem chave; local quando não tem.** As colunas são as que o
   `ws` já mapeia: todo, em andamento, review, validação, ready deploy, block, feito, cancelado.
4. **O front matter do item é o mesmo formato do rascunho do `/card`** (TOML entre `+++`), para o
   card nascer do item por script.
5. **ID:** a chave do Jira quando existe (`TS-5435`); senão um prefixo local por iniciativa
   (`WS-0012`), estável.

## Teste contra casos difíceis

| Caso | Como o modelo resolve |
|---|---|
| Item que toca 3 repos (shared → BFF → front) | campo `repos` com branch e PR de cada um; a release lê por repo |
| Hotfix em produção sem iniciativa | vai para a iniciativa permanente `sustentacao/` do contexto (substitui o `standalone`) |
| Bug achado no épico A e corrigido no B | tipo `bug`, campo `related = ["TS-…"]`; o arquivo fica na iniciativa que corrige |
| Card criado por outra pessoa no Jira | `ws item import TS-…` cria o arquivo, mascarando nomes reais do título |
| Item sem Jira (workspace pessoal) | ID local com prefixo da iniciativa (`WS-0012`) |
| Release com itens de duas iniciativas | a release mora no contexto e lista itens de qualquer iniciativa dele |
| Iniciativa que cruza contextos (whitelabel toca o shared) | contexto principal mais campo `touches`; repos vêm do `repos.toml` |
| Conhecimento usado por duas iniciativas | fica em `knowledge/` do contexto, sem duplicar |
| Dois chats na mesma iniciativa | cada item é um arquivo e os índices são gerados: quase nenhum conflito |
| Iniciativa encerrada | status `concluída`; o quadro filtra, nada muda de pasta |
| Portão e release | leem `repos.toml` (substitui o `direct_push_repos` e listas soltas do config) |

## O que muda nas ferramentas (script primeiro)

- `ws project new` vira criação de contexto e de iniciativa (com `knowledge/`, `epics/`, `items/`).
- Comandos novos: `ws epic new`, `ws item new` (com tipo), `ws item import TS-…`, `ws board`,
  `ws index`.
- `ws work migrate`: move tarefas para itens a partir de um mapa que o Claude propõe e o usuário
  aprova, e corrige os links relativos.
- Checkpoint e daily continuam lendo `CONTINUE.md` e "Próximo passo" de cada iniciativa; a daily
  passa a agrupar por item e mostrar o épico.
- O item 7 do backlog (revisão do quadro) vira o `ws board`.

## Decisões pendentes

P8 a P13 no `decisions.md` deste projeto, cada uma com a recomendação. A ordem em relação à fase 2
dos portões também está em aberto (P13).

## Migração (quando for feita)

1. `workspace` primeiro (pequeno) e os projetos novos.
2. `artemis-v2` e `whitelabel-restructure` só com os chats deles parados (mover 268 arquivos com
   outro chat editando gera conflito).
3. Spec e plano antes de construir; uma rodada de agentes; uma revisão no fim.
