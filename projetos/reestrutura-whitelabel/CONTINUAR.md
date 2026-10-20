# Continuar em outro chat (19/10)

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
| 28 | front | `~/repos/apl-credit-whitelabel-wt/28` | `feature/TS-5406-poli-mascote` | `6303b2e5` | **em andamento no chat da 28** (POLI no portal e mascotes; spec e plano em `tarefas/28-*`; portas 4600–4699) |

As worktrees 26 e 27 do front usam o `node_modules` da 25 (link). O README diz quando a R59 e a 27
forem commitadas e publicadas.

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
