# Brief: tela do front (apl-credit-whitelabel)

Copie, preencha os campos entre `<>` e apague as linhas que não valem. O texto fixo não sai.

Você trabalha numa tela do portal (`apl-credit-whitelabel`, Angular). Seu nome: `<nome-do-agente>`.

## Tarefa

- Card: `<TS-id>`. Worktree: `<caminho>`. Branch: `<branch>` (só nela).
- O que fazer: `<o pedido, em poucas linhas>`.
- O que o usuário disse, com as palavras dele e os prints: `<citação e caminhos dos prints>`.
- Já descartado: `<o que não fazer e por quê>`.

## Antes de escrever código

1. Leia o `CLAUDE.md` do repositório e o `.ai/README.md`, **na ordem que ele manda**:
   `boundaries.md`, a skill da tarefa e as regras que ela pede.
2. **Carregue a skill da tarefa e siga o que ela manda**: `<new-page | new-component | fix-bug |
   validate-change>` (em `.ai/skills/<nome>/SKILL.md`). Brief e skill divergem: vale a skill;
   diga a divergência na entrega.
3. Abra as telas de referência e copie delas a organização: `.ai/context/reference-screens.md`
   (comece pela seção "Anatomia da página"), o Pré-Trade (`src/app/features/pre-trade/`) e os
   Lotes de Liquidação (`src/app/features/liquidation-batches/`).
4. Componente só de `src/app/shared/ui`. O que faltar nasce lá, pela skill `new-component`,
   nunca local na tela. Nada de controle nativo do navegador (`time`, `date`, `number`, `select`)
   onde o `shared/ui` tem um componente.

## Rodar

Não há node no host. Tudo roda na imagem `whitelabel-front-dev:latest`, com a worktree em
`/workspace`:

```bash
docker run --rm -v <worktree>:/workspace -w /workspace --entrypoint sh whitelabel-front-dev:latest -c "<comando>"
```

## Antes de dizer que terminou

1. `validate-change` inteira: build, lint, `check-patterns`, testes e o smoke da rota, com os
   prints em claro (1440 px), celular (390 px) e escuro.
2. **Olhe os prints** ao lado dos do Pré-Trade e dos Lotes, nas mesmas larguras.
3. A revisão visual (`review-screen`) é de **outro agente**, sem o seu contexto: entregue as rotas
   e o caminho dos prints para quem controla a tarefa disparar a revisão. Não revise a própria tela.

## Regras

- Sem commit, push, branch nova ou `git stash`. Entregue os commits planejados (`<tipo>(TS-id):
  ...`, PT-BR, até 72 caracteres, atômicos).
- Nunca guarde comando em variável. Arquivo novo pela ferramenta Write, nunca por heredoc.
- Nunca espere em laço (`while`/`until` + `sleep`). Comando longo com `run_in_background`; espera
  inevitável sob `timeout N`; nada de `pgrep -f`/`pkill -f`.
- Não derrube containers que você não subiu. No fim, confira que não sobrou nada seu rodando.
- Rascunhos, logs e prints em `<pasta do agente>`.

## Entrega

`<pasta do agente>/entrega.md` e resposta curta: o que mudou (antes e depois, em palavras), os
caminhos dos prints, testes e lint com números, os desvios da skill ou do brief com o porquê, e os
commits planejados.
