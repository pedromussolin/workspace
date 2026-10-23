# Continuar em outro chat ou no Codex (23/10)

**Release 20261023 (23/10, noite):** as PRs 1, 5, 2, 4 e 3 foram commitadas nas branches de cada
tarefa e juntadas na `release/20261023` de cada repo, com a cópia `-sdbx` (release + `sandbox`). PRs
abertas, ainda não mergeadas:

| Repo | Para a `master` | Para a `sandbox` | Validação da release |
|---|---|---|---|
| apl-shared-service | #71 | #72 | 609 testes |
| BFF | #222 | #223 | 1968 testes (1970 na `-sdbx`) |
| front | #235 | #236 | `validate.sh` ok, 4758 testes, smoke ok |

Ordem do deploy: shared, BFF e front. Antes do BFF: `CFG_ACCESS_CONTROL_INSTITUTION_GROUPS` no
Parameter Store e a app role `access-control:impersonate`. Nova tarefa aberta: [34](tarefas/34-renovacao-tokens-azure.md)
(TS-5429, fora da release).

**Revisão do Claude sobre a entrega do Codex (23/10, noite):** todas as PRs validadas por inteiro,
sem commit.

| PR | Validação | Correções da revisão |
|---|---|---|
| 1 | front ok (commits locais) | — |
| 5 | front ok, 4654 testes | — |
| 2 | front ok, 4592; BFF 1944 | regra da licença P1 removida (D17 cai): `CFG_ACCESS_CONTROL_GROUP_ASSIGNMENT_ENABLED` e o aviso saem |
| 4 | front ok, 4517; BFF 1796; shared 621 (a falha `modules-viewer-boundaries` já existe na master) | spec com TestBed duplo; rota `POST /report-transfer/flows/{key}/run` só para a interna (escopo de parceiro); um registro "Envios manuais: {fluxo}" por fluxo em vez de um por envio; lista de subfluxos com estilo e "Marcar/Desmarcar todos" |
| 3 | front ok, 4603; BFF 1962 | rotas no teste de escopo; serviço do "ver como" sem consulta a cada 30 s (uma no início e uma na expiração); testes do controle de acesso com o serviço falso; PR 3 remontada sobre a PR 2 final |

Portal local (4300) servindo todas as PRs juntas: build em
`~/repos/.reestrutura_whitelabel/agentes/revisao-codex/integra-dist` (junção por `integra.py`),
dados em `smoke-dados/validacao-integrada.json`.


Retomada no Codex concluída na implementação: PR 2, envio por subfluxo (PR 4)
e "Ver como" (PR 3) preparados localmente. Ajustes finais da PR 5 revisados.
Ver as seções finais das tarefas 31, 32 e 33 e o relatório local
`~/repos/.reestrutura_whitelabel/entrega-codex-23-10.md`.
Sem commits ou publicação; revisão e smoke seguem pendentes.
Documentação na branch `chore/TS-5425-revisao-pr2`.

O limite semanal acabou no meio da tarefa 31. Ponto de partida para quem continuar (Claude ou
Codex): leia o `CLAUDE.md` desta pasta, o `~/repos/CLAUDE.md` (regras de git; o `~/repos/AGENTS.md`
tem o mesmo), o README (tabela de Tarefas), o `decisoes.md` (D108 a D122) e o
`~/repos/.reestrutura_whitelabel/privado.md` (nomes reais).

