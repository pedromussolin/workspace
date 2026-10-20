# 29 — Segurança e alinhamento com a infraestrutura

- **TS:** TS-5411 · **Branches:** `fix/TS-5411-seguranca-bff` (BFF) e `fix/TS-5411-seguranca-front`
  (front), as duas da `master` (`--no-track`), worktrees `apl-credit-whitelabel-api-wt/5411` e
  `apl-credit-whitelabel-wt/5411`
- **Status:** leva do deploy **commitada e publicada** (20/10):
  - `fix/TS-5411-seguranca-bff`: 11 commits, ponta `50167bf`; cada commit testado sozinho (589 testes no fim, só as 8 falhas da `master`);
  - `fix/TS-5411-seguranca-front` (da `master`): 2 commits, ponta `034fda89`;
  - `fix/TS-5411-seguranca-front-epico` (da 27): 6 commits, ponta `652a0ede`; cada um compila sozinho, 3.315 testes, lint igual à base.
  Em andamento: o escopo do parceiro como padrão no BFF (D99), o filtro das whitelists no TSE
  (`fix/TS-5411-whitelists-por-parceiro`, opção 2) e o levantamento da cessão.
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

## Leva do deploy (20/10, tarde)

Aprovada a lista "antes do deploy" pelo Pietro; feita por dois agentes, revisada pelo main.

- **BFF:** a sessão decide rota pública pelo caminho real (não pelo `Host`); parceiro só lista lotes
  de liquidação dos próprios produtos; contratos de cessão só de processo do próprio parceiro;
  autor da exclusão de lote pela sessão; cookie `__Host-session_id` só por HTTPS; `.dockerignore`;
  o BFF não sobe sem `CFG_ENVIRONMENT` (o `.env` local só com `LOCAL`); `python-multipart` 0.0.32;
  anexo do pré-trade sempre como download. 589 testes, as 8 falhas da `master` e nenhuma nova.
- **Front (`master`):** sai `src/assets/mocks/`; a exclusão de lote não manda o e-mail do navegador.
- **Front (épico):** o RUM troca o nome de todo clique que o código não nomeou (o dado da célula não
  vai ao Datadog); logout limpa o usuário do Datadog; cookie do Datadog só em HTTPS; o proxy da
  sandbox usa o cookie novo; a mesma correção do e-mail e a remoção dos mocks.
- **Formalização:** em aberto. O product-manager liga o cliente aos produtos (`internal_id`), e o
  TSE usa o mesmo `internal_id` nos produtos dele; a whitelist guarda o id interno do TSE. A
  consulta no banco de produção (feita pelo Pietro) decide se o filtro por parceiro funciona.

**Roteiro de deploy:** escrito em 20/10 na pasta privada (`deploy/roteiro-de-deploy.md`), com nomes
reais. Muda o plano da 24: sem escrita no Graph (D93), a cópia das roles antigas para as novas é
manual (portal ou CLI do Azure), e o rollback depende de o secret e as roles antigas ficarem até a
validação em produção.
