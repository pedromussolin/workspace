# Reestrutura Whitelabel — Planejamento

Pasta de trabalho do épico **[FRONT] Reestrutura whitelabel** (apl-credit-whitelabel).
Cada tarefa tem um arquivo com escopo, inventário, critérios de aceite e
validação. A ideia é revisar o desenho **antes** de abrir cada branch.

> **Chat novo?** Comece por [CONTINUAR.md](CONTINUAR.md): onde está cada branch, o que outro chat
> ainda está fazendo e como trabalhar ao mesmo tempo.

- Pedido de 10/10/2026 (Pietro Nett).
- Objetivo:
  - os temas de marca valem em todas as páginas;
  - existe dark mode;
  - o portal não usa mais Angular Material, só componentes próprios;
  - o repositório fica pronto para desenvolver com IA (pasta `.ai`, tarefa
    17);
  - a arquitetura segue `core/`, `shared/`, `layouts/` e `features/`, sem
    mudar o comportamento das telas.
- Referência visual: as páginas de **Pré-Trade** e de **Lotes de
  Liquidação**. Vale o design, não necessariamente o código.

## Como ler esta pasta

| Arquivo | Para que serve |
|---|---|
| [decisoes.md](decisoes.md) | Decisões tomadas e pendentes, com quem decide |
| [arquitetura-alvo.md](arquitetura-alvo.md) | Estrutura de pastas, regras de dependência, rotas e integração com o BFF |
| [achados.md](achados.md) | Defeitos e código morto encontrados no caminho, fora do objetivo do épico |
| [design-system.md](design-system.md) | Tokens de cor, temas claro/escuro, componentes próprios e ícones |
| `tarefas/` | Uma tarefa por arquivo (lista abaixo) e o [roteiro comum das áreas](tarefas/roteiro-de-area.md) |
| `evidencias/` | Baseline de build, lint e testes (10/10) e a regressão visual da 01. A validação de cada fatia seguinte fica na seção "O que foi feito" da tarefa |
| `anexos/icones/` | Fonte dos ícones SVG próprios, o mapa Material → novo e o script que gera a página de revisão |

Proposta dos ícones para revisão: https://claude.ai/artifact/Hi6hgNKrGGRgofWWHh3Dds
Prévia das telas (marcas, claro/escuro, celular): https://claude.ai/artifact/5rUQj8R3zYrg3Zry4U9Bod (fonte em `anexos/previa/`, `node build.mjs`)

As referências de código (`arquivo:linha`) e o inventário apontam para o
commit `d0bc3de`, que era o origin/master do apl-credit-whitelabel em
10/10/2026.

## Tarefas

