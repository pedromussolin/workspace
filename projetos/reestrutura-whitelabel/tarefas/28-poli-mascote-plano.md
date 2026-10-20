# POLI no portal e mascotes — plano de implementação

> **Para os agentes:** use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** a POLI entra no shell sem cabeçalho próprio, o chat vazio vira uma frase e quatro
mascotes em pixel art andam sobre a barra de digitar da POLI e da Home, reagindo ao chat e ao clique.

**Arquitetura:**
- **Motor puro** em `shared/ui/mascot/`, que só calcula os quadros: sprites, itens e controlador.
- **Componente `app-mascot`**, que desenha o quadro num SVG só, por signals.
- **`MascotService`** (raiz): preferências salvas no navegador e o canal de comandos (`play`,
  `setThinking`).
- **`app-mascot-picker`**, com a troca de mascote e a animação.
- **A feature integra:** a POLI liga os eventos do chat aos comandos; a Home só mostra o mascote.

**Stack:** Angular 20 (signals, OnPush, zone.js com `eventCoalescing`: o intervalo do mascote roda fora da zona), Karma/Jasmine, `shared/ui`.

**Spec:** [28-poli-mascote.md](28-poli-mascote.md) (D80–D85). Leia antes.

## Restrições globais

- Worktree `~/repos/apl-credit-whitelabel-wt/28`, branch `feature/TS-5406-poli-mascote`, da `6303b2e5`;
  `node_modules` é link para o da 25.
- **Sem commit pelos agentes.** O relatório traz os arquivos e a mensagem sugerida
  `tipo(TS-5406): …` (PT-BR, até 72 caracteres, sem `Co-Authored-By`).
- **Portas 4600–4699:** agente A 4600–4619, agente B 4620–4639, validação final 4690–4699. A 4300 e a
  8765 são do portal do Pietro.
- Comando pesado pelo `$PRIV/ng-slot.sh`. Rascunho em `$PRIV/agentes/28-<parte>/`, nunca em `/tmp`.
- **Contrato fixo** (escrito antes dos agentes, em `src/app/shared/ui/mascot/`): `mascot.models.ts`,
  `mascot.service.ts` e as assinaturas públicas de `mascot.component.ts` e
  `mascot-picker.component.ts`.
  - Mudar a API pública só com aviso a `main` (SendMessage).
  - O agente A completa o miolo; o B só usa.
- Textos fixos (PT-BR, exatos):
  - chat vazio e Home: "Escreva algo para iniciar um chat";
  - troca de mascote: rótulo "Mascote", nomes "Poli", "Cofre", "Moeda" e "Nota";
  - switch: "Animação";
  - botão da coluna recolhida: "Mascote e animação".

## Frente A — motor, componente e troca de mascote (`shared/ui/mascot/` e vitrine)

Cópia isolada: `git worktree add --detach $PRIV/agentes/28-motor/wt HEAD`, mais o contrato e o link
do `node_modules`. No fim, a pasta `shared/ui/mascot/` e o exemplo da vitrine voltam para a 28.

- [ ] **A1. Fixture de fidelidade.**
  - Um script em `$PRIV/agentes/28-motor/` carrega o código original:
    - `$PRIV/poli-mascote-original/poli-mascote/poli.js`;
    - a classe do `Palco.dc.html`, salvo em
      `$PRIV/poli-mascote-original/artefato/Palco.dc.html`.
  - O script grava `src/app/shared/ui/mascot/testing/mascot-fixtures.json` com:
    - as linhas de cada personagem, em cada pose da folha (parada, passo 1–4, boca aberta,
      segurando, comemorando, dormindo, piscando);
    - cada item com as opções da folha e os quadros intermediários (gráfico p=0,15/0,5/1, moedas
      n=1..4, escudo com brilho, contrato com e sem assinatura, calculadora com os dois visores);
    - uma sequência de quadros do controlador com sorteio fixo.
