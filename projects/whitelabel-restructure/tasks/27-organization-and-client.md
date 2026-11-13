+++
card = "TS-5407"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
docs = ["27-organization-and-client-plan.md"]

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 27 — Organização e cliente da pessoa no controle de acesso

- **TS:** TS-5407 · **Branch:** `feature/TS-5407-organizacao-e-cliente` (front e BFF)
- **Status:** **commitada e publicada** (20/10). BFF: `e4d4bb6` (B1–B3 juntas: os arquivos misturam as três) e `fa7c287` (bloqueio, desligado). Front: `77cce810` (F1–F3 juntas: o contrato e o Em lote só compilam juntos) e `1d967874` (`.ai`), mais os merges da 26 com a R59 e os testes do seletor (`3e05c4f6`). 3.085 testes no front; 1.159 no BFF (só as 8 falhas antigas; o `pre_trade/test_repository` às vezes falha pela ordem, passa sozinho)
- **Depende de:**
  - **front e BFF:** a 26 (TS-5405). A branch nasce da `feature/TS-5405-controle-de-acesso-ux` de
    cada repo, porque estende a aba Pessoas, o modal da pessoa, o Em lote e a listagem de pessoas
    do BFF;
  - **infraestrutura** (entra na 24): como os atributos chegam ao token, os nomes deles, a permissão
    de escrita em usuários e as variáveis novas do BFF.
- **Junto, na 25 (TS-5395, R59):** a marca do portal sai da organização da sessão, e o seletor de
  marca simula a organização fora de produção. É a mesma regra: quando a organização de alguém muda
  aqui, a marca e a home mudam no próximo login.

## Por quê

Pedido do Pietro em 19/10:

- a marca e o que cada pessoa vê vêm do Azure, que é controlado por nós;
- hoje a organização e o cliente de cada pessoa só mudam no Azure, à mão; o ideal é mudar pela tela;
- a regra tem que ficar num lugar só: nada de `client_id` de parceiro em variável ou no código do
  BFF.

## Como está hoje

- **Origem:** no login, o BFF lê do token do Azure o `org_type` (organização) e o
  `internal_client_id` (cliente) (`src/shared/business/users.py:297-299`). Os dois são atributos de
  cada usuário no Azure; como chegam ao token não está nos repositórios.
- **Escopo dos dados:** com o cliente, o BFF pede ao product-manager os produtos dele e guarda os
  `internal_id` (5 min no Redis, `src/shared/repository/users.py:33-55`). Lotes, fundos e contratos
  são consultados filtrados por `identificador_parceiro` nesses ids. A organização interna (Poliedro)
  não tem filtro e vê tudo.
- **Brecha:** sem cliente, com cliente que não é número ou com o product-manager fora, a lista de ids
  volta vazia, e lista vazia vira consulta **sem filtro**, igual à da Poliedro
  (`src/shared/business/funds.py:33-42`). Um atributo esquecido no Azure expõe todos os fundos a um
  parceiro. Quem não tem `org_type` nem chega a ter sessão: o `User` do BFF exige a organização
  (`src/shared/schemas/users.py`), e o login falha.
- **Organizações do BFF** (`OrgType`): a interna, Dots, Cerys e `client`. A Viva não tem.
- **Licença:** a infraestrutura confirmou a Entra ID P1 (19/10), o que destrava também o grupo
  dinâmico da 26.

## Decisões

- **D64:** a organização e o cliente continuam sendo atributos do usuário no Azure; nada de grupo de
  parceiro com atributo. Pietro: "acho isso melhor ainda".
- **D65:** a tela mostra e muda os dois, no modal da pessoa e no Em lote, pela prévia e pelo apply
  do controle de acesso.
- **D66:** quem muda precisa de `access-control:write` **e** ser da organização interna (o BFF
  confere). A confirmação é digitando o nome da pessoa; virar Poliedro (ver tudo) avisa em
  vermelho. Vale no próximo login.
- **D67:** o bloqueio de quem não tem escopo entra nesta tarefa, desligado, e é ligado por variável
  depois que a aba Pessoas mostrar ninguém sem organização ou cliente.
- **D68:** o BFF escreve no usuário pelo Graph e o login continua lendo o token (abordagem 1). Ler do
  Graph no login (abordagem 2) mexeria no código mais sensível do BFF; tela só de leitura (3) não
  atende o pedido.

## Desenho

### BFF

**Configuração** (só nomes, nenhum dado de cliente):

| Variável | O que é |
|---|---|
| `CFG_ACCESS_CONTROL_ORGANIZATION_ATTRIBUTE` | nome do atributo da organização no Azure (ex.: `extension_<app>_org_type`) |
| `CFG_ACCESS_CONTROL_CLIENT_ATTRIBUTE` | nome do atributo do cliente |
| `CFG_ACCESS_CONTROL_REQUIRE_PARTNER_SCOPE` | liga o bloqueio (padrão: desligado) |

Sem os nomes dos atributos, a organização e o cliente aparecem como "não configurado" e a edição
fica desligada, como já acontece com o grupo dinâmico.

**Leitura:**

- `access-control/people`: cada pessoa vem com `organization` e `clientId`, pedidos no mesmo
  `$select` da chamada que já lista os membros do grupo dinâmico (o Graph só devolve atributo de
  extensão quando ele é pedido pelo nome).
- Filtro novo de situação, `without-scope`: organização vazia, parceiro sem cliente ou com cliente
  que não existe no product-manager.
- Detalhe da pessoa: organização e cliente (id e nome).
- Rota nova `access-control/clients`: clientes do product-manager (`list_clients`), id e nome, com a
  mesma cópia de 5 min no Redis (D63).