| # | Tarefa | Branch | Depende de | Status | TS |
|---|---|---|---|---|---|
| 01 | [Estrutura base](tarefas/01-estrutura-base.md) | `refact/TS-5358-estrutura-base-front` | — | **publicada** (15/10) | TS-5358 |
| 02 | [Temas claro e escuro](tarefas/02-temas-claro-escuro.md) | `feature/TS-5359-temas-claro-escuro` | 01 | **publicada** (15/10) | TS-5359 |
| 03 | [Componentes: ícones, botões e formulário](tarefas/03-componentes-formulario.md) | `feature/TS-5360-componentes-formulario` | 02 | **publicada** (15/10) | TS-5360 |
| 04 | [Componentes: overlay, tabela e shell novo](tarefas/04-componentes-overlay-tabela.md) | `feature/TS-5361-componentes-overlay-tabela` | 03 | **publicada** (15/10; de novo em 19/10) | TS-5361 |
| 05 | [Pré-Trade](tarefas/05-pre-trade.md) | `refact/TS-5362-pre-trade-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5362 |
| 06 | [Lotes, cessão e detalhe do contrato](tarefas/06-lotes.md) | `refact/TS-5363-lotes-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5363 |
| 07 | [Report Transfer](tarefas/07-report-transfer.md) | `refact/TS-5364-report-transfer-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5364 |
| 08 | [Formalização](tarefas/08-formalizacao.md) | `refact/TS-5365-formalizacao-nova-arquitetura` | 04 | **publicada** (15/10; de novo em 19/10) | TS-5365 |
| 09 | [Controladoria e gestão](tarefas/09-controladoria.md) | `refact/TS-5366-controladoria-nova-arquitetura` | 04 | **publicada** (19/10) | TS-5366 |
| 10 | [Orquestrador](tarefas/10-orquestrador.md) | `refact/TS-5367-orquestrador-nova-arquitetura` | 04 | **publicada** (19/10) | TS-5367 |
| 11 | [Onboarding, usuários, clientes e simulação](tarefas/11-onboarding-usuarios.md) | `refact/TS-5368-onboarding-usuarios-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5368 |
| 12 | [Páginas gerais](tarefas/12-paginas-gerais.md) | `refact/TS-5369-paginas-gerais-nova-arquitetura` | 04 | **publicada** (19/10) | TS-5369 |
| 13 | [Remove Angular Material](tarefas/13-remove-angular-material.md) | `chore/TS-5370-remove-angular-material` | 01–12, 14, 15 | **publicada** (19/10) | TS-5370 |
| 14 | [Docs da API autenticada](tarefas/14-docs-api.md) | `feature/TS-5371-docs-api-autenticada` (front e BFF) | 04 | **publicada** (19/10) | TS-5371 |
| 15 | [Vitrine do design system](tarefas/15-vitrine-design-system.md) | `feature/TS-5372-vitrine-design-system` (front e BFF) | 04 | **publicada** (19/10) | TS-5372 |
| 16 | [E2E, cobertura e regressão visual](tarefas/16-testes-e2e-cobertura.md) | `test/TS-?-e2e-cobertura-regressao-visual` | 01 | **adiada** (Pietro faz depois, com o time de infraestrutura) | — |
| 17 | [Pasta `.ai`: desenvolver com IA](tarefas/17-pasta-ai.md) | `chore/TS-5389-pasta-ai` | 13 | **publicada** (19/10); aceite cumprido | TS-5389 |
| 20 | [Devcontainer do front mais leve](tarefas/20-devcontainer.md) | `chore/TS-5387-devcontainer` | `master` (independente do épico) | **publicada** (19/10) | TS-5387 |
| 19 | [Controle de acesso pelo portal](tarefas/19-controle-de-acesso.md) | `feature/TS-5390-controle-de-acesso` (front e BFF) | 13 / `origin/master` | **publicada** (19/10) | TS-5390 |
| 18 | [Segurança do front](tarefas/18-seguranca.md) | `fix/TS-5386-seguranca-front` | `master` (independente do épico) | **publicada** (19/10) | TS-5386 |
| 21 | [Permissões por ação](tarefas/21-permissoes-por-acao.md) | `feature/TS-5391-permissoes-por-acao` (front e BFF) e `fix/TS-5391-brechas-de-permissao` (BFF) | 19 / `origin/master` | **publicada** (19/10) | TS-5391 |
| 22 | [Observabilidade e logs](tarefas/22-observabilidade-logs.md) | `feature/TS-5392-observabilidade` (BFF e front) | 17 + 18 / `origin/master` | **publicada** (19/10) | TS-5392 |
| 23 | [Ilustrações próprias](tarefas/23-ilustracoes.md) | `feature/TS-5393-ilustracoes` | 13 | **publicada** (19/10) | TS-5393 |
| 25 | [Refinamento visual e de design](tarefas/25-refinamento-visual.md) | `refact/TS-5395-refinamento-visual` | `release/20261016` | **publicada** (20/10): rodada 1 (26 commits), revisão de 19/10 (R51–R58), R59, o ajuste dos testes do seletor, a R60 (home nova), a R61 (teste local) e a R62 (revisão da prévia); ponta `b8a02a7f` | TS-5395 |
| 26 | [Controle de acesso: organização e UX/UI](tarefas/26-controle-de-acesso-ux.md) | `feature/TS-5405-controle-de-acesso-ux` (front e BFF) | 25 (front) / `release/20261016` (BFF) | **publicada** (19/10): 2 commits no front, 3 no BFF | TS-5405 |
| 27 | [Organização e cliente da pessoa no controle de acesso](tarefas/27-organizacao-e-cliente.md) | `feature/TS-5407-organizacao-e-cliente` (front e BFF) | 26 | **publicada** (20/10): 2 commits no BFF, 2 no front, mais os merges | TS-5407 |
| 28 | [POLI dentro do portal, com mascotes animados](tarefas/28-poli-mascote.md) | `feature/TS-5406-poli-mascote` | 26 | **publicada** (20/10): 8 commits, ponta `91b75672` | TS-5406 |
| 29 | [Segurança e alinhamento com a infraestrutura](tarefas/29-seguranca-infra.md) | `fix/TS-5411-seguranca-bff` e `fix/TS-5411-seguranca-front` | `master` (e a 27, para o que só existe no épico) | **publicada** (20/10): leva do deploy; escopo do parceiro (D99), TSE e cessão em andamento | TS-5411 |
| 30 | [Nomes e docstrings dos testes do BFF em inglês](tarefas/30-testes-do-bff-em-ingles.md) | a criar | `master`, depois do deploy de 21/10 | **aberta** (21/10) | a criar |
| 31 | [Ajustes visuais e padrões de design](tarefas/31-ajustes-visuais-e-padroes.md) | `feature/TS-5424-ajustes-visuais-e-padroes` (PR 1), `feature/TS-5427-funil-e-cards-orquestrador` (PR 5), `feature/TS-5425-organizacao-e-grupos` (PR 2) | `master` | **em andamento** (23/10): PR 1 e PR 5 commitadas (locais); PR 2 implementada; revisão e smoke pendentes | TS-5424, TS-5427, TS-5425 |
| 32 | [Enviar agora escolhendo os subfluxos](tarefas/32-envio-por-subfluxo.md) (PR 4 da 31) | `feature/TS-5416-envio-por-subfluxo` | `master`; front sobre a PR 1 | **implementada localmente; revisão e smoke pendentes** (23/10) | TS-5416 |
| 33 | ["Ver como" outra pessoa](tarefas/33-ver-como.md) (PR 3 da 31) | `feature/TS-5426-ver-como` | PR 2 | **implementada localmente; revisão e smoke pendentes** (23/10) | TS-5426 |
| 34 | [Renovação dos tokens do Azure derruba a sessão](tarefas/34-renovacao-tokens-azure.md) | `fix/TS-5429-renovacao-tokens-azure` (front e BFF) | `master`; entra na `release/20261026` | **publicada** (26/10): na `release/20261026` e na `-sdbx`, PRs atualizadas | TS-5429 |
| 35 | [Permissões atômicas, perfis por página e migração manual dos grupos](tarefas/35-permissoes-atomicas-e-migracao-dos-grupos.md) | a criar | depois da release 20261026 | **aberta** (26/10): migração manual (D128), grupos amarrados no código levantados; falta o levantamento das telas | TS-5431 |
| 24 | [Deploy da reestruturação](tarefas/24-deploy.md) | `release/AAAAMMDD` (front e BFF) | todas | **em produção** (21/10, 19:29): front `prod-f7bb2d8`, BFF `prod-bb877db`; falta a conferência (7.4) e o pós-deploy (8) | TS-5394 |

