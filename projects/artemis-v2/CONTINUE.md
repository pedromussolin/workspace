Status: em andamento
Data: 26/11/2026
Tags: artemis, v2, liquidacao, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`. Os valores reais (hosts, usuários de banco, nomes por trás dos análogos) estão no arquivo local `~/.config/workspace/private/artemis-v2.md`.

Este arquivo foi montado em 26/10/2026 a partir do status do `README.md` e do histórico de commits da pasta. O que aqui não está escrito, o README e o histórico não dizem: confira antes de afirmar.

## Onde parei

### 26/11/2026

**Conferência das 11h (fechamento por horário e recuos):** em
[evidence/scheduled-closing-production-2026-11-25.md](evidence/scheduled-closing-production-2026-11-25.md).
**[C]** Rodada das 20:45 de 25/11 do 15 sem nada a fechar, em 1,9 s (consulta das chaves em 1,8 s).
**[C]** Cessão em `prod-c6f88ce` desde 25/11 21:57 UTC (release de 25/11 de outro dev), sem mudança
no fechamento. **[C]** Achado: o beat para ~16 min às 12:00 UTC (09:00 de Brasília) depois de enviar
a `contrato_registro_baixa_task`, em 25 e 26/11; a ocorrência das 12:00 do backstop vira perdida.
Proposta de card. **[C]** 128 recuos de 25/11 21:10 a 26/11 14:00 UTC, todos por trava: 78 numa
rajada de uma remessa do 1637, 46 no 80 e 4 no 15; nenhum no 713.

### 25/11/2026

**Passagem de chat (25/11, 19h, fechamento):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261125-fechamento-horario-e-recuos.md`
(acompanhamento do fechamento por horário e recuos do lote aberto). Nesta iteração: rodadas de 25/11
e linha de base da VM em
[evidence/scheduled-closing-production-2026-11-25.md](evidence/scheduled-closing-production-2026-11-25.md);
119 recuos do lote aberto, todos por trava (110 já em lotes concluídos; 9 do 713 esperam o fechamento
de 26/11); D43 escolhida (nova tentativa na entrada e fechamento só do lote aberto), a validar com o
negócio.

**Passagem de chat (25/11, fim do dia):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261125-desenho-live-e-cache.md`. Nesta
iteração, o desenho da TS-5733 ficou pronto para aprovação:
[04-hot-data-and-config-cache-design.md](tasks/04-hot-data-and-config-cache-design.md) (schema `live`
com os dados recentes ou ainda em aberto das quatro listagens, alimentado por gatilhos, e o cache da
configuração ligado na API com recarga por botão). Números de produção em
[listings-and-volume-2026-11-25](evidence/listings-and-volume-2026-11-25.md); decisões em
`decisions.md` (25/11).

**Passagem de chat anterior (25/11):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261125-dados-quentes-e-cache.md`
(desenho do schema de dados quentes e do cache da configuração, em andamento). Nesta iteração:

- TS-5773 em produção e funcionando, pela palavra do usuário. **[C]** A cessão em produção é a
  `prod-d28b83a` (release de 24/11 mais a TS-5773) desde 24/11 21:46. O produto 15 saiu do
  fechamento da VM em 24/11; **[C]** a execução das 17h de 25/11 veio sem o 15 (4, 80, 81, 581 e
  1406).
- **[C]** Fechamento por horário em produção: na rodada das 16:00 de 25/11 o 15 fechou 1 lote, o
  1604 não tinha nada e o agendador não falhou; às 17:00 e às 18:00 o 15 não tinha nada a fechar.
  Ponto de atenção: a consulta das chaves do 15 levou 255 s às 16h e 233 s às 17h (5 s às 18h), com
  limite de 480 s. O worker de fechamento não reinicia desde 24/11 21:48. Linha de
  base da VM (11 a 24/11): o 15 levava 4,3 a 9,8 min por rodada (p50 5,9 min); pelo horário,
  4,7 min. Rodadas, linha de base por produto e pendentes em
  [evidence/scheduled-closing-production-2026-11-25.md](evidence/scheduled-closing-production-2026-11-25.md),
  atualizado a cada rodada.
- **[C]** O travamento da migration de 24/11 não veio da API. Veio de uma sessão manual de um
  usuário pessoal do banco, parada em `idle in transaction` desde 15:06 com uma leitura da
  `produto_config` (amostras de sessão do Datadog). Os encerramentos forçados atingiram a API e a
  própria migration; a trava só saiu quando essa sessão fechou, às 19:35:08.
- Schema quente: decididos um schema próprio no mesmo banco (as tabelas da aplicação estão no
  schema `master`), os últimos 6 meses e a alimentação por gatilhos no Postgres (opção B). A
  TS-5733 vira várias tarefas. Falta confirmar o cache e escrever o desenho.

### 24/11/2026

**Passagem de chat (24/11, 21:45):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261124-pos-deploy-24-11-workers-e-ts5773.md`
(pós-deploy de 24/11, workers da cessão e o TS-5773 do produto 15). Nesta iteração: deploy da
release de 24/11 feito (shared, cessão, BFF e portal, de 18:47 a 19:50); a migration da cessão
ficou presa numa trava da `produto_config` até ~19:35; agendador validado em produção (20:00,
20:30 e 20:45); 1604 e 15 com fechamento por horário; os workers de fechamento, trocados a cada
5 minutos desde ~13/11 por uma variável duplicada, foram corrigidos no argocd; 16 cards em
Concluído.

**Passagem de chat (24/11, 16:30):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261124-janela-24-11-com-ts5925.md`
(janela de produção das 17:30 com a TS-5925 incluída). Nesta iteração: GMUD criada no portal
(GDM-374); conferência das 16h da TS-5612 na sandbox passou; TS-5925 (cadastro e troca da conta
vinculada do fundo pela aba Liquidação, nos três repos) feita, homologada na sandbox e juntada
na release de hoje; argocd de produção preparado sem commit; regra nova na skill `release`.

