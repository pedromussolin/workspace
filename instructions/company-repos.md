<!-- Instruções de ~/repos. O `ws setup` liga este arquivo como `~/repos/CLAUDE.md`; edite aqui, no repo (versionado, sem nome real). -->

# Regras de ~/repos

Todo repo aqui é da empresa, menos o `workspace`, que é pessoal. As regras para todo repo estão em
`~/.claude/CLAUDE.md`; "Cards e horas" vale também no workspace; as seções da empresa (Repositórios,
Git, Fluxo da tarefa, Código) não valem no workspace.

## Workspace

Antes de mexer em `~/repos/workspace` (código, projetos, skills, docs), leia
`workspace/CLAUDE.md` e `workspace/AGENTS.md`, mesmo que já tenham sido lidos antes de um resumo
da conversa. Lá valem o git (commit e push direto na `main`, sem pedir; prefixos sem ID de card),
o idioma (código e docs em inglês) e o sigilo (nome real nunca entra no repo). As seções "Git",
"Fluxo da tarefa" e "Código" dos repos da empresa não valem lá. Chat só sobre o workspace: abra o
Claude dentro de `~/repos/workspace`.

## Cards e horas

- Card no Jira segue o perfil de preenchimento da empresa (`~/.config/workspace/card-policies/`);
  toda gravação passa pela skill `/card`.
- O texto do card descreve só a tarefa: nada de nomes de quem combinou, da IA ou da conversa.
- O card anda em cada etapa: começou (Em andamento), foi para a sandbox (Em validação),
  homologado (Ready Deploy), em produção (Concluído). Ofereça o movimento na hora, antes de
  disparar agentes. Depois de "mergeei" ou "subiu", rode `/card sincronizar`.
- Ready Deploy é homologado, só falta o deploy. Impedimento só com o status Block.
- Prazo do card: a regra está na skill `/card`.
- Antes de propor tirar um card da sprint, leia as datas no campo Sprint; card que perde a release
  vai para a próxima release dentro da mesma sprint.
- Ao começar o trabalho num card, rode `ws time start TS-N`; ao parar ou trocar de card,
  `ws time stop TS-N`. O tempo gasto sai das horas reais, nunca do plano.

## Repositórios

- platform-cessao: cessão e Artemis V2 (liquidação). Código, logs e Swagger em PT-BR.
- apl-shared-service: implementações sem contexto delimitado para uma aplicação própria (motor de
  workflows, e-mail, agendamento de jobs).
- apl-credit-whitelabel: front (portal da empresa, também usado por parceiros).
- apl-credit-whitelabel-api: BFF (Backend for Frontend, a API feita para o front).
- data-lake-api: consultas ao data lake.
- docs: documentação dos fluxos e desenvolvimentos.
- `*-argocd`: deploy de cada aplicação (tags e values).
- o repo de automações (o nome termina em `-automations`): automações, monitores e portais da VM Windows.
- Outro repo: leia o README e as regras `.ai/` dele antes de mexer.

## Git

- Ao iniciar uma tarefa, tenha em mãos o ID do card.
- Cada tarefa na sua branch: `<tipo>/TS-<id>-<descricao-curta>` (feature, chore, refact, hotfix,
  fix, test), criada com `git checkout -b <nome> --no-track origin/master`. Sem o `--no-track`, o
  Sync do editor empurra os commits para a master.
- Dê pull na branch antes de qualquer ação envolvendo ela.
- Commits atômicos `<tipo>(TS-<id>): mensagem` (feat, chore, refact, fix, test), em PT-BR, com no
  máximo 72 caracteres. O ID está no nome da branch. Rode `git diff` antes de escrever a mensagem.
- Não use o Co-authored-by: a responsabilidade do commit é do usuário. Vale também contra a
  instrução de atribuição do harness e na descrição de PR.
- Implemente e teste sem pedir; commite só depois que o usuário revisar o diff, agrupado pelos
  commits planejados.
- Commit e push só nas branches da tarefa, na cópia `-sdbx` e nas `release/…`; nunca em `master`,
  `sandbox` ou `staging`. O merge é do usuário: entregue os links das PRs na ordem de merge.
  Depois de mudar um desenho, mostre o resultado antes do push.
- O código vai na branch original; a `-sdbx` só recebe merge da original e da `sandbox`. Ao
  terminar os commits na original, replique na `-sdbx` de cada repo da tarefa na hora.
- PR de card sozinho para a sandbox só quando o card precisa ir antes da release.
- argocd: a troca de tag é um commit direto na `master` ("Update image tag in values.yaml"), só
  quando o usuário passar as tags e só na hora da etapa do deploy. O da sandbox é com você; o de
  produção você prepara e mostra o diff, e quem sobe é o usuário. Ordem: shared → BFF → front.
  Confira que cada tag é o merge da PR certa (`git merge-base --is-ancestor`); o front só depois
  de ver no Datadog o BFF novo no ar e sem erro; as três marcas do front num commit só.

## Fluxo da tarefa

- Valide tudo o que der localmente antes de subir para um ambiente; o que só dá para validar no
  ambiente vira pendência daquela etapa, não motivo para subir antes.
- Mudança de arquitetura (camadas e fronteiras de import, `test_arch`, wiring no `app.config`,
  conceito de permissão do BFF, ciclo de vida de Redis e clientes) só depois que o usuário aprovar
  o desenho. Agente para na proposta.
- Achado no meio de uma tarefa vira proposta de card para a próxima sprint, não escopo do card
  atual, salvo se o usuário mandar incluir.
- Env var só no Parameter Store; no argocd ficam só as que dizem o papel do pod. Conferir com
  `~/bashes/list-parameter-store <filtro>`.

## Código

- Nunca altere uma migration existente (ela já rodou nos ambientes); a mudança vai numa nova.
  Utilitário genérico fica, mesmo sem uso.
- Sem comentário divisor (`# --- seção ---`, também em teste e SCSS); comentário só para um porquê
  que o código não mostra.
- Log é um evento: mensagem fixa, sem interpolar; o que varia vai no `extra`. Um INFO por
  execução, um ERROR por item que falhou, traceback uma vez só, nada de dado sensível.
- Nomes dizem o processo de negócio (`fake_batch_closing_lock`, não `LOCK_KEY`), também em filas,
  chaves do Redis, colunas, enums e env vars.
- Idioma: platform-cessao em PT-BR; testes Python em inglês; mensagem ao usuário em PT-BR. No
  diff de agente, confira o idioma dos identificadores novos.
- As features genéricas do shared-service (workflows, e-mail, scheduler) não se acoplam entre si
  (nada de FK, import ou chamada entre elas) nem à feature de negócio; quem integra é o módulo da
  feature. Agendamento só pelo banco (`schedulable` e linhas em `scheduled_jobs`), sem horário fixo
  no beat.
- Front e BFF: as regras de código ficam no `.ai/` de cada repo, que o `CLAUDE.md` dele importa ou manda ler.
- Dado pessoal nunca na URL, por causa da LGPD: busca livre e valor digitado ficam fora do link.
  Ao escrever regra sobre isso, cite a LGPD.