- `access-control/settings`: `partnerAttributes` (`not-configured` ou `ok`) e se quem usa pode
  editar (write e organização interna).

**Escrita:** operação nova no `batch/preview` e no `batch/apply`, `set_person_scope` (pessoa,
organização, cliente). A prévia confere:

- quem pede é da organização interna; senão, bloqueada com o motivo;
- a organização é um valor de `OrgType`;
- organização de parceiro exige cliente; a interna não tem cliente;
- o cliente existe no product-manager;
- sem mudança, a linha é pulada.

O apply faz `PATCH /users/{id}` com os dois atributos e apaga a cópia do Redis. Nível de confirmação
`typed` (nome da pessoa); com a organização interna, o aviso em vermelho.

**Bloqueio** (variável ligada): quem não é da organização interna e não tem cliente válido recebe
403 com "Seu usuário não tem um cliente associado. Fale com o administrador do portal.", em vez de
todos os dados. Vale para a dependência que monta os ids do parceiro, para todas as telas que a usam.
Log WARNING de evento, mensagem fixa "Usuário sem escopo de parceiro", com `organization` e `reason`
(`no-organization`, `no-client`, `invalid-client`, `no-products`) no `extra`.

### Front (controle de acesso)

- **Aba Pessoas:** colunas "Organização" (etiqueta com o nome) e "Cliente" (nome; o número no
  tooltip). KPI que filtra "Sem organização ou cliente". Atributos não configurados: as colunas dizem
  "não configurado" e um aviso diz o que a infraestrutura precisa passar.
- **Modal da pessoa:** a organização e o cliente numa pílula ao lado do nome; visão nova
  "Organização" no segmentado, com o select da organização, o campo do cliente buscado pelo nome e
  salvar. Salvar abre o diálogo de mudança direta (prévia, digitar o nome, aviso em vermelho para a
  organização interna, "vale a partir do próximo login"). Sem a permissão, sem ser da organização
  interna ou sem os atributos configurados: só leitura, com o motivo.
- **Em lote:** operação "Organização e cliente": escolhe as pessoas, a organização e o cliente;
  prévia e resultado de sempre.

### Falhas

| Situação | Comportamento |
|---|---|
| Graph recusa a escrita (permissão, usuário removido) | o resultado diz por pessoa; "Tentar de novo" refaz só ela |
| Product-manager fora | a lista de clientes mostra o erro e salvar fica desligado; o cliente aparece só com o número |
| Cliente que não existe mais | "cliente desconhecido" e conta no KPI |
| Sessão aberta | a pessoa continua com a organização antiga até o próximo login; a tela avisa |
| Atributos do AD local sincronizado | o Graph não escreve: a tela fica só de leitura e o resultado explica |

### Testes

- **BFF:** regras da prévia (não interna, parceiro sem cliente, interna com cliente, cliente
  inexistente, sem mudança); escrita no Graph; filtro e contagem de quem está sem escopo; bloqueio
  ligado e desligado para interna, parceiro com cliente, parceiro sem cliente e sem organização.
- **Front:** colunas e KPI que filtra; visão do modal; só leitura pelo motivo; operação no Em lote;
  diálogo com o nome digitado e o aviso em vermelho; smoke em claro, escuro e celular.

### Implantação

1. A infraestrutura responde as perguntas abaixo e passa os nomes dos atributos.
2. Dá ao app do BFF a permissão de alterar usuários.
3. Os nomes entram nas variáveis do BFF.
4. O Pietro acerta quem aparece no KPI "Sem organização ou cliente".
5. Liga `CFG_ACCESS_CONTROL_REQUIRE_PARTNER_SCOPE`.

## Perguntas para a infraestrutura

1. Como o `org_type` e o `internal_client_id` são gravados no usuário: atributo de extensão do Entra
   (`extension_<app>_...`, de qual app registration) ou `extensionAttribute1–15` do AD local
   sincronizado?
2. Como chegam ao token: claims opcionais do app registration ou política de mapeamento de claims?
3. O app do BFF pode receber `User.ReadWrite.All` (aplicação)? É uma permissão forte: altera qualquer
   atributo de qualquer usuário, menos senha. Alternativa de menor alcance, se houver, é bem-vinda.

## Fora desta tarefa

- **Grupo de parceiro com atributo** (proposto e descartado em favor do atributo no usuário, D64).
- **Organização da Viva:** entra no `OrgType` quando a Viva tiver usuários no portal.
- **Login lendo do Graph** (abordagem 2, D68).

## Decisões tomadas na implementação (19/10)

- **BFF:** organização desconhecida (fora do `OrgType`) conta como `no-organization`; cliente só com
  dígitos vale (`""`, `" 12 "`, `"abc"`, `"-1"` são `invalid-client`); com o product-manager fora,
  as leituras não caem (o nome do cliente vem vazio e o número conta como válido) e a prévia
  bloqueia só a linha que precisa de cliente ("Não foi possível consultar os clientes no
  product-manager."); a mesma pessoa duas vezes no lote: a segunda é pulada ("Repetido no lote.");
  o `PATCH` que dá 404 no apply falha a linha. Sem `org_type` a pessoa nem tem sessão, então o
  `no-organization` do bloqueio só vale para o atributo vazio lido pela tela.
- **Front:** escolher a interna esvazia e desliga o cliente; salvar fica desligado sem mudança e,
  para parceiro, com a lista de clientes carregando ou com erro; o aviso em vermelho da interna sai
  em `accessChangeAlerts`; a tabela de pessoas rola dentro dela no celular (`--app-table-min-width:
  900px`).
- **A validar na sandbox:** o `$select` dos atributos de extensão em `groups/{id}/members` e em
  `users` (o fake aceita; o Graph real ainda não foi provado).