## Situação em 16/10

**Prontas: 22 de 23** (a 16 está adiada e fica fora da conta). Falta a 24,
o deploy, que é a última.
- **Publicadas em 15/10:** 01 a 08 e 11, sem merge em nenhum ambiente.
- **Publicadas em 19/10:** 09, 10, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22,
  23 e a rodada 1 da 25, e de novo a 04 e a 08 com os commits novos. A 14, a
  15, a 19, a 21, a 22 e a 25 têm branch no front e no BFF; a 21 tem ainda o
  fix das brechas, só no BFF. Nenhuma em ambiente: as `release/20261016` e as
  `backup/*` e `wip/*` ficaram locais.

Cada tarefa tem a seção "O que foi feito", com os commits, as mudanças
visíveis para a PR e a validação.

| # | Branch | Nasce de | Commits | Situação |
|---|---|---|---|---|
| 01 | `refact/TS-5358-estrutura-base-front` | `master` (`3f5ea96`) | 13 | publicada |
| 02 | `feature/TS-5359-temas-claro-escuro` | 01 | 5 | publicada |
| 03 | `feature/TS-5360-componentes-formulario` | 02 | 22 | publicada |
| 04 | `feature/TS-5361-componentes-overlay-tabela` | 03 | 31 | publicada (de novo em 19/10, com o `e031e31`) |
| 05 | `refact/TS-5362-pre-trade-nova-arquitetura` | 04 | 15 | publicada |
| 06 | `refact/TS-5363-lotes-nova-arquitetura` | 04 | 18 | publicada |
| 07 | `refact/TS-5364-report-transfer-nova-arquitetura` | 04 corrigida | 14 | publicada |
| 08 | `refact/TS-5365-formalizacao-nova-arquitetura` | 04 corrigida | 7 + 3 | publicada (de novo em 19/10) |
| 11 | `refact/TS-5368-onboarding-usuarios-nova-arquitetura` | 04 corrigida | 24 | publicada |
| 09 | `refact/TS-5366-controladoria-nova-arquitetura` | 04 corrigida | 34 | publicada (19/10) |
| 10 | `refact/TS-5367-orquestrador-nova-arquitetura` | 04 corrigida | 18 | publicada (19/10). Conflito conhecido com a 11 (3 imports) |
| 12 | `refact/TS-5369-paginas-gerais-nova-arquitetura` | 04 corrigida | 24 | publicada (19/10) |
| 14 | `feature/TS-5371-docs-api-autenticada` (front e BFF) | 04 corrigida / `origin/master` | 18 + 3 | publicada (19/10) |
| 15 | `feature/TS-5372-vitrine-design-system` (front e BFF) | 04 corrigida / `origin/master` | 31 + 1 | publicada (19/10) |
| 13 | `chore/TS-5370-remove-angular-material` | 04 + merge de todas as áreas | 90 + merges | publicada (19/10) |
| 18 | `fix/TS-5386-seguranca-front` | `origin/master` (`576957c`) | 6 | publicada (19/10) |
| 20 | `chore/TS-5387-devcontainer` | `origin/master` (`576957c`) | 10 | publicada (19/10) |
| 17 | `chore/TS-5389-pasta-ai` | 13 (`4bd8380f`) | 35 + 2 merges da 13 | publicada (19/10) |
| 19 | `feature/TS-5390-controle-de-acesso` (front e BFF) | 13 (`4bd8380f`) / `origin/master` (`946dce3`) | 16 + merge da 17 / 6 | publicada (19/10) |
| 21 | `feature/TS-5391-permissoes-por-acao` (front e BFF) | 19 / 19 do BFF | 18 / 15 | publicada (19/10) |
| 21 | `fix/TS-5391-brechas-de-permissao` (só BFF) | `origin/master` (`946dce3`) | 5 | publicada (19/10) |
| 22 | `feature/TS-5392-observabilidade` (front e BFF) | 17 + merge da 18 (`0ea7a527`) / `origin/master` (`946dce3`) | 13 / 18 | publicada (19/10) |
| 23 | `feature/TS-5393-ilustracoes` | 13 (`fd987f8c`) | 10 + 2 merges da 13 | publicada (19/10) |
| 25 | `refact/TS-5395-refinamento-visual` (front) e `refact/TS-5395-opcoes-na-docs-da-api` (BFF) | `release/20261016` / `origin/master` | 34 / 4 | publicada (19/10) |

