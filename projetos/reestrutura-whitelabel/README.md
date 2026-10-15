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
| 13 | [Remove Angular Material](tarefas/13-remove-angular-material.md) | `chore/TS-5370-remove-angular-material` | 01–12 | a iniciar | TS-5370 |
| 14 | [Docs da API autenticada](tarefas/14-docs-api.md) | `feature/TS-5371-docs-api-autenticada` (front e BFF) | 04 | a iniciar | TS-5371 |
| 15 | [Vitrine do design system](tarefas/15-vitrine-design-system.md) | `feature/TS-5372-vitrine-design-system` | 04 | a iniciar | TS-5372 |
| 16 | [E2E, cobertura e regressão visual](tarefas/16-testes-e2e-cobertura.md) | `test/TS-?-e2e-cobertura-regressao-visual` | 01 | **adiada** (Pietro faz depois, com o time de infraestrutura) | — |
| 17 | [Pasta `.ai`: desenvolver com IA](tarefas/17-pasta-ai.md) | `chore/TS-?-pasta-ai` | 04 (fecha depois da 13) | a iniciar | — |
| 18 | [Segurança do front](tarefas/18-seguranca.md) | `fix/TS-?-seguranca-front` | `master` (independente do épico) | a iniciar | — |

## Situação em 15/10

**Prontas: 12 de 17** (a 16 está adiada e fica fora da conta).
- 01 a 08 e 11 publicadas em 15/10, sem merge em nenhum ambiente.
- 09, 10 e 12 (3ª leva) com commits feitos, sem push, esperando o Pietro
  publicar.
- Merge de teste das oito áreas juntas sobre a 04: compila e passa nos
  testes (1.627, só 1 falha, que já é da base). O único conflito é o da 10
  com a 11, com o passo a passo na tarefa 10.
- A 07, a 08 e a 11 nascem da 04 com as três correções de 15/10, que também
  já estão publicadas.

Cada tarefa tem a seção "O que foi feito", com os commits, as mudanças
visíveis para a PR e a validação.

| # | Branch | Nasce de | Commits | Situação |
|---|---|---|---|---|
| 01 | `refact/TS-5358-estrutura-base-front` | `master` (`3f5ea96`) | 13 | publicada |
| 02 | `feature/TS-5359-temas-claro-escuro` | 01 | 5 | publicada |
| 03 | `feature/TS-5360-componentes-formulario` | 02 | 22 | publicada |
| 04 | `feature/TS-5361-componentes-overlay-tabela` | 03 | 29 | publicada, com as 3 correções |
| 05 | `refact/TS-5362-pre-trade-nova-arquitetura` | 04 | 15 | publicada |
| 06 | `refact/TS-5363-lotes-nova-arquitetura` | 04 | 18 | publicada |
| 07 | `refact/TS-5364-report-transfer-nova-arquitetura` | 04 corrigida | 14 | publicada |
| 08 | `refact/TS-5365-formalizacao-nova-arquitetura` | 04 corrigida | 7 | publicada |
| 11 | `refact/TS-5368-onboarding-usuarios-nova-arquitetura` | 04 corrigida | 24 | publicada |
| 10 | `refact/TS-5367-orquestrador-nova-arquitetura` | 04 corrigida | 18 | commits feitos, sem push. No merge com a 11, conflito em 3 imports, com o passo a passo na tarefa |
| 12 | `refact/TS-5369-paginas-gerais-nova-arquitetura` | 04 corrigida | 24 | commits feitos, sem push |
| 09 | `refact/TS-5366-controladoria-nova-arquitetura` | 04 corrigida | 34 | commits feitos, sem push |

Abrir as PRs nesta ordem: 01 → 02 → 03 → 04. Depois as áreas, em qualquer
ordem.

**Faltam: 5.**

| # | O quê | Como vai |
|---|---|---|
| 13 | Remove o Angular Material e liga o seletor de tema | depois de todas as áreas, porque junta tudo |
| 14, 15 | Docs da API (front e BFF) e vitrine do design system | por último. Só dependem da 04 |
| 17 | Pasta `.ai`: regras, referências, receitas, scripts e fronteiras para desenvolver com IA | começa quando quiser (depende da 04); fecha depois da 13, que cria as regras de lint das fronteiras |
| 18 | Segurança: bibliotecas sem falha conhecida, cabeçalhos do nginx com CSP, `iamGuard` no `/pdd` e auditoria no `validar.sh` | da `master`, a qualquer momento. Não depende do épico |

- **Adiada:** a 16 e a D9, que o Pietro faz depois com o time de
  infraestrutura.
- **Pendências do Pietro:**
  - publicar as branches 09, 10 e 12 e abrir as PRs;
  - testar o login real e os fluxos na sandbox.
- **Decisões abertas:**
  - D13: ícone `more-vertical` novo (conjunto vai a 149);
  - 09: a barra de ferramentas do ApexCharts (zoom e baixar imagem) saiu
    da Performance. Repor o "baixar imagem" no `app-chart`?
  - 12: envio à base de conhecimento com só "Poliedro - Geral" manda
    `department=all`; confirmar com o BFF;
  - commit `129bee4` da 05;
  - A13: contraste da Dots e da Cerys no tema claro;
  - A15: títulos fora do padrão;
  - fluxo de commit: eu commito e o Pietro revisa antes de publicar, ou não
    commito antes da revisão.
- **Passada de consistência no fim:**
  - A14: margem do contêiner das páginas;
  - a Formalização trocar o `.search-box` local pelo `.app-input-icon`;
  - a Formalização usar o `app-split-button` no Exportar;
  - a `kpi-grid` da 09 subir para `shared/ui` e servir às outras grades de
    KPI;
  - D11: a 07 e a 08 passarem ao `app-switch`.
- **Esforço:** cada leva de três áreas, em modo completo, consome perto de
  uma sessão inteira.

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