| PR | TS | Tarefa | Onde | Estado |
|---|---|---|---|---|
| 1 | TS-5424 | [31](tarefas/31-ajustes-visuais-e-padroes.md) | front `~/repos/apl-credit-whitelabel-wt/31`, `feature/TS-5424-ajustes-visuais-e-padroes` | 21 commits locais, aprovados; falta publicar e abrir a PR contra a master |
| 5 | TS-5427 | 31 | front `~/repos/apl-credit-whitelabel-wt/32`, `feature/TS-5427-funil-e-cards-orquestrador` (sobre a PR 1) | 5 commits locais; **em revisão, fora dos commits:** Faixas em px, valor desembolsado em 18 px e centralizado. Falta o ok do Pietro, encaixar nos commits, publicar e abrir a PR contra a branch da PR 1 |
| 2 | TS-5425 | 31 (seção "Andamento") | BFF `~/repos/apl-credit-whitelabel-api-wt/33`; front `~/repos/apl-credit-whitelabel-wt/33` + `agentes/t5425/front-a` e `front-b` | sem commit; ver o passo a passo na tarefa 31 |
| 4 | TS-5416 | [32](tarefas/32-envio-por-subfluxo.md) | shared e BFF `*-wt/32`; front `*-wt/34` | implementada localmente; revisão e smoke pendentes |
| 3 | TS-5426 | [33](tarefas/33-ver-como.md) | BFF `*-wt/34`; front `*-wt/35` | implementada sobre a PR 2; revisão e smoke pendentes |

Ordem sugerida: fechar a PR 2, depois a PR 4, depois a PR 3. Nada se commita nos repos da empresa
sem a revisão do Pietro, e nada se publica sem ele pedir.

---

# Histórico: continuar em outro chat (19/10)

Ponto de partida para um chat novo que vai fazer a última tarefa antes do deploy (24), **enquanto
outro chat termina a R59 e a 27**. Leia isto, o `CLAUDE.md` desta pasta, o README (Tarefas e
Situação), o `decisoes.md` e o `~/repos/.reestrutura_whitelabel/privado.md` (local).

## Onde está cada coisa

Cadeia do front: `release/20261016` → 25 (TS-5395) → 26 (TS-5405) → 27 (TS-5407). No BFF:
`release/20261016` → 26 → 27; o BFF da 25 (`refact/TS-5395-opcoes-na-docs-da-api`) sai da master.

| Tarefa | Repo | Worktree | Branch | Ponta (19/10) | Situação |
|---|---|---|---|---|---|
| 25 | front | `~/repos/apl-credit-whitelabel-wt/25` | `refact/TS-5395-refinamento-visual` | `5a915319` | publicada, com a R59 (marca da sessão) |
| 25 | BFF | `~/repos/apl-credit-whitelabel-api-wt/25` | `refact/TS-5395-opcoes-na-docs-da-api` | `444c9ca` | publicada |
| 26 | front | `~/repos/apl-credit-whitelabel-wt/26` | `feature/TS-5405-controle-de-acesso-ux` | `d62bbc85` | publicada (com a R59, por merge) |
| 26 | BFF | `~/repos/apl-credit-whitelabel-api-wt/26` | `feature/TS-5405-controle-de-acesso-ux` | `0446d9b` | publicada |
| 27 | front | `~/repos/apl-credit-whitelabel-wt/27` | `feature/TS-5407-organizacao-e-cliente` | `3e05c4f6` | publicada (com a 26 e a R59, por merge) |
| 27 | BFF | `~/repos/apl-credit-whitelabel-api-wt/27` | `feature/TS-5407-organizacao-e-cliente` | `fa7c287` | publicada |
| 28 | front | `~/repos/apl-credit-whitelabel-wt/28` | `feature/TS-5406-poli-mascote` | `91b75672` | **publicada (20/10)** (POLI no portal e mascotes; `tarefas/28-*`; portas 4600–4699) |

As worktrees 26 e 27 do front usam o `node_modules` da 25 (link). O README diz quando a R59 e a 27
forem commitadas e publicadas.

**Publicada em 20/10: R60, a home nova** ([tarefas/25-home-parceiros.md](tarefas/25-home-parceiros.md)),
na `refact/TS-5395-refinamento-visual` (`aae6a159`), e por merge na 26 e na 27. A home passa a ser uma só para todos: a saudação no topo, para a
organização interna a **seção da POLI compacta logo abaixo** (não ocupa mais a altura da tela) e,
para todos, o painel do dia (`home-panel/`: cartões por módulo, acesso rápido, recentes).

