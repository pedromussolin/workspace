# 33 — "Ver como" outra pessoa (PR 3 da tarefa 31)

- **TS:** TS-5426.
- **Repos:** apl-credit-whitelabel-api (BFF) e apl-credit-whitelabel (front).
- **Status (23/10):** implementação local concluída; revisão e smoke pendentes. Diagnóstico em [31](31-visual-adjustments-and-patterns.md), item A8.
- **Depende da PR 2 (TS-5425):** a organização e o cliente da outra pessoa vêm do grupo de
  instituição (D121, D122). As branches saem das da PR 2 (`feature/TS-5425-organizacao-e-grupos`,
  front e BFF) depois que ela estiver junta e validada: `feature/TS-5426-ver-como`, `--no-track`.

## Decisões

- **D113:** é só leitura. Qualquer alteração fica bloqueada enquanto estiver simulando.

## Desenho (proposta do A8, aprovada na divisão em PRs, D108)

- **Permissão nova** `access-control:impersonate` no catálogo do BFF (`shared/utils/permissions.py`;
  o escopo `access-control` já está na página `CONTROLE-DE-ACESSO` da lista de páginas da PR 2).
- **Sessão:** guarda "vendo como X" com as roles e a organização/cliente de X (lidos do índice do
  controle de acesso, o mesmo da aba Pessoas). Ponto de entrada único: o middleware que põe
  `request.state.user` (`shared/business/users.py:339`). Cuidado com o `refresh_session`, que
  reescreve o usuário e apagaria a troca.
- **Só leitura:** com a simulação ativa, toda escrita (POST, PUT, PATCH, DELETE) responde 403, menos
  a rota que encerra a simulação e o logout.
- **Autoria:** aprovação de lote, envio de relatórios, POLI e auditoria usam o usuário da sessão; com
  a escrita bloqueada isso não acontece, mas os logs passam a ter os dois ids (quem simula e quem é
  simulado), sem e-mail.
- **Expira em 30 min.** Não dá para simular quem também tem `access-control:impersonate` nem
  encadear simulações.
- **Front:** botão "Ver como" no modal da pessoa (controle de acesso), só com a permissão; faixa fixa
  no topo "Vendo como Fulano · Voltar"; ao entrar e ao sair, recarregar a sessão e as ações do
  escopo (o front pergunta as ações ao BFF; não decide permissão).

## Regras

As mesmas da [32](32-send-by-subflow.md) (git, commit só depois da revisão do Pietro, Python em
inglês, logs, `.ai/` do front, validar local antes). Segurança: mexe em sessão, então a revisão é
mais cuidadosa (spec das rotas, teste de que toda escrita é bloqueada simulando).

## Implementado no Codex (23/10)

- BFF `apl-credit-whitelabel-api-wt/34`; front `apl-credit-whitelabel-wt/35`;
  branch `feature/TS-5426-ver-como`. As worktrees incluem as alterações ainda
  não commitadas da PR 2; os commits devem separar essa base da TS-5426.
- Ação exclusiva `access-control:impersonate`, sem substituição por admin.
  Botão no detalhe da pessoa, faixa fixa, botão Voltar e recarga ao trocar a visão.
- Estado de simulação em chave própria da sessão no Redis, duração de 30 minutos,
  preservado na renovação OAuth e removido no logout. Rejeita a própria pessoa,
  alvos com a permissão de simular, escopo inválido e encadeamento.
- Middleware usa o acesso da pessoa simulada e conserva o autor real. Bloqueia
  POST, PUT, PATCH e DELETE, exceto encerrar a simulação; logout continua liberado.
  Ações anunciadas ao front ficam restritas à leitura. Logs carregam os dois IDs.
- Validação: build development, tipos, padrões e lint dos arquivos alterados
  passaram; 126 testes direcionados do BFF passaram (simulação, sessão, catálogo
  de permissões e páginas). Specs do front escritos e compilados.
- Smoke e execução dos specs de navegador pendentes pelo ambiente restrito.
- Sem commits ou publicação; aguarda revisão.