- 4 PRs de produção abertas (shared, cessão, BFF, portal); GMUD com TS-5612 e TS-5537, viva-production
  fora do deploy, head da shared corrigido (`5e7b2d94a1c8`) e o passo do SQL da TS-5537.
- A4 validado na sandbox (15:00 e 15:30 UTC em sucesso sem `CELERY_CONFIRM_PUBLISH` no beat).
- TS-5612 na sandbox (`sand-4b222d4`); falta conferir às 19:00 UTC que a rotina antiga não disparou.
- Parameter Store de produção da cessão feito (as três variáveis).
- TS-5537 na release (`dd004bf5e`), suíte 6691 passed; SQL para a DBA levar os 19 contratos a `errado`.

**Passagem de chat (24/11, tarde):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261124-ts5612-sandbox-e-deploy-24-11.md`
(TS-5612 na sandbox e deploy da release de 24/11).

- TS-5612 na release: sai a rotina fixa do beat que fechava às 16h todo produto `agendado`; commits
  `7bef8f777` e `8cccc51e8` na `release/20261124` da cessão (só local); PR #2795 da sandbox
  esperando o merge. Suíte: 6689 passed, 207 skipped, 0 falhas.
- Agendador: `CELERY_CONFIRM_PUBLISH` saiu do beat da sandbox (argocd `a1b8c3b`); a prova do A4
  sem ela está pendente (`scripts/a4_despacho.py`, pasta privada).
- PRs de produção: branches prontas na máquina e os 4 rascunhos revisados; falta pôr a TS-5612 no
  rascunho da cessão e na GMUD.
- Produtos: o 15 é o primeiro do Mercato Libero no horário, à mão, depois do deploy; o 1604 liga no
  agendamento novo logo depois do deploy. Tabela de mudanças na pasta privada
  (`migracao-produtos-fluxo-novo.md`).

**Passagem de chat (24/11, manhã):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261124-release-24-11-sandbox-validada.md`
(release de 24/11 com a sandbox validada).

- Sandbox homologada: todos os testes do guia têm evidência na GMUD. A6 no produto 55 (lote 50049
  aprovado antes do corte às 09:14:45, compromisso `manual` registrado, lote em `liquidando`
  esperando o retorno da administradora). A5 no produto 35 por horário às 10:17 (lote vazio 50048
  descartado pela esteira); o log do descarte é DEBUG, então em produção a conferência é pela
  réplica. Produtos de teste de volta a Manual.
- Front da release: o aviso de lote fechado lista só os lotes (TS-5567) e o exemplo da observação
  no aprovar não cita mais uma pessoa real (TS-5571); na sandbox em `sand-4917fe3`.
- TS-5921 concluída: regra no `.ai` do front e do BFF contra nome real de pessoa em texto de tela,
  mock e teste (LGPD), já na master e na sandbox.

### 23/11/2026

**Passagem de chat (23/11, fim do dia):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-deploy-24-11-e-teste-a6.md`
(deploy de 24/11 e teste A6).

- TS-5624 validada na sandbox: a cessão, o BFF e o front estão com a versão nova e o Alembic com a
  CHECK nova. Os horários dos produtos 55 e 24 foram apagados pela tela, e os agendamentos ficaram
  inativos e sem horário. Em Agendado, o último horário não sai.
- GMUD de 24/11 atualizada: correção da TS-5624, Alembic esperado `a4f7c2d9e1b6`, rollback da
  cessão na imagem atual de produção (a TS-5616 subiu em 23/11) e evidências da sandbox. Só falta
  o A6.

**Passagem de chat anterior (23/11, depois das 20h):**
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-horarios-vazios-e-testes-sandbox.md`
(horários vazios da TS-5624 e fim dos testes da sandbox).

- Tarefa 24 validada na sandbox: automático por remessa (54) e por chave (187) abrem o lote vigente
  na chegada e o fecham no fim da remessa, com `recusadas=0` e `ocupadas=0`.
- Também passaram C1 (aviso depois do corte, produto 55), C2 de novo (15 lotes, com `reenvio`), B2
  (esteira de baixa nova no produto 28) e A3 (backstop). A5 não dá pela tela (lote vazio não
  aparece); A6 fica para um dia útil antes das 14h.
- TS-5624: apagar o último horário de fechamento fora do gatilho agendado, na tela, no BFF e na
  cessão, com uma migration nova que aceita agendamento cron inativo sem expressão. Na sandbox por
  PR mergeada; vai na release de 24/11.
- Achados B28, B29 e B30 em `bugs-found.md`.

**Passagem de chat anterior (23/11, depois das 19h):**
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-testes-sandbox-tarefa24-e-avulsos.md`
(testes na sandbox, Tarefa 24 e pagamentos avulsos).

- Testes do guia 13 na sandbox: resumo diário (C2), fechamento manual e por chave (produto 187),
  automático por chave e por remessa (53 e 54, A2) e por horário (24, B1, às 19:00) passaram, com
  envio simulado pela administradora própria.
- Tarefa 24 da TS-5567 antecipada para a release de 24/11: o automático entra no lote aberto (D36).
  Commit na `release/20261124` da cessão e na `-sdbx`; PR da sandbox mergeada; tag do argocd da
  sandbox commitada local, esperando o build.
- D42 pendente: o horário do 24 levou avulsos de 2021 e 2022; regra a validar com o negócio.

**Passagem de chat (23/11, depois das 18h):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-testes-features-e-email-novo.md`
(testes das features na sandbox e e-mail novo).

- Terceira leva da release de 24/11 na sandbox, no ar: e-mail do resumo diário com tabela por
  fundo e produto e link para a tela de lotes (TS-5585, shared e cessão), coluna do fundo
  alinhada na tela de configuração (TS-5624). Variável opcional do endereço do portal criada no
  Parameter Store da sandbox.