- `home.page.html` virou: `<app-home-panel>` com a seção da POLI projetada dentro dele (só
  `isPlgn()`). **Revisão de 20/10 (R62), publicada na 25 (`88ba625b`) e por merge na 26 e na 27:** a seção é uma coluna:
  `section.poli-welcome-component` > `h2.poli-prompt` "POLI AI" (no topo, à esquerda),
  `.textbox-stage` com a caixa (centralizada, até 720 px; placeholder "Escreva algo para iniciar um
  chat") e `p.poli-note` centralizado e menor (ícone e "A POLI usa o ChatGPT-5.2 e pode cometer
  erros. Verifique as informações importantes."). Saíram o `.poli-reminder` e o `app-poli-footer`
  (o componente `features/general/home/poli-footer/` foi apagado). **Não há mascote** aqui: no
  merge, a 28 põe o `<app-mascot />` dentro do `.textbox-stage`, com `position: relative` e
  `margin-top: var(--mascot-stage-h)` nele (o mascote anda nesse espaço, acima da caixa); com a
  área larga (`@container home-poli (min-width: 1040px)`, no `:host`), o espaço divide a linha do
  título: `margin-top: calc(var(--mascot-stage-h) - 2.25rem)`. Assim está na prévia.
- `home.page.ts` já não tem o vídeo do robô (como na 28) nem a saudação da POLI.
- `home.page.scss` foi reescrito para a seção compacta (cartão com a caixa centralizada).
- Também toca: `layouts/app-shell/app-shell.component.ts` (uma linha no `NavigationEnd`),
  `core/navigation/`, `eslint.config.js`, `shared/ui/detail-list` (opção `emphasis`),
  `shared/utils/module-summary.ts` e os `home-summary/` de Lotes de Liquidação, Lotes de Cessão e
  Formalização. A 28 recebe tudo por merge da `refact/TS-5395-refinamento-visual`.

**Prévia junta (20/10):** `~/repos/apl-credit-whitelabel-wt/previa` (sem branch; um commit local solto) = a 27 com o **merge da `feature/TS-5406-poli-mascote` (`91b75672`)** e a home compacta com o mascote: no `.textbox-stage`, `<app-mascot [floor]="mascotFloor()" />` e `(topSpanChange)="mascotFloor.set($event)"` na caixa. Sem essa ligação, o clique no mascote não faz nada (o `click()` só escolhe ação que cabe no chão). É só para o Pietro ver o resultado; pode ser apagada (`git worktree remove`). O portal local está servindo ela.

**Mascotes com cor fixa (D90, 20/10):** commitado e publicado na 28 (`c12173fb`, `fix(TS-5406): mascotes com cor fixa, sem a cor da marca`). O patch (código da empresa, fora deste repo) está em `~/repos/.reestrutura_whitelabel/patches/mascotes-cor-fixa.patch` e aplica limpo na `91b75672`: muda `mascot-palettes.ts`, tira `BRAND_COLOR` e `brandMix` do `mascot-render.ts` e troca os dois testes que esperavam a cor da marca (`mascot-engine.spec.ts` e `mascot.component.spec.ts`). Commit sugerido na 28: `fix(TS-5406): mascotes com cor fixa, sem a cor da marca`.

## Junção da 28 com a home nova da 25 (R59)

A 28 (`feature/TS-5406-poli-mascote`, publicada em 20/10) e a home nova da 25 (R59, no outro chat)
andam juntas: o Pietro vai trazer a 28 para a 25 depois, por **merge**. Arquivos em comum, com
conflito esperado:

- `features/general/home/home.page.*`:
  - a 28 tira o vídeo do robô e a saudação;
  - põe a frase "Escreva algo para iniciar um chat" e o `<app-mascot [floor]>` sobre a caixa, com
    o `(topSpanChange)` da caixa;
  - a 25 refaz a home e apaga o `poli-footer`.
  - Na junção, manter a home da 25 e encaixar nela o mascote, o chão e a frase da 28.
- `layouts/app-shell/app-shell.component.*`:
  - a 28 só acrescenta o `data.shellContent: 'full'` (classes `shell__main--full` e
    `shell__content--full`), para a POLI ocupar a tela dentro do shell.
- O que a Home precisa da 28 está em `shared/ui/mascot/` e em `shared/ui/textbox` (`topSpanChange`):
  arquivos novos ou só da 28, sem conflito.

## Como trabalhar ao mesmo tempo

- **Não mexa** nas worktrees 25 e 27 (front e BFF) nem nessas branches enquanto o outro chat estiver
  nelas. Crie a sua: `git -C ~/repos/apl-credit-whitelabel-wt/26 worktree add --no-track -b
  <tipo>/TS-<id>-<nome> ~/repos/apl-credit-whitelabel-wt/28 <base>` e o link do `node_modules`.
- **Base da tarefa nova:**
  - mexe no controle de acesso ou depende da 27: saia da `feature/TS-5405-controle-de-acesso-ux` e,
    quando a 27 for publicada, faça merge da `feature/TS-5407-organizacao-e-cliente` na sua;
  - o resto do front: saia da `feature/TS-5405-controle-de-acesso-ux` (já tem toda a 25) e, quando a
    R59 for publicada, faça merge da `refact/TS-5395-refinamento-visual`.
  - Branch publicada recebe o que veio de baixo por **merge**, nunca por rebase com force push.
- **Portas:** 4300 e 8765 são do portal local do Pietro (servindo a worktree 27, que tem tudo: 25, R59, 26 e 27). O outro chat
  usa 4510–4599 nos agentes e 4591/8791 no smoke. Use 4600–4699 e, no smoke, uma cópia com as
  portas trocadas: `sed 's/4300/46XX/g; s/8765/87XX/g' anexos/scripts/smoke.mjs > <cópia>`.
- **Máquina:** comando pesado (`ng build`, `ng test`, `ng lint`, Playwright) passa pelo
  `~/repos/.reestrutura_whitelabel/ng-slot.sh`, que deixa dois de cada vez entre todos os chats.

## Ferramentas

- **Validar:** `anexos/scripts/validar-leva.sh <worktree> [rotas]` com `BASE=<ponta da base>`,
  `BASE_FALHAS=$HOME/repos/.reestrutura_whitelabel/base-vazia-falhas.txt` e `BASE_LINT=20/162`.
  Confere commits (72 caracteres, sem `Co-Authored-By`, cada um compilando sozinho), build, lint,
  testes e smoke (o smoke usa 4300/8765: com o portal no ar, rode a cópia em outras portas).
- **Portal local:** `anexos/scripts/portal-local.sh <worktree>` (`BUILD=1` refaz o build). Em
  http://localhost:4300/__marcas escolhe a marca e a visão (parceiro ou interna).
- **Agentes:** até cinco, com pastas separadas e um brief como `anexos/agentes/brief-acesso.md`;
  rascunho em `~/repos/.reestrutura_whitelabel/agentes/<parte>/`, nunca em `/tmp`. Atenção: o
  `ng test --include` compila todos os specs da worktree, então dois agentes na mesma worktree
  derrubam um ao outro se um deixar spec quebrado.
- **Dados fictícios:** `~/repos/.reestrutura_whitelabel/smoke-dados/todas-acesso-21.json` (o portal
  local relê quando o arquivo muda).

## Regras que valem sempre

- Commit em PT-BR, `tipo(TS-id): mensagem` com até 72 caracteres, sem `Co-Authored-By`; nunca na
  master; pull antes de mexer numa branch.
- Repos da empresa: implementa e testa; **commit só depois da revisão do Pietro**. Push só de
  `feature/*`, `refact/*` e `fix/*` (o CI só faz build e testes nelas); nunca em master, staging,
  sandbox ou `release/*` (essas publicam imagem).
- Este repo é pessoal: nomes mascarados (Poliedro, Dots, Cerys, Viva), sem segredo, URL interna, log
  ou código da empresa; pull, commit e push na `main` a cada iteração.

## Em aberto (não é da tarefa nova)

- **24 (deploy):** `BRAND_SWITCHER` nos values de sandbox e staging, a decisão sobre `PRODUCTION`, e
  os pedidos à infraestrutura das 26 e 27 (mensagem enviada em 19/10; respostas pendentes).
- **27:** respostas da infraestrutura sobre os atributos de organização e cliente.
- Limpeza do histórico deste repo (nomes reais nos commits `383dd9c` e `b7ea70c`): oferecida, sem
  resposta.
