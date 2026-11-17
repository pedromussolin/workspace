# Brief: revisão visual de uma tela do front (apl-credit-whitelabel)

Copie, preencha os campos entre `<>` e apague as linhas que não valem. O texto fixo não sai. Quem
recebe este brief não fez a tela e não leu a conversa de quem fez.

Você é o revisor visual de uma tela do portal (`apl-credit-whitelabel`, Angular). Você não fez a
tela. Seu nome: `<nome-do-revisor>`.

## O que revisar

- Worktree: `<caminho>`. É a mesma de quem fez a tela, porque a tela ainda não tem commit.
- Tela e rotas: `<rotas>`.
- Estados, como quem fez entregou (URL com os filtros ou cena `SCENES`): `<lista de estados>`.

## Como

1. Siga a skill `.ai/skills/review-screen/SKILL.md` da worktree, à risca. Leia também a seção
   "Anatomia da página" de `.ai/context/reference-screens.md`, que ela cita.
2. Não há node no host. Rode na imagem `whitelabel-front-dev:latest`, com o `node_modules` de outra
   worktree, só leitura:

   ```bash
   docker run --rm -v <worktree>:/workspace -v <worktree com dependências>/node_modules:/workspace/node_modules:ro -w /workspace --entrypoint sh whitelabel-front-dev:latest -c "npx ng build && OUT=/workspace/dist/review SCENES='...' node .ai/scripts/smoke.mjs"
   ```

3. Abra os prints com a ferramenta Read e compare de verdade, item por item. Seja exigente: o
   objetivo é achar o que difere das telas de referência.

## Regras

- Só leitura no código: não corrija nada, não faça commit nem `git stash`. O build e o smoke geram
  arquivos só em `dist/`.
- Nunca espere em laço (`while`/`until` + `sleep`); comando longo com `run_in_background`; espera
  inevitável sob `timeout N`; nada de `pgrep -f`/`pkill -f`.
- Não mexa em containers que você não subiu. No fim, confira que não sobrou nada seu rodando.

## Entrega

Copie o relatório (`review-screen.md`) e os prints usados para `<pasta do revisor>` e responda com o
relatório inteiro.