- A release da cessão recebeu a master nova e ganhou uma migration de junção (duas pontas no
  Alembic); sem ela o deploy de produção falharia.
- Testes: A1, A4 (dois disparos seguidos na hora), C2 e a tela da configuração feitos. Os testes
  de fechamento (manual, automático, por chave, por horário e remessa) seguem com produtos de
  administradora própria, que só simula o envio.

**Passagem de chat (23/11, fim da noite):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-testes-sandbox-e-cards-parados.md`
(testes na sandbox e cards parados do sprint).

- Segunda leva da release de 24/11 na sandbox: correção do despacho do agendador (TS-5569),
  leitura da chave da baixa (TS-5737) e tela das esteiras (TS-5624, BFF e portal) commitadas,
  mergeadas na release e na `-sdbx`, PRs da sandbox mergeadas e tags novas no argocd da sandbox.
- A1 feito: 5 pagamentos no lote aberto do produto de teste; a linha do lote aberto aparece em
  todas as datas no fechamento, como no desenho do lote aberto.
- Texto do risco do beat corrigido na GMUD.
- Sprint 16.6.41 (16/11 a 30/11): 16 cards em "Tarefas pendentes" sem trabalho desde a planning;
  os 9 da Artemis V2 têm prazo 24/11 e precisam da data da próxima release do sprint.

**Passagem de chat (23/11, noite):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-testes-sandbox-e-correcao-beat.md`
(correção do beat, tela das esteiras e testes na sandbox).

- Beat: a execução perdida tem causa comprovada: o despacho reaproveita a conexão com o RabbitMQ,
  derrubada em silêncio depois de ~30 min parada; com a confirmação de publicação o beat trava
  ~16 min. Correção (conexão nova a cada disparo) pronta na TS-5569, sem commit; a confirmação no
  beat de produção saiu da GMUD e do guia.
- Tela das esteiras (TS-5624, leitura na TS-5737): chave da baixa nova e agendamentos da
  liquidação, na release de 24/11; cessão, BFF e portal prontos, sem commit; portal em ajustes da
  revisão visual.
- Massa de liquidação para a sandbox: script privado pronto, nada enviado; a administradora da
  sandbox é real, então os testes que fecham e enviam lote não vão até o fim.

**Passagem de chat (23/11, fim da tarde):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-testes-sandbox-e-tela-config.md`
(testes na sandbox, tela das configurações na TS-5624 e deploy de 24/11).

- GMUD da release de 24/11 em rascunho: [gmud-release-20261124.md](gmud-release-20261124.md)
  (prioridade High, três marcas do portal na mesma versão, cuidado com o `viva-production`).
- Guia de testes e de ligar por produto:
  [tasks/13-post-deploy-switch-on-guide.md](tasks/13-post-deploy-switch-on-guide.md).
- Sandbox: uma execução do backstop (17:00 UTC) publicada e nunca consumida; hipótese de publicação
  sem confirmação numa conexão ociosa. `CELERY_CONFIRM_PUBLISH=1` no beat da sandbox (argocd
  `0e7f6e2`); teste nos disparos das 18:30 e 19:00 UTC. Entra no beat de produção no deploy.
- Pietro quer tela para todas as configurações das esteiras da cessão, dentro da TS-5624 (escopo
  e entrada na release a decidir).

**Passagem de chat (23/11, tarde):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261123-homologacao-sandbox-release-24-11.md`
(homologação na sandbox e deploy de produção de 24/11); as anteriores ficam só como histórico.

- Ajustes da revisão da #2782 commitados (referências do planejamento, URL do shared, constantes
  sem import no `constants.py`, `cessao/utils`, rename da modalidade); 18 comentários respondidos.
- D41 feita no shared (`email_dispatch.template_recipients`, migration `9300117a09ae`) e na cessão
  (sem `targets`, sem a `email_destinatario`; 4xx do shared registrado como erro, sem retry).
- As quatro PRs da sandbox mergeadas; tags da sandbox trocadas no argocd, com o worker da fila
  isolada da TS-5737; 14 cards em validação. Resumo de objetos de banco pronto para a DBA.

- Correções 8, 6 e 5 da revisão da #2782 commitadas na `release/20261124` e enviadas na `-sdbx`,
  com a suíte verde nos dois modos e a integração com Postgres e Redis descartáveis.
- D3 decidida (os 6 produtos passam a enviar sozinhos; a volta é o gatilho `manual`) e o legado
  sai depois que o fluxo novo estiver estável. Achado 7 virou a tarefa 26 (TS-5873, backlog).
- BFF: TS-5871 (virtualenv sem a CVE) deixou o Semgrep da #280 verde; as quatro PRs da sandbox
  estão verdes, salvo o Semgrep aceito da cessão e do shared.
- `APL_SHARED_SERVICE_URL` criada na sandbox; em produção não existe e entra na GMUD.
- Revisão do Pietro na #2782 (18 comentários): constantes no `constants.py`, utilitários em
  `utils/`, nomes em PT-BR, referências do workspace fora do código e URL no `config.ini` estão
  prontos sem commit, em patches. Destinatários de e-mail no shared viraram a D41, aprovada e
  por fazer.

### 19/11/2026

