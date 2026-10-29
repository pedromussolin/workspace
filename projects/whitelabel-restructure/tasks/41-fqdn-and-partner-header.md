# 41 — Serviços internos pelo FQDN e filtro pelo cabeçalho do parceiro

- **TS:** a criar · **Branch:** a criar
- **Status:** **em desenho** (28/10), pelo processo de brainstorming: perguntas, desenho em partes, spec e plano.
- **Decisões de base:** D99 (o filtro por parceiro segue o `X-Identificador-Interno`), D101 (parceiro com vários
  produtos manda todos, separados por vírgula), D102 (o BFF chama os serviços pelo nome interno do cluster) e D103
  (neste deploy, o BFF filtra sozinho; o filtro nos serviços e o FQDN ficam para depois).

## Objetivo

Cada serviço que guarda dado de parceiro (cessão e TSE) mostra ao parceiro só os produtos dele, lendo o
`X-Identificador-Interno` que o BFF manda. Hoje quem filtra é só o BFF.

## Por que o FQDN

Pelo endereço público, o gateway de entrada consulta o Heimdall e troca o cabeçalho do BFF pelo produto da conta de
serviço do próprio BFF: o portal inteiro ficaria filtrado como se fosse um parceiro. Pelo nome interno do serviço no
cluster, a chamada não passa pelo gateway.

## Revisão das premissas (28/10)

Em 20/10 a infra disse que o Guarita sobrescreve o cabeçalho do BFF mesmo pelo nome interno. A revisão de 28/10 (só
leitura; relatório na pasta privada, `agentes/fqdn-revisao/relatorio.md`) não confirmou isso:
- **Provável:** o filtro que chama o Heimdall está preso ao gateway de entrada (`context: GATEWAY`, seletor
  `istio: ingress`). Nenhum repo que a busca alcança tem `AuthorizationPolicy`, `PeerAuthentication` ou
  `extensionProviders`. O Istio é instalado por um Terraform fora desses repos, por isso não é "confirmado".
- **Provável:** o chart padrão manda o tráfego de saída dos pods direto (`excludeOutboundIPRanges: 0.0.0.0/0`), sem
  passar pelo sidecar. Pelo nome interno, a chamada do BFF não passa pelo Heimdall.
- **Datadog, 7 dias:** cerca de 83 mil chamadas internas à cessão e ao TSE, nenhuma com 401 ou 403. É indício, não
  prova. Os eventos de auditoria do Heimdall não chegam ao Datadog.
- A "lista de ignorados" citada pela infra é a do Guarita, que vale só no caminho do gateway. Pôr o nome interno nela
  ou na lista aberta do Heimdall não é recomendado: abre o host sem autenticação.
- **Correção ao levantamento de 20/10:** em produção, os charts a partir da versão 2.4.14 não têm o sufixo do
  ambiente no nome do serviço; o user-service e o BFF (chart 2.4.12) ainda têm. Subir o chart do BFF tira o sufixo e
  quebra o front, que chama o BFF pelo nome com sufixo.
- O TSE da sandbox não serve para testar o caminho interno (lá o Istio está desligado); usar a cessão da sandbox ou o
  TSE de staging.

## Perguntas para a infra (o que a evidência não fecha)

1. A listagem dos `EnvoyFilter`, `AuthorizationPolicy` e `PeerAuthentication` do cluster e o listener do pod do TSE,
   filtrado por `ext_authz`: confirma se o Heimdall roda só no gateway.
2. Como foi o teste em que viram o cabeçalho sobrescrito: origem, destino e o nome usado na chamada.
3. Qual "lista" foi citada em 20/10 e qual o tipo do token do BFF.
4. Os eventos de auditoria do Heimdall, lidos direto no pod (não chegam ao Datadog).
5. O modo do mTLS e se aceitam tirar o `excludeOutboundIPRanges` do BFF, caso se queira política por identidade.
6. Quais nomes de serviço existem em produção, com e sem o sufixo do ambiente.

## Próximo passo

Definir o escopo e a ordem (cessão, TSE ou os dois) e as abordagens, com o Pietro.
