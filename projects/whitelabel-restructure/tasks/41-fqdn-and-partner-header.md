# 41 — Serviços internos pelo FQDN e filtro pelo cabeçalho do parceiro

- **TS:** a criar (dois cards: cessão e BFF) · **Branches:** a criar, da `master` de cada repo
- **Status:** **desenho aprovado em conversa** (28/10, D138); este arquivo é o spec para a revisão do Pietro. Depois
  dele vem o plano de implementação.
- **Decisões de base:** D99 (o filtro por parceiro segue o `X-Identificador-Interno`), D101 (parceiro com vários
  produtos manda todos, separados por vírgula), D102 (o BFF chama os serviços pelo nome interno do cluster), D103
  (no deploy de 21/10 o BFF filtrou sozinho) e D138 (este desenho).

## Objetivo

O parceiro vê só os dados dos próprios produtos, e quem garante isso é o serviço que guarda o dado, como no resto da
empresa, não só o BFF. Começa pela cessão; o TSE vem depois, em outra tarefa.

## Como é hoje (conferido em 28/10)

- **O BFF passa pelo gateway.** No Datadog, 7 dias de produção, o BFF chamou a cessão 1.678 vezes, o data lake 530,
  o shared 441, o TSE 308, o orquestrador 219, o ai-service 95 e o product-manager 85, todos pelo endereço público;
  só o user-service (24) vai pelo nome interno. Os endereços públicos da cessão, do TSE, do product-manager e do data
  lake resolvem para o balanceador do gateway do Istio, onde o Heimdall roda.
- **O gateway troca o cabeçalho.** O Heimdall injeta o `X-Identificador-Interno` do token de quem chama; para o BFF,
  é o produto da conta de serviço dele. Prova indireta: as exclusões de lote de 19/10 gravaram um UUID como autor, e o
  BFF não manda esse cabeçalho.
- **Pelo nome interno, provavelmente não troca** (revisão de 28/10, relatório na pasta privada): o filtro que chama o
  Heimdall está preso ao gateway (`context: GATEWAY`), e o chart padrão manda a saída dos pods direto
  (`excludeOutboundIPRanges: 0.0.0.0/0`). O modo "observar" (abaixo) prova com dado real.
- **O BFF já sabe quem é o parceiro.** `src/shared/business/partner_scope.py`: a claim `internal_client_id` do Azure
  é o cliente; o product-manager devolve os produtos do cliente com o `internal_id` (UUID do `Acesso` do produto), que
  é o valor do cabeçalho. A constante `PARTNER_HEADER` já existe; hoje só a Formalização a usa.
- **A cessão não filtra as rotas do portal.** Das 18 rotas que o BFF chama, 16 não identificam o parceiro e confiam
  no `produto_id` que recebem. `GET /titulo/contratos` dá prioridade ao parâmetro sobre o cabeçalho, `GET
  /fundo/produtos` devolve também os produtos de outros parceiros do mesmo fundo, e a exclusão de pagamentos usa o
  `Authorization` como autor quando falta o cabeçalho.

## Desenho

### Cessão: escopo do parceiro nas rotas que o BFF chama

Um helper único (por exemplo `cessao/escopo_parceiro.py`), no molde do TSE:

1. Sem `X-Identificador-Interno`, ou com `X-Org-Type: plgn`: sem escopo, a rota responde como hoje.
2. Com o cabeçalho: separa por vírgula; cada item precisa ser UUID e existir em `produto_acesso`, senão 403. O escopo
   é o conjunto de `Acesso.produto_id`.
3. Produto pedido fora do escopo (`produto_id`, `product_id`, `identificador_parceiro`): 403. Sem produto pedido,
   valem todos os do escopo. O filtro de produto da tela vira um recorte dentro desse conjunto.
4. Item fora do escopo (lote, `proc_id`, chave, contrato): 404, igual a inexistente.
5. Com escopo, o cabeçalho vence o parâmetro.
6. Modo por configuração, `observar` (padrão) ou `aplicar`. Em `observar` o helper decide, registra um INFO de
   mensagem fixa ("Escopo de parceiro avaliado", com rota, se veio cabeçalho, quantos produtos e a decisão no
   `extra`, sem o `internal_id`) e não muda a resposta.

Rotas (a tabela completa, com o recorte de cada uma, está no levantamento de 20/10, seção 4.2, na pasta privada):

| Tipo | Rotas | Com escopo |
|---|---|---|
| Listagem | contratos da cessão, lotes da cessão, lotes fake e reais, pagamentos, rejeitados | produtos pedidos dentro do escopo; sem pedido, o escopo inteiro |
| Por item | CNAB, reenviar, aprovar e rejeitar conciliação, status do fechamento | item fora do escopo: 404 (no status, a chave some) |
| Escrita por produto | consolidar lote, fechar lote fake, excluir pagamentos | produto fora: 403; na exclusão, confere os itens antes de enfileirar (404) |
| Contratos de um parceiro | `GET /titulo/contratos` | o produto vem do escopo; parâmetro de outro produto: 403 |
| Produtos do fundo | `GET /fundo/produtos` | só os produtos do escopo |
| Saldo e extrato da conciliação | conta do fundo, compartilhada | parceiro: 403 (só o portal interno usa) |

