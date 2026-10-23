# 31 — Ajustes visuais e padrões de design (pós-deploy)

- **TS:** TS-5424 · **Branch:** `feature/TS-5424-ajustes-visuais-e-padroes` (worktree
  `~/repos/apl-credit-whitelabel-wt/31`, da `master` `f7bb2d84`)
- **Status:** **PR 1 em andamento** (23/10): decisões D108 a D118; quatro agentes no front (pacotes A
  a D, briefs em `anexos/agentes/brief-31.md`); barra do celular e `app-card flush` feitos por mim.
- **Depende de:** 24 (deploy de 21/10)

## Por quê

Pedido do Pietro em 21/10, depois do deploy:
- ajustes visuais que ele encontrou em produção;
- regras de design que deixem uma única forma de fazer cada coisa. Hoje há telas que resolvem o mesmo
  problema de jeitos diferentes. O primeiro exemplo dele é o carregando (skeleton).

Em 23/10 ele mandou a lista (abaixo) e pediu: o que puder virar regra ou token, vira; o que ferir outra
regra, se discute antes.

A leitura foi feita na `master` de 21/10 (front `f7bb2d84`, BFF `bb877db`), no apl-shared-service
(`origin/master`) e no apl-orchestrator-service. Os caminhos abaixo são do front (`src/app/`) quando não
dizem o repo.

## Parte A: a lista do Pietro, com o diagnóstico

### Geral

**A1. Favicon antigo no celular.** *Resolvido pela D116: o "favicon" era o símbolo da marca na barra
do portal no celular, que sai. O diagnóstico abaixo, dos ícones do navegador, fica só registrado.*
- O servidor já entrega só o ícone novo (`src/favicon.ico`, 32×32, de 19/10). Os antigos por marca
  saíram do build no mesmo commit. O antigo que aparece está guardado no aparelho: atalho na tela
  inicial (copiado na criação, nunca atualiza) ou o cache de favicon do Safari/Chrome.
- O que falta no repo: não há `apple-touch-icon`, manifest, `theme-color` nem ícone de 180/192/512 px.
  O iOS pede `/apple-touch-icon.png` por convenção e recebe 404. O wordmark em 32 px é ilegível.
- `public/favicon.ico` é o ícone padrão do Angular CLI, nunca copiado para o build: peça morta.
- **Proposta:** ícones a partir do símbolo da marca (`assets/default/mark.svg`), não do wordmark:
  `favicon.svg` + `favicon.ico` 32 + `apple-touch-icon.png` 180 + `icon-192/512.png` + `site.webmanifest`
  + `theme-color` claro/escuro. Apagar o `public/favicon.ico`. Quem já tem atalho precisa recriá-lo.
- **Regra:** os ícones do app saem do `mark.svg` por script (`.ai/scripts`), nunca editados à mão.

**A2. Blocos de código (linguagem, cor e copiar).**
- Componente: `shared/ui/code-block`. Copia e colore, mas a cor só existe na superfície `soft`, e só
  para `json` e `shell` (tokenizador próprio, `code-highlight.ts`; não há biblioteca de highlight).
- Três famílias convivem: `app-code-block` soft (colorido), `app-code-block` dark (sem cor) e `<pre>`
  locais (erro do Envio de relatórios, markdown da POLI). A linguagem nunca aparece sozinha: é o
  `title` livre, quando a tela passa um. O JSON do Onboarding BGT não tem nem barra nem copiar.
- Código dentro do texto (`<code>`) não tem estilo global: 5 formas, tamanhos de 11 a 14 px, e duas
  telas caem na fonte mono do navegador. O chip escuro da coluna Variáveis do Envio de relatórios
  (`.cell-code`, `report-transfer/components/_cells.scss:42`) usa `--code-bg`/`--code-fg`, que são
  iguais nos dois temas: pílula escura no claro e invisível no escuro (contraste 1,02:1 com a
  superfície). Confirmado pelo Pietro: os prints dos chips são deste item.
- **Proposta:**
  - um só bloco (`app-code-block`), sempre com a linguagem na barra (rótulo vindo de `language`),
    cor e copiar; superfície única que segue o tema (a `soft`, que já passa AA);
  - cor de sintaxe para json, shell, sql, python, ts/js, xml, yaml e http, com `highlight.js/lib/core`
    e só essas linguagens (decisão pendente: biblioteca × tokenizador próprio);
  - a POLI passa a renderizar as cercas de código pelo mesmo visual (opção `highlight` do markdown-it);
  - código inline: um estilo global para `code` (mono, fundo `--code-soft-bg`, borda, raio pequeno),
    com tokens `--code-inline-*`; o `.cell-code` sai.
