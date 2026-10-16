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

