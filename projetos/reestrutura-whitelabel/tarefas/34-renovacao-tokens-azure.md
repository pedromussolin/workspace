# 34 — Renovação dos tokens do Azure derruba a sessão antes das 8 horas

- **TS:** TS-5429 (épico TS-5357).
- **Repo:** apl-credit-whitelabel-api (BFF); o front só se o tratamento do erro temporário mudar.
- **Status (23/10):** aberta, não começada. Fica fora da `release/20261023`.

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

As da [32](32-envio-por-subfluxo.md): git do `~/repos/CLAUDE.md`, commit só depois da revisão do
Pietro, Python em inglês, log com mensagem fixa e dimensões no `extra`, validar local antes.