- **Regra:** `<pre>` só dentro do `shared/ui/code-block`; `check-patterns` barra `<pre>` e classes
  próprias de `code` em `features/`.

### Skeleton (carregando)

**A3. Despadronizado, barras finas em tabela, itens sem espaço.**
- O `app-table` não tem skeleton próprio: com `[loading]` ele mostra uma linha única com o que a tela
  passar no slot `appTableLoading`. São 25 telas, cada uma com o seu: barras de 14 a 40 px, de 3 a 6
  barras, com ou sem embrulho, todas de largura total, sem respeitar as colunas.
- Lotes de Liquidação (o print): 5 barras de 16 px, gap de 10 px, 48 px de padding em cima e embaixo
  (o do estado da tabela mais o do embrulho `.lb-table-loading`).
- Grudados: só as duas tabelas do CERC, porque o host do `app-skeleton` virou `display: block` e o gap
  (que é de flex) deixou de valer (`cerc-reconciliation-table.component.scss:21`,
  `cerc-pending-assets.component.scss:23`).
- Fora da tabela: o Orquestrador mistura spinner e texto; PDD, Onboarding BGT (detalhe e
  monitoramento) e o analítico do Consolidado de Caixa usam spinner grande com texto; Clientes usa o
  texto "Carregando...".
- A regra atual (`.ai/rules/components.md:100` e `:150`) só lista os componentes; o `check-patterns` não
  confere nada de carregando. O template de página nova (`new-page`) gera `<app-skeleton height="14px"
  [count]="pageSize">`, que é a forma que as telas copiam.
- **Proposta:**
  - o `app-table` ganha skeleton próprio: linhas da altura de uma linha real, uma barra por coluna
    (com a largura da coluna), quantidade = tamanho da página até 8. As 25 telas tiram o slot;
  - conteúdo fora de tabela: skeleton no formato final (cartões, KPIs, gráfico), para a tela não mudar
    de altura quando os dados chegam;
  - spinner só em ação em andamento (botão, envio); texto "Carregando" solto não existe;
  - tokens `--skeleton-gap`, `--skeleton-line`, `--skeleton-radius`; o `app-skeleton` volta a garantir o
    gap mesmo se o host mudar de `display`;
  - vitrine com o exemplo de tabela carregando; template `new-page` atualizado.
- **Regra:** escrita no `.ai/rules/components.md` ("quando usar cada um") e barrada no `check-patterns`
  (`appTableLoading` em `features/`, `app-spinner` fora de botão, texto "Carregando").

### Controle de acesso

**A4. Pessoas: todos "Sem organização" e a coluna Cliente vazia.**
- O BFF lê organização e cliente como **atributos do usuário** no Graph (nomes nas variáveis
  `CFG_ACCESS_CONTROL_ORGANIZATION_ATTRIBUTE` e `..._CLIENT_ATTRIBUTE`; `access_control/repository/__init__.py:51-67`,
  `services/azure/graph.py:77-79`). É o desenho da D64. Em produção esses atributos não têm valor em
  ninguém, então todos caem em "sem organização" (`access_control/business/scope.py:25-40`).
- A D91 (20/10) mudou a origem: organização e cliente vêm de claims do Enterprise Application,
  emitidas conforme o **grupo de instituição** da pessoa. A adaptação da 27 à D91 (com a lista de
  grupos de instituição numa variável, D98) nunca foi feita: não existe "instituição" no BFF nem no
  front.
- Efeito colateral provável (não verificado): mudar organização/cliente pela tela faz `PATCH users/{id}`,
  que pede `User.ReadWrite.All`, permissão que a D94 excluiu. Deve falhar em produção.
- **Proposta (BFF + front):** organização e cliente passam a vir da participação nos grupos de
  instituição, com o mapa grupo → (organização, cliente) numa variável (D98); mudar a organização de
  alguém vira trocar a pessoa de grupo de instituição. Precisa da lista dos grupos de instituição e dos
  valores de claim de cada um (infraestrutura).

**A5. Grupos: tirar a regra "criado pela tela × do diretório".**
- A regra é a D19: o portal só mexe em membros e só apaga grupos de que o app é dono
  (`ownedObjects` do service principal). Está em ~10 pontos do BFF (`access_control/business/batch.py`,
  `rules.py`, `__init__.py:641-669`) e ~14 specs do front.
- A lista "Do portal" já é só dos grupos do app: os que têm alguma role do app ou de que ele é dono
  (`list_groups`, `business/__init__.py:482-509`). A busca ("Todo o diretório") mostra qualquer grupo
  do tenant.
