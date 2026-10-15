# Decisões

Cada decisão tem um dono e uma data. Quando uma pendente fechar, ela vai
para "Tomadas" com o motivo. Isso evita rediscutir depois.

## Pendentes

| # | Decisão | Opções | Recomendação | Quem decide | Tarefa |
|---|---|---|---|---|---|
| D9 | Onde rodam o E2E e a cobertura | (a) job novo no `workflow.yml` do front; (b) mudar o `build.yml` compartilhado de `Capitalis/actions` | (a). Não mexe no pipeline dos outros repos | Pietro, com o time de infraestrutura (adiada em 11/10: tarefa 16 fica para depois) | [16](tarefas/16-testes-e2e-cobertura.md) |
| D10 | Padrão dos campos liga/desliga nos formulários (ex.: "Ativo", "Coobrigação") | (a) um `app-switch` novo em `shared/ui`, parecido com os interruptores de antes; (b) caixa de marcar; (c) controle segmentado Sim/Não | (a) nos formulários, que é o mais fiel ao que havia. O Sim/Não segmentado fica só para filtros. Hoje cada área fez de um jeito: a 07 usou caixa de marcar e a 08 usou Sim/Não | Pietro | 07, 08 e passada de consistência |

## Tomadas

| Data | Decisão | Motivo |
|---|---|---|
| 11/10/2026 | D7: cada serviço vai para o `data-access/` da feature dona dele. O que mais de uma feature usa (ex.: `product.service`, usado por Orquestrador, Onboarding e Usuários) fica na feature dona (`features/products/data-access/`) com um único arquivo público que as outras importam; o que for genérico de verdade (sem regra de negócio) sobe para `shared/` | Pietro: "organize da maneira que fizer mais sentido pra arquitetura que montamos" |
| 11/10/2026 | D8: docs da API com visual próprio (componentes de `shared/ui`), sem Swagger UI nem Redoc | Pietro |
| 10/10/2026 | D5: tabela própria sobre `@angular/cdk/table` (estrutura e acessibilidade do CDK, visual todo nosso) | Pietro escolheu a recomendada |
| 10/10/2026 | D6: datepicker próprio sobre `@angular/cdk/overlay`, com o calendário escrito por nós | Pietro escolheu a recomendada: segue tema e dark mode e fica igual em Chrome, Edge e Safari |
| 10/10/2026 | D2: eu proponho a primária e a secundária de cada marca no modo escuro, com contraste medido, e o Pietro aprova | Pietro: "sim" |
| 10/10/2026 | D3: o tema Viva continua, mesmo sem deploy hoje | Pietro: "sim" |
| 10/10/2026 | D4: só a fonte Inter (saem Roboto e Sora) | Pietro: "sim" |
| 10/10/2026 | Cada tela também é **organizada e refatorada**: otimização, organização, reúso de código e padronização de comportamentos (ex.: como mostrar valor vazio), **sem** mudar comportamento, usabilidade ou lógica da página | Pietro |
| 10/10/2026 | Nada vai para a master por enquanto. Cada branch nasce da anterior: 02 da 01, 03 da 02, 04 da 03, cada área (05–12) da 04, e a 13 junta tudo | Pietro |
| 10/10/2026 | Continuar com vários temas de marca, escolhidos por deploy (`THEME_KEY` em `assets/env.js`, gerado na subida do container), agora aplicados em todas as páginas | Pedido do Pietro. Muitas telas ignoram o tema hoje |
| 10/10/2026 | O tema define só as cores principais e declara primária e secundária para o claro **e** para o escuro. Neutros, superfícies e cores de status são comuns a todas as marcas | Pietro. Derivar o escuro por cálculo pode deixar a marca sem contraste |
| 10/10/2026 | Dark mode começa seguindo o sistema operacional. Claro / Escuro / Sistema fica no menu do usuário (rodapé da sidebar), e a escolha fica salva no navegador | Pietro |
| 10/10/2026 | Referência visual: Pré-Trade e Lotes de Liquidação (o design, não necessariamente o código) | Pietro |
| 10/10/2026 | Sem Angular Material: todos os componentes são próprios | Pietro reforçou: "quero ter todos os componentes próprios" |
| 10/10/2026 | O `@angular/cdk` fica, só como comportamento por baixo dos componentes | Menos código nosso para manter e menos bug de acessibilidade |
| 10/10/2026 | Ícones próprios em SVG. A fonte Material Icons sai | Pietro |
| 10/10/2026 | D1: conjunto de 146 ícones aprovado como está ([anexos/icones](anexos/icones/)) | Pietro validou a página de revisão: "gostei bastante, prossiga" |
| 10/10/2026 | A refatoração de arquitetura vem junto com os temas (prompt de refatoração enviado pelo Pietro), mantendo o comportamento | Pietro |
| 10/10/2026 | Fatiado em PRs: a base primeiro (01–04), depois uma por área (05–12) e o encerramento (13). Em cada área, um commit só move arquivos e os commits seguintes trazem estilo e refatoração | Revisão possível e renomeações reconhecidas pelo git |
| 10/10/2026 | Eu commito sem push e entrego a lista exata de branches. O Pietro publica e abre as PRs | Pietro |
| 10/10/2026 | `-sdbx` só quando o merge na `sandbox` der conflito | Pietro |
| 10/10/2026 | O Pré-Trade do front não será descontinuado e pode ser movido e refatorado | Pietro. Revoga a orientação de 25/09 (TS-5238) |
| 10/10/2026 | Tudo responsivo (até ~400 px), com APIs modernas do Angular e nada depreciado. Os navegadores-alvo são Chrome, Edge e Safari | Pietro |
| 10/10/2026 | Nova página de docs da API: só o OpenAPI do **BFF**, servido numa rota protegida por sessão e permissão. A página pode **executar qualquer método** com a sessão do usuário, e o BFF continua validando cada chamada | Pietro |
| 10/10/2026 | Nova página de design system: **vitrine viva** (tokens, marcas em claro e escuro, tipografia, ícones e componentes com estados, trocando marca e tema na hora). Nada é salvo | Pietro |
| 10/10/2026 | Testes: spec de comportamento em todo componente novo ou mexido, cobertura mínima no CI, E2E em Chromium (Chrome/Edge) e WebKit (Safari), e regressão visual por prints | Pietro: "hoje não temos muitos testes e isso é péssimo" |
| 10/10/2026 | **Todas** as páginas seguem os estilos (tokens) e os componentes reutilizáveis de `shared/ui`. Padrão novo nasce em `shared/ui`, nunca dentro da tela. A 13 trava isso no lint (sem `@angular/material`, sem cor solta fora dos tokens, sem `::ng-deep` em componente de `shared/ui`) | Pietro confirmou: "todas as páginas devem seguir os estilos definidos por nós e os componentes reutilizáveis" |
| 10/10/2026 | D10: gráficos próprios em SVG (`shared/ui/charts`), com o estilo das referências que o Pietro enviou: barras arredondadas, mês em andamento hachurado, linhas suaves com área em degradê, linha tracejada para comparação, rosca com segmentos separados, barras radiais, mapa de calor, sparklines nos KPIs e tooltip escuro | Pietro: "continue com o SVG mas mude os estilos para ficar melhor trabalhado" |
| 10/10/2026 | Manter os detalhes das telas de hoje no redesenho: tooltips (inclusive o balão das aprovações e o de texto cortado), hover, linha expansível animada, trilha de etapas com pulso, selo piscando, prazo com anel, flash na linha após ação, botão spinner → check. Sidebar com separação por módulos (GERAL / MÓDULOS / ADMINISTRATIVO) também no modo trilho | Pietro na revisão da prévia v1: "se perdeu muito dos estilos de antes" |
| 10/10/2026 | Sidebar de ponta a ponta na vertical, no layout da segunda referência do Pietro: fundo cinza leve com uma linha separando do conteúdo; topo com a marca e o botão de recolher; seções Geral / Módulos / Administrativo que abrem e fecham; grupos com árvore de subitens (item atual com fundo e ícone na cor da marca); no rodapé Docs da API e Design system (selo "Nova") e o cartão do usuário, que abre o menu com Aparência (Claro / Escuro / Sistema) e Sair. Recolhida (68 px): só ícones, rótulos curtos das seções e submenu flutuante no hover. No celular vira gaveta. Substitui a sidebar flutuante da prévia v3 | Pietro: "não gostei da sidebar, faça algo mais nesse sentido" e "que a sidebar ocupasse a vertical de ponta a ponta" |
| 10/10/2026 | Organização da página como na referência: à direita da sidebar, um cabeçalho com voltar (só nas telas de detalhe) e a trilha com ícones à esquerda, e a ação principal da página à direita (ex.: Novo Pré-Trade, Novo cadastro); abaixo, título e a descrição da página visível (hoje ela fica no tooltip do "?"); depois o conteúdo. Sai o ícone ao lado do título. Busca global fica de fora, porque o portal não tem | Pietro: "a sidebar, header e conteúdo da página gostaria de organizar dessa maneira" |
| 10/10/2026 | Conteúdo da linha expansível sem moldura: continua no mesmo fundo da linha aberta, com a barra de destaque descendo até o fim do detalhe, e a tabela interna sem caixa em volta. Vale também para o Pré-Trade, que hoje usa um cartão | Pietro: o cartão "fica parecendo que o conteúdo tá saindo e não que está dentro da tabela" |
| 10/10/2026 | Botões, chips e pílulas tom sobre tom: fundo claro da cor e texto/ícone na mesma cor mais forte (no escuro, mais clara). Status de lote deixa de ser pílula sólida com texto branco. Desabilitado fica num cinza mais claro, sem cor. Vale também para o botão principal da página (fundo claro da marca, texto na cor da marca). Exceções: tooltip e diálogo explicativo, que têm estilo próprio | Pietro, com prints das ações da tabela e das pílulas de status; sobre o principal preenchido: "não está no padrão de todo o resto" |
| 10/10/2026 | KPI simples: só ícone, título e valor (saem brilho, sparkline e variação). Quando o KPI filtra a lista, ele vira botão e mostra "Clique para filtrar a lista" (ativo: "Filtrando a lista abaixo"). Os contadores do funil do Orquestrador perdem a barrinha de proporção | Pietro: "deixar os kpis simples… e caso ele sirva para filtrar, ter um texto indicando isso" |
| 10/10/2026 | Texto que não cabe (chips, nomes em célula) termina em reticências dentro do padding e mostra o texto inteiro no tooltip | Pietro, com print de chip de fundo cortado |
| 10/10/2026 | Um padrão só para alternar visão: o segmentado da tela de Lotes (ícone + rótulo, opção ativa com fundo da marca), em todas as telas e também no menu de Aparência. Saem a pílula deslizante e as abas sublinhadas | Pietro: "o toggle de views não está seguindo um padrão, gosto mais da tela de liquidação" |
| 10/10/2026 | Tudo que abre e fecha tem animação curta: linha expansível, acordeão, flows/subflows/processos, grupos e seções da sidebar (altura de 0 até o conteúdo, ~250 ms) e troca de visão (fade curto do conteúdo novo). Com movimento reduzido, só opacidade | Pietro: "as aberturas de toggle e tal deveriam ter um tratamento ou animação também" |
| 10/10/2026 | Dois ícones novos no conjunto, `sun` e `moon`, para o seletor de Aparência (total: 148) | O seletor precisa deles e o conjunto aprovado não tinha |
| 10/10/2026 | Hovers discretos e transições leves (240 ms, ease-out): sem deslocar elementos, só tons suaves de fundo e borda | Pietro: os hovers estavam "agressivos" |
| 10/10/2026 | Skeleton de carregamento próprio (`app-skeleton` em `shared/ui`), no lugar do `ngx-skeleton-loader` (90 usos em 19 templates) | Pietro: evitar o ngx e ter isso no nosso código |
| 10/10/2026 | O botão de dark mode só aparece na 13, quando todas as telas já usam tokens | Evita produção com telas meio claras e meio escuras |
