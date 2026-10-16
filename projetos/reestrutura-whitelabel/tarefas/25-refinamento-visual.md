# 25 — Refinamento visual e de design

- **TS:** TS-5395 · **Branch:** `refact/TS-5395-refinamento-visual` (da `release/20261016` do front)
- **Status:** **branch criada** (16/10), esperando a primeira rodada de revisão
- **Depende de:** todas as branches do front (a junção: 13, 17, 18, 19, 20,
  21, 22 e 23, com as áreas dentro da 13)
- **Vai antes da 24:** o deploy leva o refinamento junto.

## Por quê

Pedido do Pietro em 16/10: revisar tudo o que o épico fez em estilo e design
e ajustar, em rodadas. Ele aponta, a tarefa corrige, e ele revisa de novo.

## Base: a release

Decidido em 16/10 (Pietro): juntar tudo numa release, criar o refinamento a
partir dela e subir no ambiente. A release é a da 24 (`release/20261016`),
com todas as branches do front juntas, uma por merge. Por que não branch por
branch:
- o que a pessoa vê só existe junto: a 13 tirou o Material, a 23 pôs as
  ilustrações, e a 19 e a 21 fizeram a tela de acesso;
- as peças comuns (`shared/ui`, tokens) vêm da 03 e da 04, alteradas pela 13;
- corrigir na origem obrigaria a propagar cada ajuste por merge em cadeia.

**Como fica:**
- os commits do refinamento ficam na `refact/TS-5395-refinamento-visual`,
  atômicos, um por peça ou tela;
- cada rodada volta para a release por PR (ou merge), e a release segue
  para a sandbox;
- ajuste que vier da revisão de uma tarefa entra na branch dela, e a release
  faz merge de novo.

## Para começar (outro chat)

- **Worktree:** `~/repos/apl-credit-whitelabel-wt/25`, branch
  `refact/TS-5395-refinamento-visual`, igual à `release/20261016` (`082111a5`),
  com `node_modules` e build prontos.
- **Portal local:** `anexos/scripts/portal-local.sh ~/repos/apl-credit-whitelabel-wt/25`
  (http://localhost:4300), com os dados fictícios de acesso, liquidação e
  Pré-Trade. `BUILD=1` refaz o build depois de cada rodada.
  - Pare o portal antes do `validar-leva.sh`, que usa as mesmas portas.
- **Validação da rodada:** `validar-leva.sh` com
  `BASE=082111a5`, `BASE_FALHAS=$PRIV/base-vazia-falhas.txt`,
  `BASE_LINT=20/163` e os dados `todas-acesso-21.json`. A base passa com
  2.210 testes, audit 0 e smoke ok.

## Como funciona a rodada

1. **Revisão:** o Pietro navega no portal local, com dados fictícios
   (`anexos/scripts/portal-local.sh`, ver o README), e anota o que mudar.
   - Pode ser por tela, por componente ou geral (cor, espaçamento,
     tipografia, densidade).
   - Print com marcação ajuda.
2. **Lista:** cada item entra na tabela abaixo, com tela, o que muda, onde
   (token, componente comum ou tela) e decisão.
3. **Correção:**
   - mudança em token ou componente comum vale para todas as telas e
     entra primeiro;
   - em lote, com agentes, um por grupo de telas.
4. **Validação:** junção completa (`validar-leva.sh` com smoke), prints
   antes e depois nas 4 marcas, claro e escuro e celular.
5. **Volta para o Pietro** com os prints e o portal local já atualizado.

## Regras

- Valem as da `.ai/`, sobretudo:
  - cor só por token, sem cor fixa;
  - contraste AA, conferido pelos specs de contraste;
  - responsivo em 390 px;
  - sem Angular Material;
  - ícones próprios.
- Mudança de padrão muda a `.ai/` no mesmo commit, e a vitrine
  (`/design-system`) mostra o novo.
- Nada de mudar URL, contrato com o BFF ou permissão: aqui é só aparência.

## Itens

| # | Tela ou peça | O que muda | Onde | Situação |
|---|---|---|---|---|
| R1 | Pré-Trade, lista | A 1440 px, Status e Ações ficam fora da tela (A34) | `features/pre-trade`, `shared/ui/table` | a decidir |
| R2 | Tabela comum | Erro "ResizeObserver loop" no console ao mudar a largura (A32) | `shared/ui/table` | a decidir |