- Risco: a permissão `GroupMember.ReadWrite.All` vale para o tenant inteiro; o limite está só no código.
- **Proposta:** trocar "dono" por "do app" = dono **ou** com alguma role do app **ou** grupo de
  instituição da lista (D98). Isso libera mexer em membros de todos os grupos da lista do Pietro
  (inclusive os `[PLGN AI]`) e mantém travados os grupos corporativos sem relação com o portal. Apagar
  continua só para grupo de que o app é dono (sem `Group.ReadWrite.All`, D94). Revê a D19.

**A6. Padrão de nome ao criar grupo.** Os 41 grupos do app (lista do Pietro, 23/10):

| Tipo | Grupos | Quantos |
|---|---|---|
| Acesso a uma página, só a página | `[FRONT] ACCESS-CONTROL`, `CONCILIACAO`, `CONCILIACAO-DE-ESTOQUES`, `FORMALIZACAO`, `GERENCIAMENTO-DE-PRODUTOS`, `LOTES-DE-CESSAO`, `ONBOARDING-BGT`, `ORCHESTRATOR`, `PRE-TRADE`, `REGISTROS`, `SAUDE-DOS-FUNDOS`, `TRANSFERENCIA-RELATORIOS` | 12 |
| Acesso a uma página, com perfil | `[FRONT] LOTES-LIQUIDACAO-ADMIN`, `-READ`; `PRE-TRADE-CEO`, `-COMPLIANCE`, `-DELETE`, `-GESTAO`, `-LEGAL`, `-OPS-UPDATE`, `-RISCOS`; `TRANSFERENCIA-RELATORIOS-ADMIN`, `-OPERACOES` | 11 |
| Organização/parceiro (candidatos a grupo de instituição) | `[FRONT] CERYS`, `dots_users`, `VISAGGIO`, `[FRONT] VALIDUS`(?) | 3–4 |
| Departamento da POLI (nome fixo no código, `shared/schemas/users.py:26-39`) | `[PLGN AI] *` | 13 |
| Teste | `Front-Test` | 1 |

- O padrão `[FRONT] PÁGINA-PERFIL` já é o informal. O problema é que o hífen separa palavras e também
  página de perfil (`PRE-TRADE-OPS-UPDATE`), e as páginas misturam inglês e português.
- **Proposta:**
  - grupo de acesso: `[FRONT] <PÁGINA> - <PERFIL>`, com ` - ` (espaço, hífen, espaço) separando página
    de perfil. Ex.: `[FRONT] PRE-TRADE - RISCOS`, `[FRONT] LOTES-LIQUIDACAO - LEITURA`;
  - a página vem de uma lista fixa no BFF (uma sigla por página do `FRONTEND_ROUTE_PERMISSIONS`); o
    usuário escolhe a página e digita só o perfil, que é normalizado (maiúsculas, sem acento, espaço
    vira hífen), com sugestões (ADMIN, LEITURA, OPERACOES, TESTE...). A prévia mostra o nome final;
  - grupos de instituição e `[PLGN AI]` não são criados pela tela e não seguem esse padrão;
  - grupos antigos continuam funcionando. Renomear exige `Group.ReadWrite.All` (fora da D94), então é
    a infraestrutura que renomeia no Azure, se quiser.

**A7. Atribuir com dois dropdowns (página → perfil).**
- O catálogo existe: `GET access-control/roles` traz `scope`, `scopeName` e `action` por role
  (`BFF shared/utils/permissions.py:113-410`). Nenhuma tela agrupa por ele hoje.
- **Proposta:** em "Adicionar a grupo", 1º a página, 2º o perfil, que lista os grupos que dão acesso
  àquela página. A ligação grupo → página sai das **roles do grupo** (tem `pre-trade:read` → Pré-Trade),
  não do nome, para funcionar com os 41 grupos atuais sem renomear. O rótulo do perfil é o nome sem o
  prefixo e a página. O mesmo par de dropdowns serve para atribuir permissão (página → ação).

**A8. "Ver como" outra pessoa (simular o acesso).**
- Viável. Login e sessão são do BFF (cookie + sessão no Redis); as permissões são a claim `roles` do
  token, congelada na sessão. O ponto de entrada é um só: o middleware que põe `request.state.user`
  (`BFF shared/business/users.py:339`).
- Problemas: organização/cliente da outra pessoa dependem do A4; a renovação da sessão
  (`refresh_session`) reescreve o usuário e apagaria a troca; autoria (aprovação de lote, envio de
  relatórios, POLI, auditoria do lote) usa o usuário da sessão.
