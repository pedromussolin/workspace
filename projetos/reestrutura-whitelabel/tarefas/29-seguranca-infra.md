# 29 — Segurança e alinhamento com a infraestrutura

- **TS:** TS-5411 · **Branches:** `fix/TS-5411-seguranca-bff` (BFF) e `fix/TS-5411-seguranca-front`
  (front), as duas da `master` (`--no-track`), worktrees `apl-credit-whitelabel-api-wt/5411` e
  `apl-credit-whitelabel-wt/5411`
- **Status:** primeira leva **implementada e testada, sem commit** (20/10), esperando a revisão do Pietro
- **Origem:** revisão de segurança de 20/10, antes do deploy (5 revisores, só leitura). O relatório
  com os achados fica na pasta privada (`agentes/seguranca/consolidado.md`), porque descreve falhas
  abertas. Aqui só o plano e o andamento.

## Decisões

D91 (organização e cliente vêm de claims por grupo do Enterprise Application), D92 (grupo estático
de quem acessa o portal) e D93 (app registration só com leitura; avaliar opções mais restritas que
as `*.ReadWrite.All`).

## Primeira leva (20/10)

**BFF:**
- **Autenticação do app por certificado**, no lugar do secret (pedido do Pietro; o certificado já
  está no app registration). Os três pedidos de token (login, refresh e o token do app para o Graph)
  mandam uma *client assertion*: um JWT assinado com a chave privada (PS256, cabeçalho `x5t#S256`,
  validade de 10 minutos, `jti` único). Duas variáveis, cada uma o PEM em base64 (o Guardian lê
  linha a linha): `CFG_AZURE_CLIENT_CERTIFICATE` e `CFG_AZURE_CLIENT_PRIVATE_KEY`. A chave é RSA, sem
  senha, e o BFF confere se ela é a do certificado. Sem volta para o secret: faltando a variável, o
  BFF não sobe. Reescrito na TS-5411, com a branch PEN-2911 (de outro dev) só como referência.
- **`.devcontainer/.env` só com valores locais de mentira** (o arquivo fica): saem credenciais,
  ids do tenant e do app, endereços de sandbox e produção. Os serviços com devcontainer apontam
  para o container local; os outros, para um endereço `.invalid`. Os valores reais vão no
  `.devcontainer/.env.local`, que o git ignora e que vale por cima (config e docker-compose).
- 551 testes passando (15 novos); as 8 falhas são as mesmas da `master`. Ruff e black limpos.

**Front:** sai `src/assets/mocks/` (4 JSON que nenhum código usa e que o build servia sem login).
Build ok.

## Para o deploy

- Parameter Store de cada ambiente: criar as duas variáveis (`base64 -w0 certificado.pem` e
  `base64 -w0 chave.pem`) e tirar `CFG_AZURE_CLIENT_SECRET`.
- Validar na sandbox: login, refresh da sessão e a leitura de app roles (token do app).
- Depois de validado em todos os ambientes: apagar o secret no app registration.
- Trocar as credenciais que já estiveram no repositório (lista na pasta privada).

## Próximas levas (dependem do Pietro)

- TS-5407: trocar a organização de alguém passa a ser trocar o grupo de instituição (D91), sem
  `User.ReadWrite.All`.
- Consertos do BFF e do front apontados na revisão (filtro de parceiro, cookie de sessão, cabeçalho
  `Host`, CORS por ambiente, tokens cifrados no Redis, validação do id_token).
