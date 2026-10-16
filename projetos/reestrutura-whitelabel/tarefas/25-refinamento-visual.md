# 25 — Refinamento visual e de design

- **TS:** a criar · **Branch:** `refact/TS-<id>-refinamento-visual` (da junção do front)
- **Status:** **a iniciar** (16/10); falta o TS e a confirmação da base
- **Depende de:** todas as branches do front (a junção: 13, 17, 18, 19, 20,
  21, 22 e 23, com as áreas dentro da 13)
- **Vai antes da 24:** o deploy leva o refinamento junto.

## Por quê

Pedido do Pietro em 16/10: revisar tudo o que o épico fez em estilo e design
e ajustar, em rodadas. Ele aponta, a tarefa corrige, e ele revisa de novo.

## Base: por que a junção e não branch por branch

O que a pessoa vê só existe junto:
- a 13 tirou o Material;
- a 23 pôs as ilustrações;
- a 19 e a 21 criaram a tela de acesso;
- e as peças comuns (`shared/ui`, tokens) vêm da 03 e da 04, alteradas pela
  13.

Corrigir branch por branch obrigaria a mexer em branches já publicadas e a
propagar cada ajuste por merge até as de cima. Já se viu que essa cadeia dá
conflito a cada rodada.

**Como fica:**
1. A branch nasce do último commit da junção (`$PRIV/junta-front`).
2. Os commits do refinamento ficam por cima, atômicos, um por peça ou tela.
3. **Não é publicada** enquanto as outras não estiverem na `sandbox`.
4. Quando estiverem, transplantar só os commits do refinamento:
   `git rebase --onto origin/sandbox <commit-da-junção>`. Depois publicar e
   abrir a PR, que fica só com o refinamento.
5. **Ajuste que vier da revisão de uma PR** (ex.: na 04) entra na branch
   dela. A junção é refeita, e o refinamento faz merge da junção nova.

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