- **Proposta (BFF + front, PR própria):** role nova `access-control:impersonate`; a sessão guarda
  "vendo como X" com as roles e o escopo de X (do índice do controle de acesso); **só leitura**
  (qualquer escrita devolve 403 enquanto estiver vendo como outro); faixa fixa no topo "Vendo como
  Fulano · Voltar"; logs com os dois usuários; expira em 30 min.

**A9. Faixa vazia no topo das tabelas de Pessoas e Grupos.**
- Vem do `app-card` com `flush`: ele mantém 16 px no topo do corpo
  (`shared/ui/card/card.component.scss:45-47`). Com título, é o respiro entre título e tabela; sem
  título (Pessoas, Grupos e a vitrine), vira a faixa.
- **Proposta:** `flush` sem cabeçalho não tem padding no topo (no `app-card`, com teste).

### Orquestrador

**A10. Funil da aba Execuções → Processos (a tabela).**
- `orchestrator/flow-funnel` é um `app-table` com uma coluna por status. Dados: `aggregates.process_status`
  (`{subflow, process, status, count}`), calculados no apl-orchestrator-service. Só há contagem por
  status, sem tempos.
- Afunilamento possível: "chegaram" = total − não iniciado. A confirmar no orquestrador se `count` conta
  linhas de processo ou flows distintos (reprocesso contaria duas vezes) e como tratar grupos paralelos.
- A Visão do produto já tem um funil próprio (`product-view/components/process-funnel`), com
  `arrived/completed/conversion` por processo, mas outro endpoint e outro recorte (a coorte do período).
- **Proposta:** gráfico de faixas (o da referência): eixo horizontal = processos em ordem; espessura =
  execuções que chegaram; camadas = sucesso, pendente, falha, cancelado; rótulos com o número em cada
  etapa; a tabela atual fica embaixo, compacta. Componente novo `app-stream-funnel` em
  `shared/ui/charts` (SVG próprio). Antes do código, um protótipo com os números reais do print.

**A11. Scroll infinito no `orchestrator/product-view` (Edu Romano).**
- No Datadog (RUM), dois usuários têm visitas com o `GET .../product-analytics/{id}/processes`
  demorando: um com mediana de **19 s**; outro chegando a **60 s**, o tempo máximo de espera do BFF
  (`services/orchestrator/__init__.py:23`). Os demais ficam abaixo de 1,5 s. `summary` e
  `process-series` também passam de 15 s para esses usuários.
- A página faz 4 pedidos independentes e cada resposta troca um skeleton por conteúdo de altura
  diferente. Com respostas de 5 a 60 s, a página muda de altura em degraus enquanto a pessoa rola.
- Primeira suspeita (laço de medida do gráfico na escala de 125% do Windows) derrubada: o código não
  tem laço, e a escala era coincidência.
- **Proposta:** no front, skeletons com a altura final (a página não pula) e estado de erro com
  "tentar de novo" quando o pedido estoura; no apl-orchestrator-service, a lentidão do `processes`
  vira tarefa à parte (fora desta). Falta confirmar o sintoma com o usuário.

**A12. `gap: var(--space-3)` no "Funil de processos".**
- É o card da Visão do produto (`product-view/components/process-funnel`). Hoje: `.funnel` (entre
  cabeçalho e blocos de subflow) com `--space-1`; `.subflow` (entre processos) com `--space-1`
  (o `7940900f`, de 21/10, mexeu nesse).
- **Proposta:** `.funnel` com `--space-3`. A confirmar se era esse ou o `.subflow`.

**A13. KPIs Operações criadas, Concluídas, Em andamento e Com falha.**
- Estão na Visão do produto (`product-view/components/count-tile`), já com variação e sparkline; o
  BFF já devolve tudo (`summary` com comparação e `metric-series`). O sparkline e o tile são locais
  da feature.
- **Proposta:** visual da referência: ícone em quadrado tonal + título + abrir no topo; valor grande;
  embaixo, chip de variação com seta (verde/vermelho conforme o lado bom) à esquerda e sparkline com
  área em degradê à direita. Sobem para `shared/ui` como `app-trend-kpi` + `app-sparkline`, com vitrine.
- **Regra:** a cor da variação segue o lado bom do indicador (`goodWhen: 'up' | 'down'`): falha
  subindo é vermelho. Variação de fatia mostra "p.p." (pontos percentuais).

### Envio de relatórios

**A14. Executar uma rota ou todas, manualmente.**
- "Todas de uma vez" já existe: "Enviar agora", na aba Agendamentos, roda o fluxo inteiro
  (`report-transfer:run`; shared `POST /scheduled-jobs/{key}/run`, `trigger_type=MANUAL`, com o autor no
  histórico). Faltam o botão na aba Fluxos e rodar fluxo sem agendamento (toda execução exige um).