**Ordem para abrir as PRs na `sandbox`:**
1. 01 → 02 → 03 → 04.
2. As áreas (05 a 12, 14 e 15), em qualquer ordem. Na 11 depois da 10,
   aplicar a resolução da tarefa 10.
3. A 13.
4. A 17, a 23 e a 19, nessa ordem; depois a 21, que nasce da 19.
5. A 18 e a 20 podem ir a qualquer momento. A 22 vai depois da 17 e da 18.
6. No BFF: o fix das brechas da 21, a 14, a 15 e a 22 em qualquer ordem; a
   19 e depois a 21.

Quem entrar depois resolve os conflitos como os scripts em
`$PRIV/resolucoes/` (os da 18, da 20 e da 22). O passo a passo da 18 está
na tarefa 18.

**Junção completa do front** (19 com a 17 e a 13, mais 23, 18, 20, 21 e 22,
numa worktree descartável, em 16/10):
- a 23 e a 21 entram limpas. A 18 conflita em 10 arquivos, a 20 em 6 e a 22
  em 4 (`package.json`, lock, `entrypoint.sh` e o spec do erro). Os scripts
  resolvem tudo sozinhos;
- resultado:
  - `npm ci` ok, `tsc` 0/0, `check-patterns` limpo e `npm audit
    --omit=dev` com 0 falhas;
  - os 34 commits da 21 e da 22 compilam sozinhos sobre a junção;
  - build ok, bundle inicial de 430 kB (121 kB na rede);
  - lint 20/163, igual à base;
  - 2.213 testes, todos passando;
  - smoke de 9 rotas no claro (desktop e celular), no escuro e na Dots, sem
    erro.

**Faltam: a 25 (refinamento visual, em rodadas com o Pietro) e a 24
(deploy), nessa ordem.**
- **Atualizar com a master:** todas as branches, no front e no BFF.
- **Variáveis:**
  - BFF: `CFG_PERMISSIONS_LEGACY_ROLES` e
    `CFG_ACCESS_CONTROL_GROUP_ASSIGNMENT_ENABLED`;
  - front: `ENVIRONMENT` e as do Datadog (lista na 22).
  - Pelos scripts de Parameter Store, só depois do wrapper e do hook que
    escondem os valores (D41, D42).
