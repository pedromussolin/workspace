+++
card = "TS-5394"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 24 — Deploy da reestruturação

- **TS:** TS-5394 · **Branch:** `release/AAAAMMDD` (front e BFF)
- **Release 20261027 (27/10, ~20h20):** shared #76, BFF #227 e front #240 mergeadas na `master` e com a tag trocada no
  argocd. Conferência no Datadog em 28/10, comparando ~20 h antes e depois do deploy:
  - nenhum 403; 401 de 65 para 51; 5xx de 4 para 8, todos de serviço externo (estoque Validus, credenciais da
    whitelist, cadastro pendente), nenhum da release;
  - nenhum e-mail barrado em produção (`Send blocked outside production`);
  - apagar role pela aba Permissões falhava na primeira tentativa: corrigido na tarefa 39 (TS-5457).
  - Falta, com o Pietro: apagar no Azure as roles e os grupos antigos, os das telas removidas e os de
    "Formalização (unidades)", e a variável `CFG_ACCESS_CONTROL_GROUP_ASSIGNMENT_ENABLED` do Parameter Store.
- **Status (21/10):** **em produção desde 21/10, 19:29** (conferido no argocd e nas `master`):
  - front: PR #233 mergeada (`f7bb2d84`), tag `prod-f7bb2d8` nos três deploys;
  - BFF: PR #220 mergeada (`bb877db`), tag `prod-bb877db`;
  - antes do BFF: TSE #305 (`prod-09f63aa`, 19:29) e orquestrador #41 (`prod-766a9dd`, 19:05). O data lake #116
    está na `master` desde 19:25; a subida dele em produção não aparece nos repos locais;
  - rollback: front `prod-71f34a5` primeiro, depois o BFF `prod-ccb8306`;
  - falta: a conferência de produção (7.4 do roteiro) e o pós-deploy (8).
- **Antes (20/10, noite):** release `release/20261021` em montagem, local, sem push: front (épico + 28 + TS-5411) e BFF (27 + TS-5395 + TS-5411). Plano do Pietro: sandbox na manhã de 21/10 e produção na noite de 21/10. O TSE vai à parte (`fix/TS-5411-whitelists-consultas`, sobe antes do BFF). Roteiro na pasta privada (`deploy/roteiro-de-deploy.md`)
- **Depende de:** todas as outras (01 a 23, menos a 16)
- **21/10, manhã:** as `master` tinham andado (TS-5377: pagamentos pelo `lote_id` e modal de CNABs). Merge da
  `master` nas duas releases, com a TS-5377 do front levada a `features/liquidation-batches` e o modal refeito com os
  componentes próprios. Front: `validate.sh` ok (3.498 testes) e smoke ok. BFF: 1.480 testes, as mesmas 8 falhas.
  Commit depois da revisão do Pietro; em seguida, as `-sdbx`
- **21/10 (D104):** a configuração do front passa a vir do Parameter Store pelo Guardian (`entrypoint.sh`), testada numa
  imagem igual à de produção com um Guardian falso (lista fechada, valor recusado, nada no log, e os três casos sem Guardian
  caindo na configuração do deploy). A `-sdbx` do TSE (`fix/TS-5411-whitelists-consultas-sdbx`) está montada: conflito só de
  acréscimo em `/v1/products`, e as mesmas falhas da `sandbox` pura
- **21/10 (D105):** padrão do Parameter Store e `scripts/parameter-store/` (manifesto, doc e `ps.sh`) no front e no BFF,
  testados com uma AWS falsa (nenhum valor nos argumentos de processo). Na sandbox do BFF: 57 nomes no formato antigo, 1
  duplicado (`CFG_USER_SERVICE_TOKEN`), um segredo gravado sem criptografia, e faltam o certificado e a chave
- **21/10, commits (locais, sem push):**
  - front `release/20261021`: `dac4aa3b` (merge da master), `2c977cc0` (Guardian), `bfb6ca6d` (manifesto e `ps.sh`);
    `release/20261021-sdbx` = `8d399b99`, merge da `sandbox` sem mudar arquivo (a `sandbox` tem o conteúdo da master);
  - BFF `release/20261021`: `01650ad` (merge da master), `058b2f1` (sai o provedor de login antigo, D106), `ba4e142`
    (manifesto e `ps.sh`); `release/20261021-sdbx` = `a6dc857`, com a TS-5228 da sandbox (`instance` só com o caminho)
    e sem a role de bypass da TS-5270;
  - TSE `fix/TS-5411-whitelists-consultas-sdbx` = `44a01da`.
  - `fix(TS-5394)` no `ps.sh` das duas releases (`07dda33` no BFF, `52e84c2c` no front), levado às `-sdbx`: a AWS CLI
    não lê `--cli-input-json` de pipe; o valor vai num arquivo 600 em `/dev/shm`, só durante a chamada.