- Uma rota só: precisa do apl-shared-service (parâmetro novo na task `run_flow` e filtro em
  `file_flow.py:221`; o `_run_route` já roda uma rota isolada), do select de rota no diálogo e do
  rótulo do parâmetro no front. O BFF só repassa.
- Riscos: o dedupe (Redis, por hash dos parâmetros) não pega um disparo manual com parâmetro diferente
  do agendado, então a mesma rota pode rodar duas vezes ao mesmo tempo; nomes com `{seq}` podem gerar
  remessas numeradas diferente; o manual ignora fluxo desativado.
- **Proposta (shared + front, PR própria):** parâmetro `route` em `run_flow`; trava por fluxo (lock
  no Redis pelo `flow_key`) enquanto houver execução em andamento; "Enviar agora" na aba Fluxos e por
  rota no detalhe; aviso ao disparar fluxo desativado.

**A15. "Rotas" → "subfluxos".**
- Só texto: ~18 pontos no front, o cabeçalho `rota` do CSV e as mensagens 422 do apl-shared-service, e
  o resumo de um endpoint na Docs da API. Nomes internos (`definition.routes`, tabelas, API) não mudam.
  Nomes já gravados ("Rota 1") continuam como estão; o padrão novo vira "Subfluxo N".
- "Subfluxo" não existe no envio, só no orquestrador, que escreve "Subflow" em inglês e com outro
  sentido (etapa com status e reexecução). Com a execução por rota (A14), o sentido se aproxima.
- **Proposta:** "Subfluxo" no Envio de relatórios e, pela mesma regra (portal em PT-BR), "Subfluxo"
  também no orquestrador, no lugar de "Subflow".

### Pendentes da rodada de 21/10 ([24](24-deploy.md))

- A tabela de agendamentos não cabe a 1440 px com o menu aberto (faltam 195 px).
- As colunas da visão "Por parceiro" não se alinham entre os grupos.

## Divisão em PRs (proposta)

| PR | O que entra | Repos | Depende de |
|---|---|---|---|
| 1 | A1, A2, A3, A9, A12, A13, A15 (texto do front), pendentes de 21/10, A11 (lado do front) | front | — |
| 2 | A4, A5, A6, A7 | front + BFF | lista dos grupos de instituição (infraestrutura) |
| 3 | A8 (ver como) | front + BFF | 2 |
| 4 | A14 e o texto de A15 que vem do shared | shared + front | — |
| 5 | A10 (funil novo) | front | protótipo aprovado |
| — | Lentidão do `product-analytics/processes` | apl-orchestrator-service | fora do épico |

## Decisões

D108 a D118 (23/10), no `decisoes.md`. Em aberto:
- **A4:** de onde vem a organização e o cliente. Com a D118 (`User.ReadWrite.All`), voltar a gravar
  atributo no usuário é possível, mas o token continua vindo do grupo de instituição (D91); a
  recomendação segue sendo ler e mudar pelo grupo. Falta o valor de claim de cada grupo da D112.
- **A11:** o print do Edu Romano (22/10, 17:53) mostra a página curta e ~830 px vazios abaixo do
  fim do `app-shell`, com o menu lateral rolando junto. Não reproduziu localmente (build da master,
  dados fictícios, respostas atrasadas, vindo do Orquestrador rolado). Falta medir em produção.

## Parte B: regras e padrões

As regras que saem da Parte A: ícones do app (A1), bloco e código inline (A2), carregando (A3),
`app-card flush` (A9), KPI com tendência e cor da variação (A13), glossário PT-BR do portal (A15).
Cada uma vai para o `.ai/rules/components.md` do front e para o `design-system.md` daqui, com exemplo
na vitrine e, quando der, checagem no `check-patterns`.

**Contagem do carregando (21/10, na `master`)**, em `features/**/*.html`:

| Forma | Arquivos |
|---|---|
| `[loading]` da própria tabela (`app-table`) | 56 |
| `<app-skeleton>` | 43 |
| texto "Carregando" | 17 |
| `<app-spinner>` | 10 |
| skeleton próprio da feature (classe ou componente `*-skeleton`) | 9 |
| `<app-loading-status-component>` | 1 |

Ainda a levantar (pedido de 21/10): vazio, erro, cabeçalho de página, filtros, modais e botões de ação.

## Como validar

- `check-patterns` limpo, sem item novo na lista de legado.
- Prints de antes e depois em claro, escuro e celular.
- Build, lint e testes sem falha nova.