- [ ] **A2. Porte do motor.** Arquivos:
  - `mascot-sprites.ts`: `outline`, `poliRows`, os outros três personagens, `coinRows` e `body`;
  - `mascot-items.ts`;
  - `mascot-render.ts`: `toPaths` e `mix`;
  - `mascot-palettes.ts`: todas as cores fixas da arte, com uma entrada no `ALLOWED` do
    `check-patterns.mjs` e o motivo "cores fixas do pixel art dos mascotes, iguais às do pacote
    original";
  - `mascot-controller.ts`.
  - Matrizes e fases idênticas. Diferenças só as da spec:
    - sem `bubble` e sem status;
    - `stageWidth` dinâmico;
    - `idlePauseTicks` sorteado em [73, 136] quadros, ou 8–15 s;
    - `random` injetável;
    - `comemorar`, só com a fase happy;
    - `setThinking`;
    - um `pose()` só.
  - Cor da marca:
    - `b` do Cofre e o destaque dos itens viram `var(--brand-primary)`;
    - os tons derivados viram `color-mix(in srgb, var(--brand-primary) X%, <cor>)`, o mesmo `mix()`
      escrito em CSS;
    - o preenchimento vai por `style.fill`.
  - Spec do porte contra o fixture, caractere a caractere, e specs do controlador.
- [ ] **A3. `app-mascot`.**
  - Um `<svg>` com `viewBox` nas unidades do motor (pixel 6) e escala 0,5 (3 px) ou 1/3 (2 px, abaixo
    de 760 px).
  - Posições arredondadas para pixel de tela inteiro e `shape-rendering: crispEdges`.
  - `ResizeObserver` atualiza a largura do palco.
  - Animação ligada:
    - `setInterval` de 110 ms, parado quando a aba fica oculta (`visibilitychange`) e no destroy;
    - comandos do serviço: `play` e `thinking`;
    - clique: se estiver dormindo, `comemorar`; senão, ação sorteada diferente da atual.
  - Animação desligada:
    - sem intervalo;
    - parado à direita da barra (`stageWidth − largura − 24` unidades), na pose de repouso;
    - `thinking` → olhos para cima;
    - `play` ou clique → pose feliz por 1,2 s, com troca por opacidade (150 ms).
  - Altura do host conforme `MASCOT_STAGE_HEIGHT_PX`.
  - Fora do leitor de tela e do Tab; só o personagem tem `pointer-events`.
  - Spec de comportamento.
- [ ] **A4. `app-mascot-picker`.**
  - Grupo de rádio com as 4 miniaturas (pose parada, pixel 2) e o `app-switch` "Animação":
    - o switch fica ligado quando `animated()` é verdadeiro;
    - mudar o switch chama `setAnimated`.
  - `compact`: `app-icon-button` "Mascote e animação" com `app-menu` (as 4 opções e o switch).
  - Ícone: usar um que já existe em `icons.ts`. Ícone novo só com aviso a `main`.
  - Spec.
- [ ] **A5. Vitrine.** Exemplo de `app-mascot` e `app-mascot-picker` no registro da vitrine
  (`features/design-system/showcase/`), para o spec do registro passar. Atualizar
  `.ai/context/design-system.md` (seção de componentes) com uma linha sobre o mascote.
- [ ] **A6. Prints.** Página estática com os 4 personagens em todas as poses e itens. Comparar
  com o `spritesheet.png` (só a Poli) e com o artefato (os outros três).

## Frente B — página da POLI, shell e Home (`features/poli-chat/`, `features/general/home/`, `layouts/app-shell/`, `app.routes.ts`)

Na worktree 28. Não toca em `shared/ui/mascot/`: usa o contrato. Enquanto o A não termina, o
`app-mascot` não desenha nada, e os specs do B só conferem que ele está lá e que os comandos saem.

- [ ] **B1. Rotas e shell.**
  - As 11 rotas da POLI viram filhas do shell em `app.routes.ts`, com o mesmo `loadChildren`. URLs,
    guards e `data.department` ficam iguais.
  - Cada rota ganha `data.shellContent: 'full'`. O shell lê o `data` da rota ativa mais funda e tira
    a margem do `.shell__content` (classe `shell__content--full`).
  - Specs: `app.routes.spec.ts`, `poli-chat.routes.spec.ts` e o do shell.