**Passagem de chat (19/11):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261119-release-24-11-revisao-correcoes.md`
(CI da release, revisão da #2782, correções e GMUD); a de 18/11 fica só como histórico.

**Revisão da #2782 (cessão), feita junto com a revisão manual do Pietro.** Confirmados os achados
2 (D3), 5, 6, 7 e 8; os outros são intencionais ou só da sandbox. As correções 5, 6 e 8 estão
prontas em worktrees, sem commit, com a suíte verde nos dois modos, e esperam a revisão do Pietro.
A D3 (seis produtos com fechamento automático e `liquidacao_automatico` desligada passariam a
enviar sozinhos) espera a decisão; a recomendação é manter o comportamento de hoje. O achado 7
vira tarefa só no workspace, depois do sim. A D4 deu 0 linhas: o backfill é seguro.

**Release de 24/11 na sandbox: CI corrigida do nosso lado; falta a sandbox.** A montagem e as PRs
da sandbox são de 18/11 (shared #87, cessão #2782, BFF #280, front #317), mas a CI estava vermelha
nas quatro e ninguém tinha olhado. O Pietro: "Não posso subir nenhum deles com testes falhando".
- **Cessão, 41 testes de log:** fora do `ENV=docker` (como na CI), o `logger.config` põe o logger
  `cessao` com `propagate=0` e o caplog não vê nada; a imagem local tem `ENV=docker`, por isso
  passava. Correção: fixture autouse `log_visivel` (padrão de
  `test/database/test_cache_configuracao.py:125`) nos 11 arquivos, um commit por card na
  `release/20261124`. Scripts que imitam a CI: `run-cessao-tests-{release,sdbx}-ci.sh`
  (`env -u ENV`).
- **Cessão, downgrade da TS-5737:** o SQLite da imagem da CI não tem `DROP COLUMN`; o teste
  passou a conferir o `op` simulado, como as outras migrations.
- **Cessão `-sdbx`:** o `amend` do merge de 18/11 tinha desfeito 5 ajustes de teste com a sandbox;
  voltaram na resolução do merge da sandbox nova, sem commit próprio. Suíte da `-sdbx` nos dois
  modos: 7071 passed e 1 failed (o bloqueio abaixo).
- **Front:** `batches.service.ts` fora do Prettier (TS-5582); formatado.
- **BFF:** o lint vermelho é da TS-5848 (Pré-Trade); a correção foi à sandbox pela #281.
- **Semgrep fica como está** (decisão do Pietro): já falhava em toda PR. A release acrescenta um
  falso positivo no `INSERT` da `liquidacao_remessa` (`refact.py`, TS-5572); o CVE novo do
  `urllib3` vale para qualquer PR.
- **Teste da administradora externa** (`test_criar_success`, depende da homologação dela): "Se só
  esse falhar, não tem problema".
- **TS-5283 (outro dev):** a #2784 deixou a sandbox vermelha (`normalizar_cnpj("")` devolve 14
  zeros); o dono corrigiu na #2785 e a `-sdbx` juntou a sandbox nova: 7072 passed no modo da CI.
- **Achados em código de outros devs, sem efeito em 24/11** (nada disso está na master): a
  validação da Dayvale lê a lista inteira na sandbox (partes da TS-5207 e da TS-5498 que só estão
  lá), então o ganho de memória da TS-5737 não aparece na homologação para a Dayvale; o estoque
  (TS-4989, PR ainda aberta) pode, com lote aberto, passar o pagamento pelo lote aberto antes do
  lote do estoque. Vale quando essas branches forem para a master depois de 24/11. Detalhe em
  `~/repos/.artemis_v2/agentes/release-20261124/investigacao-sdbx-5.md`.

### 18/11/2026

**Passagem de chat (18/11):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261118-release-24-11-sandbox.md` (release
de 24/11 na sandbox); a de 17/11 fica só como histórico.

**TS-5624 do front concluída e enviada** (`feature/TS-5624-product-settings-page`, `2c08d916`). A
revisão visual por um agente novo achou 4 desvios (grades da aba Cessão, erro de horário escrito à
mão, tabela da conciliação à esquerda, 12 px a mais no celular); um agente corrigiu e outro revisou
de novo sem desvio. A correção do celular mexeu na barra de filtros de `shared/ui`, com a aprovação
do Pietro. Fica de fora o balão de "Adicionar horário", que repete o texto do botão.

**Ambiente local derrubado.** O ensaio do front está 13 commits atrás da TS-5624.

### 17/11/2026

**Passagem de chat (fim de 17/11):** retomar pela passagem privada
`~/.local/share/workspace/projects/artemis-v2/HANDOFF-20261117-release-24-11-guardas-front.md`
(release de 24/11, guardas de tela do front, TS-5624 refeita e aprovada no navegador, ambiente
local no ar).

**Tudo sobe de uma vez em 24/11.** A TS-5737 entra na release dos 12 cards; a release 2a deixou de
existir (`decisions.md`; `estimate.md` e o checklist de `tasks/13-plan.md` atualizados).

**TS-5737 redesenhada e aprovada** (revisão de 17/11 no topo de `tasks/14-phase0-design.md`):
esteira de baixa nova (refact) ao lado da atual, ligada por produto na coluna
`produto_config.liquidacao_baixa_refact` (desligada por padrão, `PATCH /produto/<id>/`); código em
`cessao/framework/liquidacao/refact_baixa.py`, no padrão do `refact.py`; rodadas por fila de espera
com TTL e dead-letter, sem depender do `consumer_timeout`. D39 decidida; D40: nenhuma administradora
reenvia sozinha; o padrão do nome do arquivo não muda (as administradoras validam).

**TS-5737 commitada e enviada** (`fix/TS-5737-reentrega-segura-baixa`, 17 commits, worktree
`ts5737-cessao`; o Pietro revisa na montagem da release). Inclui a marca de envio na baixa de
registro e de cobrança (5891 passed; integração 44 passed) e testes que valem com a release junta. Suíte inteira: 5850
passed, 0 failed (`run-cessao-tests-master-1112.sh`, que instala a violeta 0.11.18 que a master de
12/11 pede); integração da esteira refact com Postgres 16 e Redis 7 reais: 30 passed; fila de espera
com TTL testada num RabbitMQ 3.13 local. Peças: chave e desvio; `refact_baixa.py` (teto, rodadas com
log no lote, trava por advisory lock em conexão própria, guarda na reentrega, marca de envio, callback
com `event_id` fixo e timeout); caminho em blocos (`is_valid_refact`, `gerar_saida_refact`,
`gerar_file_name_refact`) em dayvale, fydd, genius, CNAB 444, bgt e adm. Q; adm. V fora (sem uso).
Entregas e roteiro do `kill -9` em `~/repos/.artemis_v2/agentes/ts5737/`. B27 registrado.

