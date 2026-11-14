+++
card = "TS-5392"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 22 — Observabilidade: logs estruturados no BFF e visibilidade no front

- **TS:** TS-5392 · **Branch:** `feature/TS-5392-observabilidade` (BFF e front)
- **Status:** a iniciar (decisões D34 a D39 tomadas em 16/10). Vem antes do deploy (24).
- **Depende de:** 13 (front) e da `origin/master` (BFF). Usa o lote da 19 só
  como exemplo de evento de auditoria.
- **Referência:** o guia de logging da empresa, guardado fora do repo em
  `$PRIV/referencias/guia-logging-empresa.md`. Princípio: log é **evento**.
  - A mensagem é estável.
  - Os dados variáveis viram dimensões estruturadas.
  - O contexto (`trace_id`, `request_id`, `env`, `service`, versão) entra
    sozinho.
  - Estruturado não quer dizer tudo em `extra`: `timestamp`, `level`,
    `message` e os ids de tracing fazem parte do esquema do logger.

## Como está hoje (Datadog, 7 dias até 16/10)

| | BFF (`apl-credit-whitelabel-api`) | Front (`apl-credit-whitelabel-front`, `-dots`, `-cerys`) |
|---|---|---|
| Volume | ~16 mil logs; production, sandbox e staging | ~24 mil, só o log de acesso do nginx, em texto |
| Traces (APM) | sim: ~17 mil spans em production e ~13 mil na sandbox; os logs já levam `trace_id`/`span_id` (ddtrace) | não |
| RUM (navegador) | — | **não existe**: nenhum erro de JavaScript, chamada que falhou ou tempo de tela chega ao Datadog |
| Erros | ~270 | ~1.250, mas **quase todos são `[notice]` do nginx** (worker que sobe ou desce), classificados como erro por saírem no stderr |

**O que atrapalha no BFF:**
- **Logs por requisição:** cada requisição gera dois, "Request GET:/rota" e
  "Response GET:/rota". O método e o caminho vão interpolados na mensagem,
  então não dá para agrupar.
- **Campos:** os nomes fogem do padrão (`levelname`, `asctime`), e as
  dimensões vêm duplicadas num texto `extras`. Não há `request_id` nem quem
  fez a chamada.
- **Interpolação:** 54 das 116 chamadas de log interpolam valores (f-string),
  e só 8 usam `extra`.
- **Mesmo erro em três camadas:** um timeout da Plataforma de Cessão gera o
  erro do cliente, o aviso da requisição e o erro da resposta.
- **Ruído:** a barra de progresso do `curl` do entrypoint (download do
  guardian) aparece como erro.
- **Dado sensível:** o e-mail de um usuário aparece numa URL logada (chamada
  ao serviço de IA).
- **Evento de negócio:** quase não existe. A exceção é "fechamento do lote
  (produto N): falhou...", com o valor interpolado.

## Proposta

**BFF: uma camada central de observabilidade** (`src/services/logging`, que
já tem `dictConfig` e o formatter JSON):
1. **Esquema padrão**, com os nomes de atributo padrão do Datadog para que os
   facets funcionem sem pipeline:
   - `timestamp`, `status`/`level`, `message` e `logger.name`;
   - `service`, `env`, `version`, `dd.trace_id` e `dd.span_id`;
   - `http.request_id` e `usr.id`;
   - as dimensões do evento como atributos;
   - sem o texto `extras` nem `asctime`/`levelname`.
2. **Contexto automático por `contextvars`:** `request_id` (gera ou propaga o
   `X-Request-ID`) e `usr.id`, também em tarefas assíncronas e em
   background.
3. **Um evento por requisição** ("HTTP request completed"), no lugar de dois:
   - campos: `http.method`, `http.route` (o template, ex.:
     `/users/{ecid}`), `http.status_code`, `duration_ms` e o
     `http.request_id`;
   - nível: 2xx/3xx em INFO, 4xx em WARNING e 5xx em ERROR;
   - o `/health` continua fora.
4. **Cliente HTTP de saída** (serviço compartilhado, Plataforma de Cessão,
   serviço de usuários, IA, TSE e Graph):
   - um evento por falha ou repetição, com `peer.service`, método, rota sem
     query, status, `attempt` e `duration_ms`;
   - o sucesso fica só no span do APM.
5. **Exceções:** um handler só, com um ERROR (`error.kind`, `error.message`,
   `error.stack`). A mesma falha não é logada de novo nas outras camadas.
6. **Arquivos e streaming:**
   - exportações (CSV/XLSX, CNAB), download e upload de anexos e o
     streaming do chat têm eventos centrais de início, fim e falha, com
     bytes, duração e provedor;
   - sem log por chunk.
