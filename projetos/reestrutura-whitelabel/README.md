# Reestrutura Whitelabel — Planejamento

Pasta de trabalho do épico **[FRONT] Reestrutura whitelabel** (apl-credit-whitelabel).
Cada tarefa tem um arquivo com escopo, inventário, critérios de aceite e
validação. A ideia é revisar o desenho **antes** de abrir cada branch.

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
| 01 | [Estrutura base](tarefas/01-estrutura-base.md) | `refact/TS-5358-estrutura-base-front` | — | **commits feitos, sem push** (10/10) | TS-5358 |
| 02 | [Temas claro e escuro](tarefas/02-temas-claro-escuro.md) | `feature/TS-5359-temas-claro-escuro` | 01 | **commits feitos, sem push** (10/10) | TS-5359 |
| 03 | [Componentes: ícones, botões e formulário](tarefas/03-componentes-formulario.md) | `feature/TS-5360-componentes-formulario` | 02 | **commits feitos, sem push** (11/10) | TS-5360 |
| 04 | [Componentes: overlay, tabela e shell novo](tarefas/04-componentes-overlay-tabela.md) | `feature/TS-5361-componentes-overlay-tabela` | 03 | **commits feitos, sem push** (11/10) | TS-5361 |
| 05 | [Pré-Trade](tarefas/05-pre-trade.md) | `refact/TS-5362-pre-trade-nova-arquitetura` | 04 | **commits feitos, sem push** (13/10) | TS-5362 |
| 06 | [Lotes, cessão e detalhe do contrato](tarefas/06-lotes.md) | `refact/TS-5363-lotes-nova-arquitetura` | 04 | **commits feitos, sem push** (13/10) | TS-5363 |
| 07 | [Report Transfer](tarefas/07-report-transfer.md) | `refact/TS-5364-report-transfer-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5364 |
| 08 | [Formalização](tarefas/08-formalizacao.md) | `refact/TS-5365-formalizacao-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5365 |
| 09 | [Controladoria e gestão](tarefas/09-controladoria.md) | `refact/TS-5366-controladoria-nova-arquitetura` | 04 | **commits feitos, sem push** (15/10) | TS-5366 |
| 10 | [Orquestrador](tarefas/10-orquestrador.md) | `refact/TS-5367-orquestrador-nova-arquitetura` | 04 | **commits feitos, sem push** (15/10) | TS-5367 |
| 11 | [Onboarding, usuários, clientes e simulação](tarefas/11-onboarding-usuarios.md) | `refact/TS-5368-onboarding-usuarios-nova-arquitetura` | 04 | **publicada** (15/10) | TS-5368 |
| 12 | [Páginas gerais](tarefas/12-paginas-gerais.md) | `refact/TS-5369-paginas-gerais-nova-arquitetura` | 04 | **commits feitos, sem push** (15/10) | TS-5369 |
| 13 | [Remove Angular Material](tarefas/13-remove-angular-material.md) | `chore/TS-5370-remove-angular-material` | 01–12, 14, 15 | **commits feitos, sem push** (16/10) | TS-5370 |
| 14 | [Docs da API autenticada](tarefas/14-docs-api.md) | `feature/TS-5371-docs-api-autenticada` (front e BFF) | 04 | **commits feitos, sem push** (15/10) | TS-5371 |
| 15 | [Vitrine do design system](tarefas/15-vitrine-design-system.md) | `feature/TS-5372-vitrine-design-system` (front e BFF) | 04 | **commits feitos, sem push** (15/10) | TS-5372 |
| 16 | [E2E, cobertura e regressão visual](tarefas/16-testes-e2e-cobertura.md) | `test/TS-?-e2e-cobertura-regressao-visual` | 01 | **adiada** (Pietro faz depois, com o time de infraestrutura) | — |
| 17 | [Pasta `.ai`: desenvolver com IA](tarefas/17-pasta-ai.md) | `chore/TS-5389-pasta-ai` | 13 | **commits feitos, sem push** (16/10); aceite cumprido | TS-5389 |
| 20 | [Devcontainer do front mais leve](tarefas/20-devcontainer.md) | `chore/TS-5387-devcontainer` | `master` (independente do épico) | **commits feitos, sem push** (15/10) | TS-5387 |
| 19 | [Controle de acesso pelo portal](tarefas/19-controle-de-acesso.md) | `feature/TS-5390-controle-de-acesso` (front e BFF) | 13 / `origin/master` | **em andamento** (6ª leva) | TS-5390 |
| 18 | [Segurança do front](tarefas/18-seguranca.md) | `fix/TS-5386-seguranca-front` | `master` (independente do épico) | **commits feitos, sem push** (15/10) | TS-5386 |
| 21 | [Permissões por ação](tarefas/21-permissoes-por-acao.md) | `feature/TS-5391-permissoes-por-acao` (front e BFF) | 19 | a iniciar (D27–D33 decididas) | TS-5391 |
| 22 | [Observabilidade e logs](tarefas/22-observabilidade-logs.md) | `feature/TS-5392-observabilidade` (BFF e front) | 13 / `origin/master` | a iniciar (D34–D39 decididas) | TS-5392 |
| 23 | [Ilustrações próprias](tarefas/23-ilustracoes.md) | `feature/TS-5393-ilustracoes` | 13 | a iniciar (direção A; D44–D46 decididas) | TS-5393 |
| 24 | [Deploy da reestruturação](tarefas/24-deploy.md) | `release/AAAAMMDD` (front e BFF) | todas | a iniciar depois das outras (D40–D43 decididas). É a última | TS-5394 |