**TS-5584:** snapshot OpenAPI da shared no BFF commitado e enviado
(`chore/TS-5584-snapshot-openapi-shared`, `x-source` no commit da branch da shared; regenerar sem
`--ref` depois do merge da shared na master). Erros de contrato do OCR e dos lastros não são dela.

**TS-5585:** job do resumo às 20:00 em dias úteis, commitado e enviado (`5c0eb77c4`).

**RabbitMQ de produção:** versão e `consumer_timeout` não conferidos; a conta de desenvolvedor não
lê o Amazon MQ e o endereço do broker só existe como segredo. O desenho deixou de depender disso.

**Ensaio da montagem (fim do dia):** feito nos quatro repos, em HEAD destacada, sem branch nem
push; resoluções gravadas pelo `git rerere`; instruções no checklist de `tasks/13-plan.md`. As duas
quebras que só apareciam com tudo junto foram corrigidas nos cards (TS-5737 `d59b94d86`, TS-5596
`600f379cc`, ambas enviadas). Worktrees `ensaio-release-*` ficaram para consulta.

**Jira:** 12 cards movidos para Em andamento, com a data de início real (plano ou primeiro commit);
TS-5537 segue em validação (não foi para produção). TS-5612 ganhou a promoção do refact da baixa e
os achados (B27, consulta à dayvale, confirmação das administradoras) e saiu da sprint para o
backlog; o prazo (23/12) o Pietro apaga à mão, porque o `ws` não apaga prazo.

### 16/11/2026

**Board pronto.** Sprint 16.6.41 (16 a 29/11) com os cards da release 1, a TS-5737 e os da TS-5705,
todos com prazo. A TS-5565 (passagem da VM) foi para Concluído: passagem feita com o Rafael Frankl,
acesso à VM garantido; a VM segue rodando.

**Release 1 conferida, sem montar** (`ws release branches`, só leitura). A data ainda não está
fechada, possivelmente 24/11. Os 12 cards têm branch no remoto nos 4 repos, nenhuma mergeada nem
atrás da cópia local; todas de 10 a 25 commits atrás da master. Ordem de merge sugerida:
- cessão: 5582 → 5583 → 5569 → 5570 → 5585 → 5567 → 5624 → 5571 → 5572 → 5596;
- shared: 5584 → 5585; BFF: 5582 → 5567 → 5568 → 5624; front: 5582 → 5567 → 5624 → 5571.

**Duas cabeças do Alembic a acertar na montagem [C].** A release 20261112 (mergeada na master em
12/11 à noite, depois das branches) trouxe migrations a partir do mesmo ponto que as nossas:
- cessão: a master tem `c3f8a1d6e2b4` sobre `410aaaf27d06`; a nossa `5d2e8f1a9c47` (TS-5583)
  também parte de `410aaaf27d06`;
- shared: a master tem `b7e1d24c9f30` → `e6a4c82447c4` → `c3f81d5a92e7`; a nossa `c4d8a1f65b27`
  (TS-5585) parte de `b7e1d24c9f30`.

Correção: apontar o `down_revision` das nossas para a cabeça da master no dia da montagem (a
master ainda pode andar até lá). Nenhuma das duas está na sandbox, então nunca rodaram em ambiente.
Os planos já mandavam "conferir a cabeça no dia" (`tasks/13-plan-ts-5583.md`,
`tasks/13-plan-ts-5569.md`), mas o choque com a master não estava registrado.

`[release]` acrescentado ao `config.toml` local (shared → cessão → BFF → front).

### 11 a 13/11/2026

**Pausa para reorganizar o board (13/11).** A gestão pediu sprints definidas, com escopo fechado. O
Pietro vai reorganizar o board do Jira a partir da tabela abaixo; até lá, nada novo começa.

**Estado por card da tarefa 13 (13/11).** Detalhe e prazos em `tasks/13-plan.md`. Release única,
montada só com todos prontos, na ordem das migrations: 5583 → 5569 → 5570 → 5585 → 5567 → 5572.

| Card | Pronto | Falta |
|---|---|---|
| TS-5582 lotes vazios | cessão, BFF e front; branches enviadas | PRs na release |
| TS-5596 limpeza dos vazios antigos | script, simulação, blocos e runbook | revisão da DBA; execução em produção |
| TS-5583 duas colunas | branch enviada (8 commits) | PR na release |
| TS-5567 acúmulo natural | Fase 1, Fase 2 sem migration e remessa (cessão, BFF, front) | Tarefa 24 (automático) foi para a TS-5612 |
| TS-5569 agendamentos em tabela | branch enviada (9 commits, sobre a 5583) | PR depois da 5583 |
| TS-5584 Excel na shared | branch enviada (8 commits) | snapshot OpenAPI no BFF depois da PR |
| TS-5570 horário por produto | completa | PR na release |
| TS-5585 resumo diário e aviso | shared e cessão | horário do job (nasce desligado) |
| TS-5571 aprovação antes do corte | cessão e front | PR na release |
| TS-5624 tela de configuração do produto | cessão, BFF e front | validar a tela no navegador |
| TS-5568 `POST /liquidacao/` no fluxo novo | BFF sem o consolidate | PR; a rota legada sai na TS-5612 |
| TS-5572 automático no fluxo novo | completa | PR na release |
| TS-5620 omnis e lemans_2 sem o Atlas | pipeline do CSV no parser-script (enviado); liquidar no portal (cessão, BFF, front, **sem commit**) | ver abaixo |
| TS-5612 limpeza pós-deploy | lista em `tasks/13-plan.md` | sem sprint até o fluxo novo estabilizar |