- **21/10, sandbox:** Parameter Store do BFF e do front prontos (`check: ok`; 49 nomes migrados, o duplicado resolvido, 2 sem
  uso apagados; o secret e o provedor de login antigo ficam até o fim do ciclo). PRs para a `sandbox` abertas: TSE #304,
  BFF #218, front #230. Falta o Pietro mergear, trocar as tags no argocd e validar (6.3)
- **21/10:** mensagens de log do BFF e do front em inglês (`052e27d` no BFF, `84cbac52` no front), como os outros serviços;
  as mensagens ao usuário seguem em PT-BR. Levadas às `-sdbx` e às PRs
- **21/10, primeira subida na sandbox:** o BFF novo morria por falta de memória (usa ~128 MiB, o limite era 128 MiB,
  igual em produção); recursos do BFF passam a 256/512 MiB e 100m/500m de CPU (sandbox agora, produção no deploy da noite).
  O Guardian do front funciona no pod, mas entrega os valores entre aspas: correção no `entrypoint.sh` (`e426aca9`, PR #231)
- **21/10, rodada de correções na release (front):** 5 pacotes por agentes ([brief](../attachments/agents/brief-release-21-10.md)):
  - sai "Hoje na sua operação" da home;
  - o contador de produtos vai para fora da tabela e volta a contar a busca;
  - o carregando do Consolidado de Caixa segue o padrão das tabelas;
  - a Conciliação de Estoques deixa de chamar uma rota que não existe no BFF e mostra um aviso no lugar;
  - zero avisos no build;
  - as tabelas do Envio de Relatórios encostam no cartão, como no Pré-Trade e nos Lotes.

  Estado: aplicadas na release, sem commit, com a validação completa rodando.

  Ficaram para decidir:
  - a tabela de agendamentos não cabe a 1440 px com o menu aberto (faltam 195 px);
  - as colunas da visão "Por parceiro" não se alinham entre os grupos.
- **21/10 (TS-5193):** a área do Orquestrador refeita pelo dev (aba Visão do produto e Execuções por produto) é portada para
  a base nova e entra no deploy da noite ([brief](../attachments/agents/brief-5193.md)). As PRs dele não são mergeadas.
  - O BFF chama rotas novas do serviço de orquestração, que só existem numa PR aberta desse serviço.
  - Essa PR precisa subir na sandbox e em produção antes do BFF.
  - Feito: front e BFF portados, validados e nas PRs para a sandbox (front #232, junto das correções; BFF #219). Entra no deploy da noite (D107).
- **21/10 (TS-5129):** a aba de ativos pendentes da Conciliação de registros, feita por outro dev na estrutura antiga
  (front e BFF), é portada para a base nova ([brief](../attachments/agents/brief-5129.md)).
  - O BFF do dev exige 4 variáveis novas para a consulta à registradora. No porte, elas ficam opcionais.
  - O pré-aquecimento do cache roda em cada réplica; o porte o trava a uma réplica por dia.
  - Entra no deploy da noite (D107). As variáveis da registradora vão para o Parameter Store da sandbox e de produção.
  - Feito: front e BFF portados, validados e nas PRs para a sandbox (front #232, BFF #219). O BFF chama uma rota nova do
    serviço do data lake, que só existe numa PR aberta desse serviço; ela sobe antes do BFF, como a do orquestrador.
- **21/10, testes sem falha:** as 8 falhas antigas do BFF (testes da conciliação desatualizados desde 21/09) foram
  corrigidas. Front com 4.298 testes e BFF com 1.787, nenhum falhando. O TSE está sendo conferido no ambiente completo.
- **21/10, conferência no Datadog (produção, ~1 h depois da subida):**
  - BFF: logs em JSON com `evt.name` e `http.request_id`. 413 requisições: 373 ok, 19 × 401 (sessão vencida, esperado
    com o login de novo), 18 × 499 (chamada cancelada pelo navegador) e 3 × 504;
  - os 504 são timeouts do orquestrador na Visão do produto (19:37). As 4 rotas de `product-analytics` levam de 6 s a
    23 s na mediana e chegam a 60 s. O resto do portal fica abaixo de 5 s, com o controle de acesso de 1 s a 5 s;
  - migração das permissões (20:22): 23 ok, 9 já existentes e 2 falhas ("Permission being assigned was not found on
    application"). As duas atribuições eram de roles criadas no mesmo lote, antes de o Azure propagar. Refeitas às
    20:25 e 20:26, com sucesso;
  - RUM: 12 sessões nas três marcas, `env:production`, versão nova, nenhum erro (nenhum `[Report Only]`); ações com o
    nome mascarado ("texto da tela omitido");
  - front: os erros do nginx são só avisos de subida e desligamento, gravados como erro. A mensagem do log de acesso
    do nginx segue em PT-BR ("Requisição HTTP concluída", `nginx.conf:62`), fora do commit dos logs em inglês;
  - TSE, orquestrador e data lake: na versão nova, sem padrão de erro novo. O que aparece como erro são o progresso
    do download do Guardian e linhas INFO gravadas na saída de erro, como antes do deploy;
  - **nenhum monitor do portal no Datadog** (busca por nome e serviço): os da seção 4 do roteiro não foram criados;
  - fora do deploy: o event bus do TSE reinicia a cada 2 a 3 minutos desde antes da subida, e o TSE grava variáveis
    de ambiente no log (`[DEBUG] NOME=valor`). Os valores não foram abertos.

## O que é

1. **Atualizar tudo com a master.** Juntar as branches do épico com o que
   tiver entrado na `master` até o dia. O que chegou nesse meio-tempo é
   levado para o padrão novo, como a 08 fez com o `e4e13a5`. Os conflitos
   conhecidos usam os scripts de `$PRIV/resolucoes/`.
2. **Normalizar as variáveis de ambiente**, nos repos de deploy (argocd) e
   nos segredos:
   - **front:** `ENVIRONMENT` (14), `API_URL`/`API_UPSTREAM` (a CSP da 18 tira
     a origem do BFF do `API_URL`) e `THEME_KEY`;
   - **BFF:** a configuração da atribuição a grupo (19) e as do Graph, se a
     escrita entrar;
   - **observabilidade (22):** as chaves do RUM no `env.js` do front
     (aplicação, client token, `env`, versão e amostragem);
   - inventário dos **nomes** que o código lê × os que cada ambiente tem.
3. **Liberar as permissões do Graph para o app do BFF** (D18). A lista e o
   porquê de cada uma estão na tarefa 19, em "O que foi feito: BFF".
   - Pedir à infraestrutura:
     - `Application.ReadWrite.OwnedBy`, `AppRoleAssignment.ReadWrite.All`,
       `Group.Create` e `GroupMember.ReadWrite.All`, com consentimento de
       admin;
     - pôr o service principal do BFF como dono do próprio app
       registration.
   - Proteger a credencial do app, de preferência com um certificado,
     porque a `AppRoleAssignment.ReadWrite.All` deixa o app dar privilégio
     a si mesmo.
   - Testar na sandbox, com o lote da 19:
     - as buscas;
     - criar role e grupo;
     - atribuir e remover;
     - apagar grupo do app sem a `Group.ReadWrite.All`. Se não der, decidir
       entre pedir essa permissão ou apagar grupo pelo portal do Azure.
   - Ligar a `CFG_ACCESS_CONTROL_GROUP_ASSIGNMENT_ENABLED` só depois de a
     infraestrutura confirmar a licença Entra ID P1/P2 (D17).
4. **Normalizar roles e grupos do Azure**, a partir do catálogo do BFF
   (19/21):
   - criar as roles novas (`api-docs:read`, `design-system:read`,
     `access-control:read/write` e as da 21);
   - reatribuir;
   - tirar as que sobram.
5. **Release:** criar a `release/AAAAMMDD`, subir para o ambiente, validar e
   fazer a GMUD de produção (skill `criando-gmud`).

## Segredos: rodar os scripts do Pietro sem ler os valores

**Onde estão:** em `~/bashes`. As variáveis ficam no AWS Systems Manager
Parameter Store:
- `list-parameter-store`, `diff-parameter-store`, `create-parameter-store`
  e `delete-parameter-store`;
- `params`, um arquivo de dados que deve ter parâmetros e valores. **Ninguém
  abre esse arquivo**, e ele entra na trava;
- fora do escopo: `generate-codeartifact-token`, `rot-crypt`,
  `clear-docker` e `hello-pietro`.

Em 16/10 só os nomes foram listados, sem abrir nem executar nada. O formato
da saída (para o wrapper) sai do código dos scripts `list` e `diff`, lido
depois de a trava estar ligada. Se o código tiver algum valor embutido, a
leitura passa por uma máscara.


Os scripts do Pietro leem e gravam variáveis de verdade. Para eu usá-los sem
ver valor nenhum:

1. **Wrapper próprio** (`attachments/scripts/env-without-value.sh`):
   - roda o script do Pietro com a saída inteira redirecionada para
     `$PRIV/env/<repo>-<ambiente>.raw` (permissão 600), sem passar pela
     tela;
   - imprime só o nome de cada variável, se está presente ou vazia, e se o
     valor é **igual ou diferente** entre ambientes, por classe (A, B, C…);
   - nem hash do valor aparece;
   - o valor só aparece para as chaves de uma lista aprovada pelo Pietro,
     que não são segredo (ex.: `THEME_KEY`, `ENVIRONMENT`, `PRODUCTION`).
2. **Trava:** um hook `PreToolUse` no Claude Code nega qualquer comando que
   leia `$PRIV/env/` ou o `~/bashes/params`, exceto o wrapper.
3. **Gravar:**
   - valor que não é segredo (ex.: `ENVIRONMENT=sandbox`): eu passo para o
     script;
   - segredo: o Pietro digita no próprio terminal (`! comando`) ou num
     arquivo que só ele edita.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D40 | Ambientes | (a) sandbox, validação com login real e, depois, produção com GMUD; (b) só sandbox agora | (a), em duas etapas |
| D41 | Valores visíveis | (a) nenhum; (b) só a lista aprovada de chaves que não são segredo | (b) |
| D42 | Trava com hook | (a) sim; (b) só o wrapper | (a) |
| D43 | Normalização no Azure | (a) pela tela da 19, depois do passo 3, que libera as permissões do Graph; (b) pela CLI do Azure, com o login do Pietro | (a), com (b) como plano B, se o consentimento atrasar |

## O que foi feito: release (16/10/2026)

Decisão do Pietro em 16/10: juntar tudo numa release agora, criar o
refinamento visual (25) a partir dela e subir no ambiente. A master não
andou desde a base do épico (front `576957c`, BFF `946dce3`).

**Front: `release/20261016`**, da `origin/master`, com um merge por tarefa,
sem push:

| Merge | Tarefa |
|---|---|
| `21bbe3c5` | 13 (com as áreas 01 a 15) |
| `78265657` | 17 |
| `a5d19b60` | 23 |
| `40deaff0` | 19 |
| `5a6f36dc` | 21 |
| `0005b5eb` | 18 (script de resolução) |
| `5bb1d0e9` | 20 (script) |
| `9f08ddb2` | 22 (script) |

- A árvore é igual à da junção validada (`f32dce27`). Só muda uma linha:
  o spec do erro sai da lista de legado do `check-patterns`.
- A validação completa da junção vale para ela: 2.213 testes, audit 0 e
  smoke em 9 rotas.
- `check-patterns` limpo e `tsc` 0.

**BFF: `release/20261016`**, da `origin/master`, sem push:

| Merge | Tarefa |
|---|---|
| `0368282` | 14 |
| `9f827bc` | 15 |
| `6669c9e` | 19 (script) |
| `f62ed98` | fix da 21 |
| `082f47d` | 21: a 14 e a 15 entram no catálogo |
| `65d07de` | 22 |

O que a junção do BFF pediu além do conflito de texto (scripts
`bff_feature_TS-5391-…` e `bff_feature_TS-5392-…` em `$PRIV/resolucoes/`):
- **21 × 14 e 15:**
  - a 21 tirou o `check_authorized_roles`, que a rota do OpenAPI da 14 usa,
    e ela quebraria na importação. Passou ao `require("api-docs", read)`;
  - os escopos `api-docs` e `design-system` entraram no catálogo, e as
    telas `/api-docs` e `/design-system` entraram na lista de rotas da 21;
  - os testes do fix da 21 ganharam a configuração que o `require` lê.
- **22 × 21 e fix:**
  - imports dos dois lados;
  - a indexação na Base de Conhecimento fica com a medição da 22 e o
    usuário que o fix passa;
  - o log de sucesso do PATCH sai;
  - os testes do fix trocam o transport observado da 22.
- **Resultado:** 955 testes, com as mesmas 8 falhas da base; ruff igual à
  master (9 avisos antigos).

**21 sem a transição (D59):** juntada de novo nas duas releases.
- **Front:** `082111a5`, sem conflito.
- **BFF:** `ad5b142`, com os imports dos dois lados. Os testes do fix usam
  `poli-chat:read`, e sai a configuração que eles ligavam.
- **Resultado no BFF:** 927 testes, com as mesmas 8 falhas da base.

**Refinamento:** `refact/TS-5395-refinamento-visual`, criada da release do
front e atualizada com ela.

**Subir na sandbox (só depois da validação local, D58):** pelo fluxo da empresa, uma cópia da release junta a
`origin/sandbox`. O teste (16/10) mostrou:
- **front:** conflito em 5 arquivos do fechamento de lotes. É a TS-5377
  (fechamento assíncrono do lote fake, 2 commits) e a TS-5211 (1 commit),
  que estão na sandbox e não na master. Elas foram escritas na estrutura
  antiga e precisam ser levadas à `features/liquidation-batches`, como a 08
  fez com o `e4e13a5`;
- **BFF:** conflito em 2 arquivos (`exceptions_handlers.py` e o viewer do
  pré-trade), da TS-5377 e da TS-5228.

## Migração das permissões (D59, 16/10)

Sem a transição, a ordem no deploy é:
1. sobe a release;
2. logo em seguida, alguém com `access-control:write` abre a aba Migração da
   tela da 19 e aplica o plano: cria as roles novas e copia as atribuições;
3. quem recebeu entra de novo no portal para a role chegar à sessão;
4. as roles antigas aparecem como "sem uso no código" na aba Permissões e
   são apagadas pela tela.

**Antes do deploy:**
- as permissões do Graph (passo 3), para a tela gravar;
- a **D56** (admins): sem a transição, quem só tem `admin:update` perde o
  dry run e o "Enviar agora", e quem tem `admin:read` perde o re-executar
  do orquestrador. A migração precisa dar `admin:test`, `admin:run`,
  `admin:approve` e `admin:reprocess` a quem for decidido;
- avisar as áreas da janela sem acesso entre os passos 1 e 3.

## Pendência vinda da 25 (19/10)

- **Seletor de marca:** pôr `BRAND_SWITCHER: "true"` nos `values.yaml` do sandbox e do staging do
  front, no repo de deploy. Em produção, a variável não entra.
- **`PRODUCTION`:** nenhum ambiente define essa variável hoje, e o `env.js` diz `production: false`
  até em produção. Vale decidir se ela entra nos três `values.yaml` de produção.


## Pendência vinda da 26 (19/10)

- **Pedido à infraestrutura (D60), antes do deploy do controle de acesso:**
  - atributo booleano no usuário do Azure dizendo se a pessoa tem acesso ao portal, e quem liga;
  - grupo dinâmico com a regra sobre esse atributo (exige Entra ID P1; é a mesma licença pendente
    da D17, de atribuir permissão a grupo);
  - o id do grupo em `CFG_ACCESS_CONTROL_PORTAL_USERS_GROUP_ID` nos `values.yaml` do BFF (sandbox,
    staging e produção). Sem a variável, a aba Pessoas cai na busca no diretório, como hoje.
- O BFF passa a usar o Redis que já tem para o cache do controle de acesso (5 min); nada novo a
  configurar.
- **Licença:** a infraestrutura confirmou a Entra ID P1 (19/10). O grupo dinâmico (D60) e a
  atribuição de permissão a grupo (D17) estão liberados pela licença.

## Pendência vinda da 27 (19/10)

- **Perguntas à infraestrutura** (lista completa em [27](27-organization-and-client.md#perguntas-para-a-infraestrutura)):
  como o `org_type` e o `internal_client_id` são gravados no usuário e como chegam ao token, e se o
  app do BFF pode receber `User.ReadWrite.All`.
- **Variáveis do BFF após a PR 2 (TS-5425)** (sandbox, staging e produção): substituir
  `CFG_ACCESS_CONTROL_ORGANIZATION_ATTRIBUTE` e `CFG_ACCESS_CONTROL_CLIENT_ATTRIBUTE` por
  `CFG_ACCESS_CONTROL_INSTITUTION_GROUPS`, JSON com `group_id`, `organization` e `client_id`.
  Usar os object ids dos grupos de cada ambiente, incluindo o da organização interna (D122).
  Conferir uma única instituição por pessoa, os valores das claims e a troca de grupo no sandbox.
  Não há organização padrão: quem não tem grupo não entra no portal.
  `CFG_ACCESS_CONTROL_REQUIRE_PARTNER_SCOPE` só depois de acertar quem está sem organização ou cliente (D67).