- [ ] **B2. Sem cabeçalho.**
  - Apagar `poli-header/` (componente e spec).
  - O título do departamento (`pageTitle`) vai para o topo da coluna de histórico, acima do "Novo
    chat".
  - A página ocupa `100dvh` dentro do shell. No celular, abaixo da barra do shell.
  - Spec da página.
- [ ] **B3. Troca de mascote na coluna.**
  - `app-mascot-picker` no `utility-sidebar-footer`.
  - Coluna recolhida: `<app-mascot-picker compact />` no `utility-sidebar-collapsed`, abaixo do
    "Novo chat".
- [ ] **B4. Chat.**
  - O vazio mostra só "Escreva algo para iniciar um chat" e perde vídeo, saudação e `darkScheme`.
  - A `.textarea` vira `position: relative`, com `<app-mascot>` por cima (`bottom: 100%`).
  - A lista de mensagens reserva `MASCOT_RESERVED_SPACE_PX` embaixo.
- [ ] **B5. Eventos.** No `PoliChat`:
  - `sendChat` → `setThinking(true)`;
  - fim do stream sem erro → `setThinking(false)` e `play('contrato')` se a resposta trouxe arquivo
    gerado, senão `play('comemorar')`;
  - erro (do stream ou do `error`) → `setThinking(false)`;
  - `startNewChat`, troca de conversa e `ngOnDestroy` → `setThinking(false)`.
  - Spec com o serviço espiado.
- [ ] **B6. Home.**
  - Para a organização interna, o vídeo, a saudação e o texto saem; entram a frase e o
    `<app-mascot>` sobre a caixa.
  - Sai a lógica do vídeo (`poliVideo`, `onVideoReady`, novas tentativas de tocar).
  - A espera da Home (`isLoading`) não pode depender do vídeo.
  - Continuam: o aviso do modelo e o rodapé.
  - Spec da Home.
- [ ] **B7. Limpeza.**
  - Apagar `src/assets/general/poli-animation.webm` e `poli.svg`, depois de conferir que nada mais
    usa (`grep` no `src`, na `.ai/` e nos specs).
  - Textos que ficaram sem uso em `page.constants.ts`.
  - Os estilos órfãos.
- [ ] **B8. Smoke da frente.**
  - Rotas `/home`, `/poli-chat` e `/legal-poli-chat` com o BFF falso; o stream do chat por
    `page.route` (SSE fictício).
  - Prints: vazio, conversa e recolhida, em claro, escuro, Dots e celular.

## Junção e validação (main)

1. Copiar `shared/ui/mascot/` e a vitrine do A para a 28; `tsc`, os specs das duas frentes e o
   build.
2. `validar-leva.sh` com `BASE=6303b2e5`, `BASE_FALHAS` da base vazia e `BASE_LINT=20/162`, rotas
   `/home /poli-chat /legal-poli-chat`, numa cópia do smoke com as portas trocadas para 4690/8790.
3. Prints com e sem *reduced motion* (`page.emulateMedia({ reducedMotion })`); conferir os quatro
   personagens e as reações.
4. Commits planejados, para a revisão do Pietro:
   1. `feat(TS-5406): motor de pixel art dos mascotes em shared/ui`
   2. `feat(TS-5406): componente app-mascot e serviço de preferências`
   3. `feat(TS-5406): troca de mascote e animação, com exemplo na vitrine`
   4. `refact(TS-5406): POLI dentro do shell, sem cabeçalho próprio`
   5. `feat(TS-5406): chat vazio com frase e mascote sobre a barra da POLI`
   6. `feat(TS-5406): mascote reage ao chat da POLI`
   7. `feat(TS-5406): mascote na Home no lugar do vídeo do robô`
   8. `chore(TS-5406): remove vídeo e ícone do robô da POLI`