- **Azure:**
  - permissões do Graph e consentimento de admin;
  - o service principal como dono do app (D18 revista);
  - as app roles novas: `api-docs:read`, `design-system:read` e
    `access-control:read`/`write`. As da 21 são criadas pela migração;
  - normalizar roles e grupos pela tela da 19 (D43).
- **Datadog:** criar a aplicação de RUM; facets, monitores e dashboard
  (listas na 22).
- **Release:** `release/AAAAMMDD`, primeiro na sandbox e depois em produção,
  com GMUD (D40).

**Pendências do Pietro:**
- abrir as PRs (as branches estão publicadas desde 19/10);
- **decisões:**
  - **D56:** como migrar os `admin:*`;
  - **D57:** o logo do login;
  - **A31:** confirmar com a infraestrutura se o host do BFF é público;
- confirmar com a infraestrutura o HSTS do gateway antes de ligá-lo (18) e
  a anotação `source:nginx` no argocd (22).

**Depois de um ciclo na sandbox:**
- **Graph real:** testar a tela da 19. Nada rodou contra ele ainda; é o
  maior risco.
- **CSP:** trocar de report-only para valendo, se não houver violação.
- **Transição das permissões:** desligar a `CFG_PERMISSIONS_LEGACY_ROLES`
  e apagar as roles antigas pela tela da 19. Quem tem `whitelists:create`
  sem `whitelists:update` fica mais restrito no front desde já (21).

**Adiada:** a 16 e a D9, que o Pietro faz depois com o time de
infraestrutura. **Fora do épico:** a A29 (injeção no apl-ai-service).

## Ordem e branches

```
master ── 01 ── 02 ── 03 ── 04 ──┬── 05 Pré-Trade
                                  ├── 06 Lotes
                                  ├── 07 Report Transfer
                                  ├── 08 Formalização
                                  ├── 09 Controladoria
                                  ├── 10 Orquestrador
                                  ├── 11 Onboarding/usuários
                                  └── 12 Páginas gerais ──→ 13 Remove Material
```

- **Branches empilhadas:** enquanto a PR anterior não entra na master, a
  branch seguinte nasce da anterior. Depois do merge, a branch seguinte é
  rebaseada na master.
- As tarefas 05 a 12 são independentes entre si. Podem andar em paralelo
  depois da 04.
- Em cada área, o primeiro commit **só move arquivos**, para o git reconhecer
  a mudança como renomeação. Os commits de estilo e de refatoração vêm depois.
- Eu faço os commits sem push. Ao fim de cada fatia, entrego a lista exata de
  branches para o Pietro publicar e abrir as PRs.
- **`-sdbx`**: só se criar quando o merge na `sandbox` der conflito.
- **Caminho até a master** (combinado em 15/10):
  - tudo o que o épico planeja entra primeiro na `sandbox`;
  - o que chegar na `master` nesse meio-tempo vem junto, já refatorado no
    padrão novo;
  - no fim, a `sandbox` vai inteira para a `master`.
- **Publicação de 15/10:**
  - as branches 01 a 06 foram rebaseadas na `master` (`3f5ea96`, PR #220:
    status `pendente_cerys`/`pendente_poliedro` da formalização) e
    publicadas;
  - a tarefa 08 precisa levar esses status novos para a tela refatorada.
- **Requisitos que valem para todas:**
  - tudo responsivo, até ~400 px;
  - Chrome, Edge e Safari;
  - APIs modernas do Angular, nada depreciado;
  - spec de comportamento em todo componente novo ou mexido.
- O **botão de dark mode** fica escondido até a 13. Sem isso, a produção
  mostraria telas meio claras e meio escuras durante a migração.

## Rodar local com dados fictícios

Abre qualquer worktree do front (ou a junção) com um BFF falso, que tem
todas as telas liberadas e os dados de `$PRIV/smoke-dados/`. As ações não
gravam nada:

```bash
~/repos/whitelabel-workspace/anexos/scripts/portal-local.sh ~/repos/.reestrutura_whitelabel/junta-front
```

- Abra http://localhost:4300. No Windows, também funciona pelo WSL.
- `BUILD=1` refaz o build antes; sem build, o script faz um.
- O segundo argumento troca os dados (padrão: `todas-acesso-21.json`). O
  padrão já tem dados para o controle de acesso, os Lotes de Liquidação (lotes
  fake e reais em vários status, detalhe com pagamentos e saldo) e o
  Pré-Trade (uma solicitação por etapa, com aprovações, histórico e anexos).
  Os geradores ficam em `$PRIV/geradores/`.