## Situação em 16/10

**Prontas: 17 de 19** (a 16 está adiada e fica fora da conta). Faltam a 17
e a 19.
- **Publicadas em 15/10:** 01 a 08 e 11, sem merge em nenhum ambiente.
- **Commits feitos, sem push:** 09, 10 e 12 (3ª leva), 14 e 15 (4ª leva,
  front e BFF), e 13, 18 e 20 (5ª leva).
- **Branches publicadas que ganharam commits:** a 04 (`e031e31`, contraste)
  e a 08 (merge da master e porte da responsividade, 3 commits).
- **A 13 já junta tudo:** ela nasce do merge de todas as áreas (05 a 12, 14
  e 15) sobre a 04. Por isso entra na `sandbox` por último.
- **Junção da 6ª leva** (19 com a 17 e a 13, mais 23, 18 e 20, numa
  worktree descartável, em 16/10):
  - a 23 entra limpa; a 18 conflita em 10 arquivos e a 20 em 6;
  - os scripts `$PRIV/resolucoes/fix_TS-5386-seguranca-front.sh` e
    `chore_TS-5387-devcontainer.sh` resolvem tudo sozinhos. O da 18 também
    tira o spec do erro da lista de legado do `check-patterns`;
  - resultado:
    - `npm ci` ok, `tsc` 0/0, `check-patterns` limpo e `npm audit
      --omit=dev` com 0 falhas;
    - build ok, com bundle inicial de 423 kB (118 kB na rede);
    - lint 20/163, igual à base;
    - 2.083 testes, todos passando;
    - smoke de 8 rotas no claro (desktop e celular), no escuro e na Dots,
      sem erro;
  - o `validar-leva.sh` marca "commits que não compilam sozinhos" nos
    commits da 18 e da 20: eles nascem da master, na estrutura antiga, e não
    compilam sobre as dependências do épico. Foram validados nas próprias
    branches.

Cada tarefa tem a seção "O que foi feito", com os commits, as mudanças
visíveis para a PR e a validação.