**TS-5620 em detalhe.**
- **Liquidar no portal:** a cessão confere produto e estado em rota nova do `refact.py`; BFF e front
  usam. Worktrees `ts5620-cessao`, `ts5620-bff` e `ts5620-front`, **sem commit, esperando a revisão
  do Pietro**. Aberta: trava no Redis contra o duplo clique.
- **Upload de 1109 e 1373:** o arquivo vai do portal ao S3 de dois clientes novos do parser-script,
  que publica uma mensagem por linha no RabbitMQ da cessão com o contrato do datawall (a cessão não
  muda). Parser-script pronto: `feature/TS-5620-liquidacao-csv-padrao`, 4 commits, enviada em 12/11,
  82 testes. A ordem dos campos do JSON foi provada rodando as mesmas versões do datawall (1.10.1
  da linguagem e cheshire 5.8.1), para a deduplicação da cessão casar com a do datawall.
- **Quem grava no S3:** o apl-shared-service (decisão de 12/11). Proposta de 12/11, **a aprovar**:
  (a) origem nova "arquivo enviado" nos fluxos do `report_transfer` do shared, rota
  `POST /flows/upload`, BFF repassa pelo `_post_file` do cliente do shared, botão "Subir arquivo" na
  tela **[recomendo: produto novo vira configuração e o histórico de execuções vem pronto]**; ou
  (b) módulo novo e simples, destinos fixos em variável de ambiente. **[H]** o histórico de execuções
  se prende ao id da tarefa agendada; conferir se o upload cabe sem migration. As linhas recusadas
  pelo parser-script só aparecem no log, não na tela.
- **No deploy:** dois clientes no argocd do parser-script (bucket, SQS e app); variáveis da conexão
  S3 do shared no Parameter Store; `CELERY_BROKER_URL` do parser-script apontando para o RabbitMQ da
  cessão; teste na sandbox com arquivo real de 1109 ou 1373.
- **Data do lote** no portal: em aberto.

**Tarefa 14 (esteira de baixa que não aguenta lote gigante), sem card.** Desenho da Fase 0 em
`tasks/14-phase0-design.md` (12/11; só leitura, nada implementado).
- Decidido: Fase 0 = reentrega segura + arquivo em blocos; teto com 3 rodadas automáticas (15 min,
  1 h, 4 h; da 2ª em diante numa fila isolada) antes de `errado` (seção 3.1).
- Abertas: código fora do `refact.py` (decisão 1 do desenho); envio interrompido, com a proposta de
  consultar a administradora antes de reenviar (decisão 4); ordem do arquivo por `id` (decisão 8).
- **Achado de 12/11:** a rodada de 4 h usa `countdown`, e o Celery segura a mensagem sem confirmação
  até a hora. Se o `consumer_timeout` do RabbitMQ de produção estiver ligado (30 min por padrão a
  partir da 3.8.15), o broker fecha o canal e devolve também as baixas em andamento. Conferir versão e
  limite antes de implementar; recomendo pedir à operação para aumentar o limite.


**TS-5582 em execução (Em andamento no Jira desde 10/11).** D26 = `descartado`; a limpeza dos vazios
antigos saiu para a **TS-5596** (prazo 18/11); BFF e front entraram no card (aviso de descartado na
tela, filtro e cor). Decisões em `decisions.md`; escopo no topo de `tasks/13-plan-ts-5582.md`.
- Worktrees em `~/repos/.artemis_v2/worktrees/` (`ts5582-cessao`, `ts5582-bff`, `ts5582-front`),
  branch `feature/TS-5582-lotes-vazios-liquidacao` a partir da master de 10/11. Tudo implementado e
  testado **sem commit**, esperando a revisão do Pietro (cessão 5.705 testes ok; BFF 4.492 ok; front
  253 da área ok, 2 falhas de layout que já existem na master).
- Instruções e logs dos agentes em `~/repos/.artemis_v2/agentes/ts5582/`.
- Mensagens E1 (ETL, com aviso do estado `descartado`) e E2 (negócio, reescrita sem jargão) prontas
  em `~/repos/.artemis_v2/agentes/ts13-mapeamento/` (fora do repo: nomes reais). Falta enviar.

### 09/11/2026

**Tarefa 13, planos de implementação.** Desenho em `tasks/13-closing-design.md`; índice dos
planos em `tasks/13-plan.md`, um plano por card (`tasks/13-plan-*.md`).
- Revisados linha a linha contra o código: TS-5582, TS-5583, TS-5567 e TS-5569.
- Escritos, com a revisão pausada para poupar tokens: TS-5584, TS-5570, TS-5585, TS-5571,
  TS-5568, TS-5572 e a tela de configuração do produto. A TS-5570 ainda precisa trocar os jobs de
  horário único pela lista `horarios` da TS-5569 (11 jobs mais o do produto 1604).
- Cards criados no Jira: TS-5582, TS-5583, TS-5584 e TS-5585. O da tela de configuração ainda não.
- Decisões de 07/11 e 08/11 em `decisions.md`; pendentes D26 a D30. B26 (lotes vazios) explicado
  em `bugs-found.md`.
- O PC foi formatado em 09/11 e os agentes de revisão pausados se perderam. Retomar com agentes
  novos pelo brief de revisão, na cópia local `~/repos/.artemis_v2/agentes/ts13-plans/`
  (`REVIEW-BRIEF.md`, `BRIEF.md`, `INDEX.md`), restaurada do backup.

### 04/11/2026