- `THEME_KEY=<chave>` troca a marca (chaves no `privado.md`).
- Pare com Ctrl+C.

Serve para ver todas as telas, os temas, o celular, a tela de acesso da 19
e a migração da 21. O BFF não é testado aqui: ele tem os próprios testes
(`pytest`) e é validado na sandbox.

## Rodar local contra o BFF da sandbox

Dados reais, mas o BFF da sandbox é o da master. Com as branches da 19, da
21 e da 22 do front, ficam de fora:
- a tela de acesso, que dá erro;
- os botões que pedem as ações novas (`test`, `run`, `reprocess`,
  `approve`), que somem;
- o `usr.id` do RUM.

Use para as áreas e a 13, ou para a junção sem a 21.


1. Na branch que for testar: `cd apl-credit-whitelabel && npm start` (front
   em http://localhost:4200, chamando a API em http://localhost:8000).
2. Em outro terminal:
   `TARGET=<url-da-sandbox>/api node ~/repos/whitelabel-workspace/anexos/scripts/bff-sandbox-proxy.mjs`.
   A URL real da sandbox está no `privado.md` (fora do repo).
3. Faça login na sandbox (`<url-da-sandbox>`). O Azure só
   devolve o login para a sandbox, por isso a sessão nasce lá.
4. No DevTools da sandbox, em Application → Cookies, copie o valor de
   `session_id`.
5. Abra `http://localhost:8000/__sessao?id=<valor>`. O proxy grava o cookie
   em localhost e abre http://localhost:4200/home.

Cuidados:
- Os dados são os da sandbox, e as ações gravam de verdade lá.
- "Sair" no front local encerra a mesma sessão da aba da sandbox.
- Quando a sessão expira, o front manda para `/login`. Aí é só repetir os
  passos 3 a 5.

## Números de partida (`d0bc3de`)

| Área | Arquivos | Linhas | Cores fixas | `::ng-deep` | Specs |
|---|---|---|---|---|---|
| Base (app, auth, http, tema, layout) | 39 | 2.636 | 112 | 0 | 9 |
| Componentes de formulário | 51 | 3.407 | 106 | 57 | 12 |
| Componentes de overlay/tabela | 63 | 5.753 | 185 | 25 | 15 |
| Pré-Trade | 65 | 14.103 | 583 | 9 | 3 |
| Lotes, cessão, contrato | 45 | 6.913 | 188 | 18 | 12 |
| Report Transfer | 42 | 9.939 | 442 | 6 | 10 |
| Formalização | 6 | 3.013 | 138 | 0 | 2 |
| Controladoria e gestão | 31 | 7.812 | 291 | 6 | 2 |
| Orquestrador | 18 | 6.743 | 382 | 1 | 0 |
| Onboarding, usuários, clientes, simulação | 22 | 4.941 | 191 | 0 | 2 |
| Páginas gerais | 30 | 4.435 | 163 | 6 | 6 |

Como os números foram contados:
- arquivos `.ts`, `.html` e `.scss`, sem os `.spec.ts`;
- "cores fixas" são ocorrências de `#hex` e `rgb(a)(`;
- o Angular Material aparece em 119 arquivos `.ts`.

## Glossário

- **Token (de design):** variável CSS com nome de função, como
  `--surface-card`, no lugar de um valor solto como `#fff`. O tema muda o
  valor, e a tela continua igual no código.
- **Tema de marca:** Poliedro, Dots, Cerys ou Viva. É escolhido por deploy
  (`THEME_KEY`) e define só as cores principais.
- **Esquema de cor:** claro ou escuro. É escolhido pelo usuário ou segue o
  sistema operacional (`prefers-color-scheme`).
- **CDK (`@angular/cdk`):** biblioteca da equipe do Angular sem visual
  nenhum. Ela cuida de comportamento: posicionar popups, prender o foco num
  diálogo, navegação por teclado e arrastar-e-soltar.
- **Feature:** pasta que reúne tudo de uma área de negócio: telas, chamadas
  ao BFF, modelos e estado.
- **Lazy loading:** o código da tela só é baixado quando o usuário entra
  nela.
- **Branch empilhada:** branch criada a partir de outra que ainda não foi
  para a master.
- **`::ng-deep`:** seletor do Angular que fura o encapsulamento de estilo do
  componente. É um sinal de que o componente não oferece o ajuste que a tela
  precisava.