7. **Sanitização num filtro:**
   - e-mail, CPF/CNPJ, token, cookie e `Authorization` mascarados;
   - query string fora da URL logada;
   - corpo de requisição e de resposta nunca entra.
8. **Eventos de negócio**, com mensagem fixa: lote fechado ou falhou;
   pré-trade enviado e decidido; status da formalização alterado em lote;
   onboarding reprocessado; envio de relatório executado ou testado; acesso
   alterado (19). Cada módulo declara os seus.
9. **Migrar os 54 logs interpolados** e ligar no `ruff` as regras de logging
   (`G004` etc.), que barram f-string em chamada de log.
10. **Entrypoint:** `curl -sS`, sem a barra de progresso.

**Front: observabilidade no navegador**, porque o portal não tem servidor
próprio além do nginx:

11. **RUM e Browser Logs do Datadog** (pacotes npm no bundle, sem CDN), num
    serviço `core/observability`:
    - erros de JavaScript pelo `ErrorHandler` global e chamadas ao BFF que
      falharam pelo interceptor HTTP;
    - telas e tempos (Core Web Vitals);
    - `allowedTracingUrls` com a origem do BFF, que liga a sessão do
      navegador ao trace do BFF;
    - privacidade com `mask-user-input`, sem Session Replay e `usr.id` sem
      e-mail;
    - configuração pelo `env.js` (aplicação, client token, `env`, versão e
      amostragem), que vai para a 24;
    - a CSP da 18 libera o intake do Datadog no `connect-src`.
12. **nginx:**
    - log de acesso em JSON, com o `$request_id` repassado ao BFF como
      `X-Request-ID` e o tempo do upstream;
    - os `[notice]` deixam de virar erro: anotação `source:nginx` no deploy
      e/ou `error_log` em `warn`.

**No Datadog** (a escrita pelo MCP não está liberada; criar pela UI ou por
código de infraestrutura):

13. **Facets e uma visão salva** "Portal".
14. **Monitores:**
    - taxa de 5xx do BFF;
    - timeouts da Plataforma de Cessão;
    - falha no fechamento de lote;
    - erros de JavaScript por versão.
15. **Dashboard "Portal: saúde":** requisições, latência por rota, erros por
    `peer.service`, sessões e erros do RUM.

## Testes

- **Formatter:** a saída tem o esquema (chaves, tipos e nenhum `extras`).
- **Middleware:** um evento por requisição, com a rota template e o
  `request_id` propagado.
- **Sanitizador:** e-mail, CPF/CNPJ e token.
- **Cliente HTTP:** a falha vira um evento só, com `attempt`.
- **Front:** o serviço de observabilidade inicia com a configuração do
  `env.js`, não inicia sem ela, e o interceptor reporta a falha sem o
  corpo.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D34 | Front com observabilidade | (a) RUM e Browser Logs, com correlação ao BFF; (b) só o nginx; (c) RUM só de erros | (a) |
| D35 | RUM: amostragem e privacidade | (a) 100% das sessões (portal interno, pouco tráfego), `mask-user-input`, sem Session Replay; (b) com Session Replay | (a). Replay em tela financeira pede outra conversa |
| D36 | Nomes dos campos | (a) atributos padrão do Datadog (`http.*`, `usr.id`, `error.*`, `duration`); (b) nomes próprios, com pipeline de remapeamento | (a) |
| D37 | Requisição | (a) um evento por requisição; (b) manter início e fim | (a): metade do volume e agrupável |
| D38 | Quem fez a chamada | (a) `usr.id` com o `oid` do Azure; (b) e-mail; (c) nada | (a): identifica sem dado pessoal |
| D39 | Alcance | (a) só o portal (BFF e front) agora, com o padrão anotado para levar ao serviço compartilhado depois; (b) já o serviço compartilhado também | (a) |

## O que foi feito: BFF (16/10/2026)

Branch `feature/TS-5392-observabilidade`, criada da `origin/master`
(`946dce3`). São 14 commits, sem push. Cada um foi testado isolado: 549
testes, com as mesmas 8 falhas da base.

**O que entrou:**
- **Esquema do log** (`src/services/logging/formatters.py`):
  - no topo: `timestamp` (UTC, ms, `Z`), `status`, `message`,
    `logger.name`, `service`, `env` e `version`;
  - correlação: `dd.trace_id`, `dd.span_id`, `http.request_id` e `usr.id`
    (o `oid`);
  - as dimensões aninhadas, sem `extras`, `asctime` nem `levelname`;
  - `duration` em nanossegundos (o padrão do Datadog).