**Produção feita (~19h10 às ~19h25, adiantada da janela das 20h, depois do whitelabel).** Detalhe
na `gmud-ts-5536.md` (portal: GDM-352), em "Evidências", item "Produção, execução".
- **Cessão** `prod-579ad13` (`release/20261104`, PR #2743, sem a TS-5537) em `asgard-production` e
  `viva-production`. A migration `c3f81d7a5e24` rodou às 19:20 e foi validada: 156 produtos, 0
  divergentes.
- **Argocd** (merge da `chore/TS-5536-worker-fechamento`): `fake-batch-closing` com 2 réplicas,
  sondas e 4 tarefas por pod, pela `CONCORRENCIA_POR_FILA` do Parameter Store.
- **BFF** `prod-f0511cb` e **Portal** `prod-2ff9802` (`release/20261104-artemis`, PRs #264 e #287),
  nas três marcas.
- **Sandbox antes:** S1, exclusão, S2, S8 e S9 ok. Achado e corrigido: diálogo de confirmação
  largo demais; o `DialogService` ganhou teto de 560 px (PR #287; sandbox pela #288).
- **Do dia:** concorrência por fila no lugar da `CELERY_WORKER_CONCURRENCY` do values (o
  Parameter Store vencia); TS-5537 fora, a pedido do time; scripts da modalidade em
  `attachments/sql/closing-modality-{preview,validate,apply}.sql`; pendências do `viva-production`,
  renomear a coluna da modalidade e variáveis repetidas nos workers em `after-v2.md`.
- **Para o negócio:** resumo em linguagem simples mandado no grupo; a operação acompanha o primeiro
  uso em 05/11.

**Nova frente (noite):** o Rafael Frankl sai da empresa e a liquidação do Mercato Libero que ele
rodava na EC2 de automações vem para a V2. Criada a [tarefa 13](../vm-migration/tasks/13-mercato-libero-settlement.md),
só com o contexto, e a [evidência de 04/11](evidence/mercato-libero-ec2-calls-2026-11-04.md): a
máquina segue chamando a cessão todo dia, com pico às 16h–17h de Brasília. As telas de operações
dele foram para o projeto novo `projects/vm-migration/`, que guarda o inventário
da máquina (tarefa 01 de lá). Recorte da 13, a pedido do Pietro: a V2 cuida do sistema em diante,
com o fechamento automático por horário de corte da tarefa 11 no lugar da varredura, tudo na rota
nova (`refact.py`), inclusive o `POST /liquidacao/` que a varredura chama (migra antes ou junto).
A chegada dos dados fica com o time. Contingência pelo agendamento antigo pendente na D25.

### 03/11/2026

**Decisões do dia** (detalhe em `decisions.md`):
- Todo análogo no `refact.py` substitui o código antigo: (1) roda só na tela; (2) os outros
  escopos (`POST /liquidacao/`, automático, agendado, máquina de estados) passam a usá-lo;
  (3) o legado é apagado. Guarda e correção só no `refact.py`. A migração começa depois da
  semana de testes de tela.
- Código da cessão em PT-BR, inclusive o inglês que já existe no `refact.py` (tradução marcada
  para 04/11; escopo a decidir: só nomes internos ou também rotas, fila, task, chaves do Redis,
  JSON de status e chaves de log).
- Chart do argocd não muda (desligamento fica em 30 s).

**Cards novos:** TS-5536 (listagem, exclusão, busca de pagamentos e worker no fluxo novo) e
TS-5537 (B18), no épico TS-5278.

**Desenvolvido e revisado pelo Pietro (todos os testes passando):**
- **Cessão, `feature/TS-5536-listagem-fluxo-novo`:** listagem nova no `refact.py` (chave pela
  modalidade, `qtd_aptos` pela D9, `GET /liquidacao/fake-batches`); exclusão nova
  (`DELETE /liquidacao/fake-batches`: só pagamentos sem lote da linha, do dia na linha `origem:`;
  `FOR UPDATE` e reconferência; uma transação por liquidação; continua sozinha em tarefas de
  ~400 s; não depende do Redis para terminar; trava da linha compartilhada com o fechamento);
  status do fechamento devolve também a exclusão (`operation`); busca de pagamentos da linha
  (`GET /liquidacao/fake-batches/payments`). Prova de concorrência em Postgres e Redis reais.
- **BFF e front, mesma branch:** usam as três rotas; o Fechar só habilita com apto ("N de M
  registros aptos"); a exclusão manda a chave e o dia; a tela acompanha a exclusão pelo status.
- **Cessão, `chore/TS-5536-worker-fechamento`:** probes por arquivo e `exec` só no worker sem
  consumer; **argocd**, mesma branch: duas réplicas e probes (sobe junto com a imagem da cessão
  ou depois, nunca antes).
- **Cessão, `fix/TS-5537-callbacks-nulos-na-liberacao`:** `callbacks or []` na esteira da cessão.

**Achados:** B23 (excluir pela tela apaga remessas inteiras), B24 (Redis de produção cheio
descartou ~19,7 mi chaves em outubro), origem do B18 (TS-187, de 06/2025; 10 contratos do produto
15 presos) e causa do B21 (lotes nascem vazios no automático). Medição da listagem em
`evidence/fake-listing-replica-2026-11-03.md`: custo igual à antiga.

### Até 26/10/2026

O desenvolvimento da V2 começou em 05/10/2026. O escopo inicial é a tela de lotes de liquidação da platform-cessao, ou seja, o fechamento e a conciliação dos lotes, com a **performance** como ponto principal. A DBA revisa as queries; a parte de aplicação fica com a gente.

Situação das tarefas, pela tabela do `README.md` (última edição em 20/10):

| Tarefa | Situação |
|---|---|
| 01, réplica de leitura | concluída (PR #2628, 07/10; variável no Parameter Store), TS-5279 |
| 03, fechamento mais rápido e assíncrono | em produção (cessão 19/10, BFF e front 20/10), TS-5377; casos e plano de 20/10 em `tasks/03-post-production-cases.md` |
| 12, lotes reais: buscar os lotes antes dos valores | **prioridade máxima** (14/10); mapeada; depende da D21 |
| 02, dois modos de fechamento (chave ou proc_id) | desenho alinhado |
| 04, 05, 06, 07 | mapeadas (a 04 espera a revisão da DBA; a 06 espera a decisão D4) |
| 08, Genius: reenvio e logs de erro | mapeada (revisada em 13/10); depende das D12 a D16 |
| 09, lote automático da Voltis | aguardando dados (configs do produto) |
| 10, fluxo da Genius para a Dayvale | aguardando descoberta (APIs da Dayvale e TS-5207) |
| 11, fechamento por horário de corte | ideia; depende da 02 e da D8 |

O que o histórico de commits registra depois disso (20 a 22/10):

- **20/10, TS-5383:**
  - a premissa da D21 e o SQL foram validados na réplica;
  - publicada só com código, e depois registrada em produção com as primeiras horas;
  - hotfix do detalhe do lote real pelo `lote_id`.
- **20/10, fase 1 da TS-5377 (robustez do fechamento):** a GMUD seguiu pelas releases de 20/10. Com a fase 1 em produção, a GMUD passou a ser retroativa.
- **21/10:** métricas de produção do fechamento e dos lotes reais.
- **22/10:** a GMUD da TS-5377 de 19/10 virou retroativa; a GMUD da fase 1 recebeu o uso em produção e o rollback; a GMUD da TS-5383 recebeu o hotfix do detalhe pelo `lote_id`; as prioridades das GMUDs e o ambiente da Viva na TS-5383 foram registrados; os testes de 22/10 das GMUDs da TS-5377 e da TS-5383 foram registrados.
- **Último commit da pasta (22/10):** status das GMUDs da TS-5377 sem pendência de teste.

As GMUDs estão em `gmud-ts-5377.md`, `gmud-ts-5377-phase1.md`, `gmud-ts-5383.md` e `gmud-ts-5279.md`.

## Branches e worktrees

Worktrees em `~/repos/.artemis_v2/worktrees/`. Cópia do trabalho de 03/11 antes dos commits
(patch e árvore final de cada worktree) em `~/repos/.artemis_v2/agentes/backup-20261103/`
(`arvores.txt` tem a árvore aprovada de cada uma).

**Situação em 13/11** (conferida com `git status` em cada worktree):
- **Enviadas, sem nada local:** `ts5567-{cessao,bff,front}`, `ts5568-bff`, `ts5569-cessao`,
  `ts5570-cessao`, `ts5571-{cessao,front}`, `ts5572-cessao`, `ts5582-{cessao,bff,front}`,
  `ts5583-cessao`, `ts5584-shared`, `ts5585-{cessao,shared}`, `ts5596-cessao`,
  `ts5624-{cessao,bff,front}`, `ts5620-parser` (apl-cessao-parser-script). Estado das PRs não
  conferido.
- **Sem commit:** `ts5620-cessao` (`feature/TS-5620-liquidar-lote-real`), `ts5620-bff` e
  `ts5620-front` (`feature/TS-5620-liquidate-batch`), esperando a revisão do Pietro.
- `preview-front` (`preview/artemis-v2-front`) tem 1 arquivo alterado, fora dos cards.
- Rascunhos dos agentes da tarefa 14 em `~/repos/.artemis_v2/agentes/ts14/`; mapeamento da TS-5620
  em `~/repos/.artemis_v2/agentes/ts13-exec/atlas-omnis/` (fora do repo).

| Repo | Branch | Worktree | Situação em 03/11 (em produção desde 04/11) |
|---|---|---|---|
| cessão | `fix/TS-5537-callbacks-nulos-na-liberacao` | `ts5537` | 1 commit, no remoto |
| cessão | `chore/TS-5536-worker-fechamento` | `ts5536-worker` | 2 commits, no remoto |
| argocd | `chore/TS-5536-worker-fechamento` | `argocd-ts5536` | 1 commit, no remoto |
| cessão | `feature/TS-5536-listagem-fluxo-novo` | `ts5536-listagem` | 8 commits, no remoto (base `8873832dd`) |
| BFF | `feature/TS-5536-listagem-fluxo-novo` | `bff-ts5536` | 7 commits, no remoto (base `3bf3e82`) |
| front | `feature/TS-5536-listagem-fluxo-novo` | `front-ts5536` | 4 commits, no remoto (base `bf378f60`) |

As três `feature/TS-5536-…` partem da `feature/TS-5435-fechamento-por-proc-id` (que contém a fase 2).

O README e o histórico não registram branches nem worktrees. O código da V2 vive nos repositórios da empresa; confira lá a situação de cada branch antes de continuar uma tarefa. Todas as referências `arquivo:linha` do README valem para os commits de `origin/master` de 05/10/2026 listados nele.

## Próximo passo

1. **Schema `live` e cache (TS-5733 em várias tarefas):** aprovação do desenho
   (`tasks/04-hot-data-and-config-cache-design.md`); depois o plano de implementação e os 6 cards
   da seção 10 pelo `/card`.
2. **Travamento da migration:** cards de `idle_in_transaction_session_timeout` nos usuários
   pessoais do banco, de `lock_timeout` na migration e do roteiro com `pg_blocking_pids`.
3. **Fechamento por horário e recuos** (passagem `HANDOFF-20261125-fechamento-horario-e-recuos.md`):
   em 26/11, depois das ~12h, na réplica: os 9 recuos do 713 e os 78 do 1637 no lote, e os vigentes
   antigos; rodadas das 16h e 17h do 15 (consulta das chaves e os 4 avulsos); desenho da D43; card do
   beat parado às 12:00 UTC.
4. **Fechamento da janela:** conferir o comentário da GDM-374; TS-5925 para Concluído; Parte A do
   guia e o resumo diário (C2).
5. **D42 e D43 com o negócio.** Na próxima sprint: B31 e o menu lateral recolhido.
6. **Sem data:** DBA (TS-5596, `EXPLAIN` da TS-5737, resumo diário); TS-5620 (D37, D38); S1 a S14.
