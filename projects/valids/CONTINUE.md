Status: em andamento
Data: 04/11/2026
Tags: valids, pdd, ecl, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`. Os nomes reais por trás dos análogos e o CNPJ de cada fundo por letra estão no arquivo local `~/.config/workspace/private/valids.md`.

Este arquivo foi montado em 03/11/2026, na migração da pasta local `~/projects/pdd-workspace` para cá, a partir do README, do histórico das tarefas (último registro em 30/10) e das branches conferidas nos repositórios em 03/11. O que aqui não está escrito, essas fontes não dizem: confira antes de afirmar.

## Onde parei

Migração: em 03/11/2026 a pasta local `~/projects/pdd-workspace` virou este projeto, com os nomes em inglês e o conteúdo igual, publicada no mesmo dia (8 commits, de `chore: palavras conhecidas do projeto valids` a `chore: Frescor como palavra conhecida`). O que sobrou dela está em "Pendências fora da feature".

Situação das abas pelo `README.md` (30/10):

| Aba | Situação |
|---|---|
| Visão Geral e Histórico VP e PDD | completas; desde 30/10 leem a poça do Postgres pela carga do ECL (D78), atrás de `CFG_VALID_ECL_STOCK_FROM_POOL` |
| Mov. Estoque ([tarefa 01](tasks/01-stock-movement.md)) | commitada na TS-5441 nas três pontas (28/10); carga da poça com liga/desliga por variável de ambiente, desligada (D58) |
| Abertura de Rating ([02](tasks/02-rating-breakdown.md)) | implementada na TS-5438 (27/10) e integrada na TS-5442 (28/10); poça vazia até ligar a carga |
| Análise de Migração ([03](tasks/03-migration-analysis.md)) | faixas mensais integradas na TS-5442; o pagamento espera a D21 (controladoria) |
| Monitoramento de Inconsistências ([04](tasks/04-inconsistency-monitoring.md)) | Análise Residual commitada na TS-5466 e Performance de Pagamento na TS-5467 (29/10, sem push); D76 aberta; Lacunas só com o título (D41, D72) |

Últimos registros (30/10, histórico da tarefa 01, itens 17 e 18):

- nomes ECL em todo o módulo `valid` da data-lake-api (D80) commitados na `feature/TS-5442-pdd-integracao`: data-lake-api `5d284f6` e BFF `ee9d113`, que sobem juntos;
- ArgoCD de staging (`feature/TS-5442-pdd-cargas-diarias`): worker `valid` e agendamento das cargas no beat, com os horários de produção, por escolha do Heitor, embora o Postgres do staging fique desligado das 19h às 08h e nos fins de semana;
- o deploy de produção de 29/10 aplicou as migrations 0010 e 0011, mas as cargas diárias não rodaram: o beat não agendou as tasks do `valid`.

Conferido nos repositórios em 03/11/2026 (pelo último fetch de cada um, de hoje) e **ainda não registrado nas tarefas**: TS-5438, TS-5441 e TS-5442 já estão na `origin/master` da data-lake-api, do BFF e do front (a TS-5438 também no platform-cessao). A TS-5466 e a TS-5467 seguem só locais, fora da `master`.

Decisões pendentes no `decisions.md`: D21, D38, D41, D43, D47, D72 e D76.

## Branches e worktrees

| Repositório | Branch | Estado em 03/11 |
|---|---|---|
| data-lake-api | `feature/TS-5442-pdd-integracao` (`5d284f6`) | publicada, na `master`; TS-5438 e TS-5441 também |
| data-lake-api | `feature/TS-5466-pdd-analise-residual`, `feature/TS-5467-pdd-performance-pagamento` | só locais, fora da `master` |
| apl-credit-whitelabel-api (BFF) | `feature/TS-5442-pdd-integracao` (`ee9d113`) | publicada, na `master`; TS-5466 e TS-5467 só locais |
| apl-credit-whitelabel (front) | `feature/TS-5442-pdd-integracao` (`5adf998e`) | publicada, na `master`; TS-5466 e TS-5467 só locais |
| platform-cessao | `feature/TS-5438-pdd-abertura-de-rating` | publicada, na `master` |
| data-lake-api-argocd | `feature/TS-5442-pdd-cargas-diarias` (`5042f92`) | publicada; fora da `master` pelo que o clone local sabe (sem fetch desde o clone) |

Worktrees: nenhum. A cópia `~/projects/.worktrees/apl-credit-whitelabel-mov-estoque`, citada na tarefa 01, não existe mais; o front está no checkout principal.

## Pendências fora da feature

Da migração e da máquina do Heitor, levantadas em 03 e 04/11/2026. Nenhuma bloqueia a feature.

| # | Pendência | Quem decide | O que falta |
|---|---|---|---|
| 1 | Apagar as cópias antigas, fora do repo: `~/projects/pdd-workspace` e `~/projects/.pdd_workspace` | Heitor | o sim dele; o conteúdo já está aqui, em `~/.config/workspace/private/valids.md` e em `~/.local/share/workspace/projects/valids/` |
| 2 | O `~/.config/workspace/names.toml` da máquina do Heitor nasceu em 03/11 só com os nomes deste projeto; em 04/11 ganhou os dos outros projetos (41 nomes distintos) | Heitor | confirmar que é a tabela completa do Pietro; tirar as 5 entradas repetidas (iguais entre si) e o comentário do topo que ainda diz "Partial on purpose" |
| 3 | O hook não barra CNPJ (o `CLAUDE.md` antigo da pasta fazia um grep de 14 dígitos) | Heitor | decidir se os CNPJs do arquivo privado entram no `names.toml`, com a letra do fundo como análogo |
| 4 | O `ws setup` não rodou inteiro na máquina do Heitor: hooks do git ligados à mão e dicionários baixados em 03/11; faltam o `uv`, os links das skills e o portão do Claude Code | Heitor | seguir "Máquina nova" em `projects/workspace/README.md` |
| 5 | O `pre-push` só acusa o e-mail da empresa no commit depois de os commits existirem | Pietro (dono do `ws`) | proposta no `docs/backlog.md`, "Confidentiality check" |

## Próximo passo

1. Perguntar ao Heitor o que aconteceu depois de 30/10: o merge da TS-5442 na `master` (release e data), o deploy e se as cargas diárias foram ligadas. Conferir no Datadog se `dispatch_valid_ecl` e `dispatch_valid_movement` rodaram.
2. Registrar a resposta no histórico da tarefa 01, na tabela de Tarefas e nas abas do `README.md`, e atualizar este arquivo.
3. Decidir com ele o destino da TS-5466 (Residual) e da TS-5467 (Performance), locais e feitas sobre a TS-5442 de 28/10 (sem os commits de 29 e 30/10): atualizá-las sobre a `master` antes de publicar.
4. Seguir pelas pendentes: D76 (indicadores da Performance), D41 e D72 (Lacunas) e a D21, que está com a controladoria.
