# Brief: tela do front (apl-credit-whitelabel)

Copie, preencha os campos entre `<>` e apague as linhas que não valem. O texto fixo não sai. A
revisão visual é outro brief, para outro agente: `front-screen-review.md`.

Você trabalha numa tela do portal (`apl-credit-whitelabel`, Angular). Seu nome: `<nome-do-agente>`.

## Tarefa

- Card: `<TS-id>`. Worktree: `<caminho>`. Branch: `<branch>` (só nela).
- O que fazer: `<o pedido, em poucas linhas>`.
- Arquivos: `<as pastas e os arquivos da tela>`.
- O que o usuário disse, com as palavras dele e os prints: `<citação e caminhos dos prints>`.
- Trechos de regra que valem aqui, com o caminho: `<trechos de .ai/rules/... e da memória>`.
- Já descartado: `<o que não fazer e por quê>`.

## Antes de escrever código

1. Leia o `CLAUDE.md` do repositório e o `.ai/README.md`, **na ordem que ele manda**:
   `boundaries.md`, a skill da tarefa e as regras que ela pede.
2. **Carregue a skill da tarefa e siga o que ela manda**: `<new-page | new-component | fix-bug>`
   (em `.ai/skills/<nome>/SKILL.md`). Para mudar o layout de uma tela que já existe: a anatomia
   (item 3) e depois a `validate-change`. Em código e padrão vale a skill; em git, espera e
   containers vale este brief (sem branch nova e sem commit, mesmo que a skill mande).
3. Abra as telas de referência e copie delas a organização: `.ai/context/reference-screens.md`
   (comece pela seção "Anatomia da página"), o Pré-Trade (`src/app/features/pre-trade/`) e os
   Lotes de Liquidação (`src/app/features/liquidation-batches/`).
4. Componente só de `src/app/shared/ui`. Nada que abra o seletor do navegador (`type="time"`,
   `date`, `datetime-local`, `month`, `week`, `<select>`): o que faltar nasce em `shared/ui`, pela
   skill `new-component`, nunca local na tela.

## Rodar

Não há node no host. Tudo roda na imagem `whitelabel-front-dev:latest`, com a worktree em
`/workspace`. O `node_modules` da worktree costuma estar vazio: monte o de outra worktree com o
mesmo `package-lock.json`, só leitura.

```bash
docker run --rm -v <worktree>:/workspace -v <worktree com dependências>/node_modules:/workspace/node_modules:ro -w /workspace --entrypoint sh whitelabel-front-dev:latest -c "<comando>"
```

## Antes de dizer que terminou

1. `validate-change`, seções 1 a 3: build, lint, `check-patterns`, testes e o smoke, com os prints
   em claro (1440 px), celular (390 px) e escuro. A seção 4 (commits) fica com quem controla a
   tarefa.
2. **Olhe os prints** ao lado dos do Pré-Trade e dos Lotes, nas mesmas larguras
   (`/pre-trade /liquidation-batches` no mesmo smoke, ou como cenas).
3. Não revise a própria tela: a `review-screen` é de outro agente, sem o seu contexto. Entregue o
   que ele precisa (abaixo).

## Regras

- Sem commit, push, branch nova ou `git stash`. Entregue os commits planejados (`<tipo>(TS-id):
  ...`, PT-BR, até 72 caracteres, atômicos).
- Nunca guarde comando em variável. Arquivo novo pela ferramenta Write, nunca por heredoc.
- Nunca espere em laço (`while`/`until` + `sleep`). Comando longo com `run_in_background`; espera
  inevitável sob `timeout N`; nada de `pgrep -f`/`pkill -f`.
- Não derrube containers que você não subiu. No fim, confira que não sobrou nada seu rodando.
- Rascunhos e logs em `<pasta do agente>`; prints com `OUT=<pasta do agente>/prints` no smoke.

## Entrega

`<pasta do agente>/entrega.md` e resposta curta: o que mudou (antes e depois, em palavras), as
rotas mudadas e **os estados que importam** (com dado, sem dado, cada aba ou visão) como URL com
os filtros ou como cena `SCENES` pronta para colar, os caminhos dos prints, testes e lint com
números, os desvios da skill ou do brief com o porquê, e os commits planejados.