Junto: na exclusão de pagamentos, sem cabeçalho o autor deixa de vir do `Authorization`; passa a ser o `Acesso` do
produto.

### BFF: o cabeçalho em toda chamada interna, pelo FQDN

1. **Cabeçalho num ponto só.** Toda chamada do BFF a um serviço interno (cessão, TSE, product-manager, orquestrador,
   user-service, shared, ai-service, data lake) leva o `X-Identificador-Interno` com os `internal_id` do parceiro da
   sessão, separados por vírgula, como o Heimdall faz no gateway. A sessão interna (Poliedro) vai sem cabeçalho.
   Nunca vai para serviço de fora (Azure, Graph, BlueDeck, CERC, S3).
2. **FQDN.** As URLs dos serviços internos (Parameter Store, uma variável por serviço) passam para o nome interno do
   cluster, uma por vez, primeiro na sandbox. Os nomes certos por ambiente ficam na pasta privada (em produção, os
   charts a partir da 2.4.14 não têm o sufixo do ambiente; o user-service ainda tem).
3. **Defesa em profundidade.** O BFF mantém os filtros que já tem. Para parceiro, ele deriva o produto de
   `/titulo/contratos` do escopo, em vez de repassar o que o usuário manda (conferir na `master`; parte disso entrou na
   TS-5411).

### Ordem de entrega

1. **Cessão em `observar`** nas rotas do BFF, com a correção do autor da exclusão. O log mostra o cabeçalho que chega
   hoje pelo gateway (o da conta de serviço do BFF).
2. **BFF**: cabeçalho em toda chamada interna e a troca para o FQDN, serviço por serviço (sandbox, depois produção),
   conferindo no Datadog o host novo, os 4xx e 5xx e a latência. Depois da troca, o log da cessão deve mostrar
   cabeçalho só nas chamadas de parceiro: é a prova de que ele chega intacto.
3. **Cessão em `aplicar`**, depois de uma semana de log sem decisão errada: sandbox, staging, produção.

## Riscos

| Risco | O que segura |
|---|---|
| Ligar `aplicar` antes da troca para o FQDN: o portal inteiro filtrado pelo produto da conta de serviço do BFF | a ordem acima; o log de `observar` mostra o cabeçalho que chega |
| `GET /titulo/contratos` e `POST /liquidacao/` também têm outros chamadores, que chegam com cabeçalho pelo gateway: em `aplicar`, a resposta deles pode mudar | `observar` primeiro; antes de `aplicar` nessas duas rotas, validar com o time (abaixo) |
| Pelo FQDN, ninguém confere o token do BFF | igual ao que o KrakenD e outros chamadores internos já fazem; pergunta 5 para a infra |
| Monitor ou painel do Datadog filtrado pelo host antigo | revisar ao trocar cada serviço |
| BFF da sandbox chama o data lake de staging, que fica em outro cluster | nesse serviço, usar o data lake da sandbox ou manter o endereço público |
| Subir o chart do BFF para 2.4.14 ou mais tira o sufixo do nome dele e quebra o front | fora desta tarefa; anotar para quem mexer no chart |
| A TS-5435 (Artemis) mexe no mesmo arquivo de liquidação da cessão | combinar a ordem de merge |

## Para validar com o time (fora desta tarefa)

O Pietro vai validar se dá para mudar o comportamento destas rotas da cessão, que outros clientes usam:
- `PATCH /titulo/contratos` (publicada no KrakenD) usa o `produto_id` da URL e ignora o cabeçalho: um parceiro com a
  rota liberada altera contrato de outro produto.
- Nas rotas de parceiro (uploads, consulta de baixas, cadastro, cedente, exclusão de títulos, operação), sem
  cabeçalho o identificador vem do `Authorization`; em `/baixa/pagamento` e `/titulo/contratos` o parâmetro vence o
  cabeçalho.
- Antes de `aplicar` em `GET /titulo/contratos` e `POST /liquidacao/`: quem são os outros chamadores (um deles fecha
  lotes cerca de 88 vezes por dia sem identificação) e se a resposta deles pode mudar.

## Perguntas para a infra (não bloqueiam; o log de `observar` responde parte)

1. A listagem dos `EnvoyFilter`, `AuthorizationPolicy` e `PeerAuthentication` do cluster e o listener do pod do TSE,
   filtrado por `ext_authz`.
2. Como foi o teste em que viram o cabeçalho sobrescrito: origem, destino e o nome usado.
3. Qual "lista" foi citada em 20/10 e qual o tipo do token do BFF.
4. Os eventos de auditoria do Heimdall, lidos direto no pod.
5. O modo do mTLS e se aceitam tirar o `excludeOutboundIPRanges` do BFF, caso se queira política por identidade.
6. Quais nomes de serviço existem em produção, com e sem o sufixo do ambiente.

## Testes

- **Cessão** (pytest na imagem do devcontainer): o helper (sem cabeçalho, `plgn`, um produto, dois produtos,
  identificador inválido, modo `observar` sem mudar a resposta) e, por rota, quatro casos: sem cabeçalho igual a hoje,
  com escopo filtrado, produto de fora 403, item de fora 404.
- **BFF**: o cabeçalho vai em toda chamada interna de parceiro, não vai na sessão interna e nunca vai para serviço de
  fora; um teste de arquitetura impede cliente interno novo sem o cabeçalho.