- **Requisição:** um evento por requisição, com a rota template e o
  `X-Request-ID` propagado e devolvido. O nível segue o status; o 499 (o
  cliente desistiu) fica em INFO.
- **Chamadas de saída:** passam por um `ObservedTransport`, com
  `peer.service` (13 serviços). Uma falha gera um WARNING, e os logs
  duplicados e os que traziam o corpo da resposta saíram.
- **Exceções:** o handler não loga mais. A falha aparece uma vez só, no
  evento da requisição, com `error.*` e o stack.
- **Arquivos e streaming:** eventos de início, fim e falha, com bytes,
  duração, provedor e operação, sem log por chunk.
- **Sanitização:** mascara e-mail, CPF/CNPJ, JWT, `Bearer`, `token=`,
  `Authorization` e `Cookie`, inclusive em `error.*`, e tira a query
  string das URLs.
- **Eventos de negócio** (`shared/utils/business_events.py` e um `events.py`
  por módulo):
  - fechamento do lote fake;
  - pré-trade enviado e decidido;
  - status das whitelists em lote;
  - reprocessar o onboarding;
  - envio de relatórios (executar, testar conexão e testar fluxo).
- **ruff:** regras `G001` a `G004`, `G010`, `G101`, `G201` e `G202`, com as
  violações de 73 para 0. As chamadas de log no código foram de 135 para 36.
- **Entrypoint:** `curl -fsSL`.

**Volume:**
- uma requisição comum passa de 2 logs para 1;
- o timeout da Plataforma de Cessão passa de 4 para 2, com 1 ERROR;
- a exceção não tratada passa de 3 para 1;
- o 4xx deixa de contar como erro.

**Ajustes feitos** (16 commits, 566 testes, com as mesmas 8 falhas da base):
- **`7909ab5`:** as mensagens dos eventos técnicos em PT-BR, com um
  `evt.name` estável:
  - `http.request` (requisição);
  - `http.outbound_failed` (chamada externa que falhou);
  - `file_transfer.*` (arquivos) e `stream.*` (streaming);
  - `http.unhandled_exception` e `process.unhandled_exception` (exceções).

  Os monitores e o dashboard filtram por `@evt.name`.
- **`f3c7972`:** o `UtcDatetime` (`src/shared/schemas/datetimes.py`) faz toda
  data com hora sair em UTC com `Z` e milissegundos. Vale para:
  - Formalização (whitelists e unidades), liquidação (balance e statement) e
    lotes;
  - histórico do chat;
  - onboarding.

  Cada upstream foi confirmado no código. Os textos `*Formatted` e a coluna
  do xlsx convertem para Brasília. Exemplo: o `createdAt`
  `2026-08-10T13:05:00.123456` vira `2026-08-10T13:05:00.123Z`, e o
  `createdAtFormatted`, `10/08/2026 13:05`, vira `10/08/2026 10:05`.

**Para o RUM do front** (2 commits, 18 no total, 569 testes, com as mesmas 8
falhas da base):
- **`1e70452`:** o `iam/profile` devolve também o `azureId`, que é o `oid` do
  Azure e o mesmo `usr.id` dos logs do BFF. Ele liga a sessão do RUM aos logs
  sem mandar nome nem e-mail (D38). Vem nulo nas sessões gravadas antes do
  campo, até o próximo refresh.
- **`62993e9`:** o CORS expõe o `X-Request-ID`. Só importa quando o front
  chama o BFF por URL absoluta (local); nos deploys, o `/api` é da mesma
  origem.

**Achado à parte:** o path `/real-batches//statement` tem barra dupla
(`viewer.py:444`).

**Para fazer no Datadog, pela UI** (lista completa no relatório do agente):
- conferir o pré-processamento de JSON;
- facets de `http.route`, `peer.service`, `evt.*`, `transfer.*` e
  `error.upstream_*`;
- visão salva "Portal";
- monitores de taxa de 5xx, timeouts da cessão e falha no fechamento de
  lote;
- dashboard "Portal: saúde".


## O que foi feito: front (16/10/2026)

Branch `feature/TS-5392-observabilidade` do front, criada da 17 com o merge
da 18 (`0ea7a527`). São 13 commits, sem push:

| Commit | O quê |
|---|---|
| `11128be0` | chaves do Datadog no `env.js`, geradas pelo `entrypoint.sh` e pelo `generate-env.js` |
| `787ee2cf` | `@datadog/browser-rum` e `@datadog/browser-logs` 7.15.0, com versão exata |
| `4986437d`, `ecc6bff7` | `core/observability`: RUM e Browser Logs, telas pelo caminho template da rota e `usr.id` pelo `azureId`, com specs |
| `7098d2ad`, `c330f15c` | `ErrorHandler` global e interceptor: erro de JavaScript e falha de chamada ao BFF (método, rota sem query, status, `http.request_id` e duração, sem corpo), com specs |
| `07a964bc` | CSP: `connect-src` com o intake do Datadog |
| `fb102e67` | nginx: log de acesso em JSON e `X-Request-ID` repassado ao BFF |
| `b01092b6` | `error_log` em `warn` (um `sed` no `nginx.conf` da imagem, que quebra o build se o formato mudar) |
| `e40f31a7` | `.ai/rules/observability.md`: o que vai e o que nunca vai ao Datadog; o evento de negócio é do BFF |
| `98ba9983` | o SDK do Datadog é baixado sob demanda, fora do bundle inicial |
| `25989e89` | 404 de arquivo estático só no log de acesso (`log_not_found off`) |
| `cf907c2c` | a `.ai` deixa de dizer que a TS-5386 não está na base (feito pelo main) |

**Privacidade:**
- 100% das sessões, `mask-user-input` e sem Session Replay;
- nenhum corpo, e-mail nem token: o `beforeSend` tira a query das URLs,
  inclusive das que aparecem dentro do texto do erro, e mascara e-mail no
  caminho e nas causas;
- o `usr.id` é o `azureId`, sem nome e sem e-mail (D38).

**Bundle:** com o SDK no bundle inicial, ele ia a 630 kB e estourava o
orçamento de 500 kB. Agora o SDK vem num chunk próprio, só quando o `env.js`
liga o Datadog, e as chamadas anteriores ficam numa fila. O bundle inicial
ficou em 429 kB (121 kB na rede). Com o Datadog ligado, a página baixa uns
170 kB a mais (cerca de 55 kB na rede).

**Variáveis de ambiente novas do front** (nenhuma é segredo: o client token
do RUM só envia dados, e a chave de API não vai ao navegador):

| Variável | Padrão |
|---|---|
| `DD_RUM_APPLICATION_ID` | vazio (Datadog desligado) |
| `DD_RUM_CLIENT_TOKEN` | vazio (Datadog desligado) |
| `DD_SITE` | `datadoghq.com` |
| `DD_SERVICE` | `apl-credit-whitelabel-front` |
| `DD_ENV` | o valor do `ENVIRONMENT` |
| `DD_VERSION` | vazio (a tag da imagem) |
| `DD_RUM_SESSION_SAMPLE_RATE` | `100` |
| `DD_RUM_TRACE_SAMPLE_RATE` | `100` |

**Validação:**
- `validate-batch.sh` ok: os 12 commits do agente compilam sozinhos;
- `validate.sh` ok: audit 0, 1.968 testes passando;
- `check-patterns` limpo;
- imagem de produção com um BFF falso:
  - a CSP traz o intake;
  - o `X-Request-ID` chega ao BFF: gerado pelo nginx, mantido quando é
    válido e trocado quando não é, e volta na resposta, até no 504;
  - o log de acesso sai em JSON, sem a query;
  - nenhum `[notice]`;
- portal num Chromium com o Datadog ligado e os envios segurados no
  navegador:
  - telas com o nome da rota;
  - `usr.id` com o `azureId`;
  - a falha de chamada traz o `request_id`;
  - nenhum e-mail nem corpo;
  - nenhuma violação da CSP.

**Para a 24 e o Datadog:**
- criar a aplicação de RUM do tipo Browser, sem Session Replay. Ela fornece
  o application id e o client token;
- no argocd: `DD_RUM_APPLICATION_ID`, `DD_RUM_CLIENT_TOKEN` e `DD_VERSION`, e
  a anotação de logs `source:nginx` no contêiner. Se o admission controller
  do Datadog injetar `DD_ENV`, `DD_SERVICE` e `DD_VERSION`, o front usa esses
  valores; conferir o `DD_SERVICE` dos deploys das outras marcas;
- facets: `@http.request_id`, `@evt.name`, `@http.url_details.path` e
  `@upstream.duration`;
- monitores:
  - erros de JavaScript por versão;
  - `@evt.name:http.bff_request_failed status:error`;
  - LCP p75 por tela.

**Observações:**
- a primeira checagem de rota sai antes de o SDK chegar e vai sem cabeçalho
  de trace;
- eventos anteriores ao perfil ficam sem `usr.id`;
- a linha de erro nativa do nginx (502 e 504) traz a requisição com a query;
- se um dia ligarem o Session Replay, a CSP vai precisar de
  `worker-src blob:`.