| # | Branch | Nasce de | Commits | Situação |
|---|---|---|---|---|
| 01 | `refact/TS-5358-estrutura-base-front` | `master` (`3f5ea96`) | 13 | publicada |
| 02 | `feature/TS-5359-temas-claro-escuro` | 01 | 5 | publicada |
| 03 | `feature/TS-5360-componentes-formulario` | 02 | 22 | publicada |
| 04 | `feature/TS-5361-componentes-overlay-tabela` | 03 | 31 | publicada; **publicar de novo** (`e031e31`) |
| 05 | `refact/TS-5362-pre-trade-nova-arquitetura` | 04 | 15 | publicada |
| 06 | `refact/TS-5363-lotes-nova-arquitetura` | 04 | 18 | publicada |
| 07 | `refact/TS-5364-report-transfer-nova-arquitetura` | 04 corrigida | 14 | publicada |
| 08 | `refact/TS-5365-formalizacao-nova-arquitetura` | 04 corrigida | 7 + 3 | publicada; **publicar de novo** (merge da master, porte e ajuste dos filtros) |
| 11 | `refact/TS-5368-onboarding-usuarios-nova-arquitetura` | 04 corrigida | 24 | publicada |
| 09 | `refact/TS-5366-controladoria-nova-arquitetura` | 04 corrigida | 34 | sem push |
| 10 | `refact/TS-5367-orquestrador-nova-arquitetura` | 04 corrigida | 18 | sem push. Conflito conhecido com a 11 (3 imports) |
| 12 | `refact/TS-5369-paginas-gerais-nova-arquitetura` | 04 corrigida | 24 | sem push |
| 14 | `feature/TS-5371-docs-api-autenticada` (front e BFF) | 04 corrigida / `origin/master` | 18 + 3 | sem push |
| 15 | `feature/TS-5372-vitrine-design-system` (front e BFF) | 04 corrigida / `origin/master` | 31 + 1 | sem push |
| 13 | `chore/TS-5370-remove-angular-material` | 04 + merge de todas as áreas (`2dbb699`) | 53 + merges | sem push. Vai por último |
| 18 | `fix/TS-5386-seguranca-front` | `origin/master` (`576957c`) | 6 | sem push |
| 20 | `chore/TS-5387-devcontainer` | `origin/master` (`576957c`) | 10 | sem push |

**Ordem para abrir as PRs na `sandbox`:**
1. 01 → 02 → 03 → 04.
2. As áreas (05 a 12, 14 e 15), em qualquer ordem. Na 11 depois da 10,
   aplicar a resolução da tarefa 10.
3. A 13, por último.
4. A 18 e a 20 podem ir a qualquer momento. Quem entrar depois resolve os
   conflitos como os scripts: specs do `9bcf7b7` ficam na versão do épico;
   `package.json` do épico com as versões da 18; lock refeito sem as
   entradas `@angular/*`; guard do `/pdd` em `controllership.routes.ts`;
   spec de rotas com os imports de `@core` e as rotas públicas lazy. O
   passo a passo está na tarefa 18.

**Faltam: 6** (17 e 19 em andamento; 21 a 24 a planejar).

| # | O quê | Como vai |
|---|---|---|
| 17 | Pasta `.ai`: regras, referências, receitas, scripts e fronteiras para desenvolver com IA | pode começar: a 13 já criou as regras de lint e o `AGENTS.md`. Leva também as regras de segurança da 18 |
| 19 | Controle de acesso pelo portal: permissões, grupos e atribuição em lote no Azure | depois do épico. Antes, decidir D16–D19 |

- **Adiada:** a 16 e a D9, que o Pietro faz depois com o time de
  infraestrutura.
- **Pendências do Pietro:**
  - publicar as branches sem push (09, 10, 12, 14 e 15 no front e no BFF;
    13, 18 e 20) e de novo a 04 e a 08, e abrir as PRs;
  - antes do deploy de tudo:
    - criar as app roles (`api-docs:read`, `design-system:read`);
    - criar a variável `ENVIRONMENT` do front em cada ambiente;
  - confirmar com a infraestrutura o que o gateway envia (HSTS e outros
    cabeçalhos) antes de ligar o HSTS da 18;
  - na 24: pedir as permissões do Graph para o app do BFF (lista na 19) e
    o consentimento de admin;
  - testar o login real e os fluxos na sandbox;
  - depois de um ciclo na sandbox sem violação, trocar a CSP de report-only
    para valendo.
- **Perguntas da 5ª leva:** respondidas em 16/10 (ver `decisoes.md`):
  - o CERC fica com o "baixar imagem";
  - a margem sem os 2,5% extras, num commit que pode ser revertido;
  - o proxy da sandbox vai para `scripts/` (20);
  - o compose da raiz fica só com a imagem de produção (20).
- **Achados novos:** A23 a A25 (tooltip de ação desabilitada, login apaga
  a preferência do menu e ícones com a secundária crua na Dots).

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

## Rodar local contra o BFF da sandbox

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
