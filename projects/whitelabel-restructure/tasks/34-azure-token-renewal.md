+++
card = "TS-5429"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 34 — Renovação dos tokens do Azure derruba a sessão antes das 8 horas

- **TS:** TS-5429 (épico TS-5357).
- **Repo:** apl-credit-whitelabel-api (BFF); o front só se o tratamento do erro temporário mudar.
- **Status (26/10):** publicada. `fix/TS-5429-renovacao-tokens-azure` em front e BFF, juntada na release (hoje `release/20261027`)
  e dela na `-sdbx`. Sandbox desde 26/10 (BFF #226, front #239 mergeadas); produção em 27/10 pelas PRs BFF #227 e front #240 (D132);
  o merge fica com o Pietro.
- **Depois do deploy (28/10):** o evento `Azure token refresh rejected` não apareceu nenhuma vez de 26/10 a 28/10, nem na
  sandbox nem em produção, e os 401 do BFF caíram de 65 para 51 nas ~20 h depois do deploy. Não há AADSTS para ler: o
  item 4 fica fechado, e reabre se o evento aparecer.

## Contexto (Pietro, 23/10)

As 8 horas estão configuradas para o cookie e para a sessão no Redis. Durante esse período, os tokens
do Azure precisam ser renovados. Hoje o caminho é:

1. Um token vence e o BFF tenta renová-lo.
2. Se a renovação falha, o BFF responde 401.
3. O front recebe o 401 e manda a pessoa para o login.

Nos logs de produção de 23/10 há recusas 400 do Azure na renovação, inclusive às 17h09, seguidas de
401 do BFF. Isso pode explicar a queda antes das 8 horas.

- **Falta o motivo:** o código registra só o HTTP 400, sem o código específico do erro do Azure.
- **Toda falha vira logout:** qualquer exceção na renovação, inclusive uma falha temporária, leva ao
  mesmo 401.

## Escopo

1. Registrar no `extra` do evento de falha o `error` e os `error_codes` do Azure, o `trace_id` e o
   `correlation_id`; nunca token, refresh token ou e-mail.
2. Separar recusa definitiva (`invalid_grant` e afins: 401 e login) de falha temporária (rede,
   timeout, 5xx: nova tentativa com espera curta e, se persistir, erro temporário que o front não
   trata como fim de sessão).
3. Conferir se duas requisições da mesma sessão renovam ao mesmo tempo com o mesmo refresh token; se
   sim, trava por sessão no Redis e reaproveitar o resultado.
4. Com o código registrado, achar a causa dos 400 (refresh token expirado ou revogado, Acesso
   Condicional pedindo MFA, troca de senha, sessão revogada, configuração do app registration).

## Pronto quando

- A falha de renovação registra o código do Azure, sem dado sensível.
- Falha temporária não desloga; só a recusa definitiva leva ao login.
- Testes: recusa definitiva, falha temporária que passa na nova tentativa, falha temporária que
  persiste e renovação concorrente.
- A causa dos 400 de 23/10 identificada e corrigida, se estiver no BFF ou na configuração do app.

## Regras

As da [32](32-send-by-subflow.md): git do `~/repos/CLAUDE.md`, commit só depois da revisão do
Pietro, Python em inglês, log com mensagem fixa e dimensões no `extra`, validar local antes.

## O que foi feito (23 a 26/10)

O Codex implementou em 23/10, à noite, sem commit; o Claude revisou e corrigiu em 26/10. Worktrees em
`~/repos/.reestrutura_whitelabel/agentes/ts5429/{bff,front}` (branch `fix/TS-5429-renovacao-tokens-azure`,
a partir da `master`) e ensaio da junção com a release em `ensaio-bff` e `ensaio-front`.

**BFF**
- `refresh_tokens` (`src/services/azure/__init__.py`): até 3 tentativas (espera de 0,2 s e 0,4 s) só
  para falha temporária: rede, timeout, 408, 429, 5xx, `temporarily_unavailable` e `server_error`.
  Qualquer outra recusa (4xx) é definitiva. Uma assinatura nova do certificado a cada tentativa.
- Log `Azure token refresh rejected` com `azure_status_code`, `azure_error` (só se tiver cara de código
  OAuth), `azure_error_codes` (o AADSTS), `azure_trace_id`, `azure_correlation_id`, `attempt` e
  `temporary`. Nunca a descrição, o token ou o e-mail.
- Uma renovação por sessão: trava no Redis (`session-refresh:{id}`, 60 s); quem chega depois espera até
  8 s e reaproveita o resultado. A gravação só acontece se a sessão ainda existe e a trava ainda é de
  quem renovou (logout no meio não ressuscita a sessão). Scripts Lua conferidos num Redis 7.4 real.
- Middleware: recusa definitiva → 401 e a sessão é apagada; o resto (inclusive falha do Graph) → 503
  com `Retry-After: 1`, e a sessão continua.

**Front**
- `iam/status`: só o 401 é "sem sessão"; outro erro é propagado. O `authGuard` cancela a navegação e
  avisa ("Não foi possível verificar sua sessão. Tente novamente."), sem mandar para o login.
- `iamGuard` e `plgnGuard`: 401 → login, 403 → `/unauthorized`, outros → cancela (o `iamGuard` avisa).

**Correções da revisão sobre a entrega do Codex**
- O Codex mandava para 503 qualquer 4xx fora de `invalid_grant` e afins (ex.: `invalid_client`,
  `invalid_request`, erro desconhecido). Como o 503 mantém a sessão, a pessoa ficaria presa em erro até
  as 8 horas. Agora todo 4xx é definitivo, como a tarefa pede.
- Resposta 200 sem `access_token` **e** `id_token` também é definitiva (antes virava 503 em loop).
- Parâmetro `refresh_token` sem uso tirado do `refresh_session`; o middleware usa a sessão devolvida.
- Aviso no `authGuard` (antes a primeira carga ficava em branco, sem mensagem).
- Testes novos: 429, recusa sem código, erro que não é código OAuth, falha do Graph, sessão sem refresh
  token, espera de renovação travada, middleware com sessão renovada e sessão sumida, scripts do Redis.

**Commits:** BFF `f2ea469`, `ebd0faa`, `74dc55e` (cada um passa sozinho), junção na release `3871d9e` (com o teste do
"ver como" ajustado) e na `-sdbx` `460aa66`; front `7e93dcbf`, `fde9ccd6`, junção `eb521680` e `-sdbx` `a6a40c70`.

**Validação:** BFF na branch 1818 testes, na release 2096, na `-sdbx` 2098; front `validate.sh` ok com 4814 testes na
release e na `-sdbx`. Antes: ensaiado sobre a `release/20261026`, 2096 testes (o teste do
"ver como" que simulava o `refresh_session` antigo foi ajustado na junção). Front: specs de auth 40/40;
`validate.sh` sobre a release no ensaio.

## Achados nos logs de produção (20 a 23/10, consulta no Datadog em 26/10)

- Renovações com 400 por dia (200 / 400): 20/10 32/34, 21/10 83/26, 22/10 68/52, 23/10 109/45. Nenhum
  5xx ou timeout. Cada 400 vira um 401 do BFF.
- **Não é concorrência:** em 23/10 os 45 400s formam 19 rajadas de requisições paralelas da mesma
  pessoa, e em nenhuma uma tentativa passou e outra falhou.
- **É por pessoa:** algumas pessoas falham na **primeira** renovação de toda sessão, 62 a 70 min depois
  do login, sessão após sessão, sem nenhuma renovação com sucesso; outras renovam dezenas de vezes.
- O pedido do BFF é o mesmo para todos, então a causa provável está no Entra ID para essas pessoas:
  Acesso Condicional (frequência de entrada de 1 hora, MFA ou dispositivo), ou contas convidadas (B2B)
  de parceiros sujeitas à política do tenant de origem. O AADSTS do log novo confirma; antes do deploy,
  o log de entradas não interativas do Entra ID (por pessoa e horário) já mostra o código.
- Os ids das pessoas ficam no `privado.md`, não aqui.
