# Reenvio para a Genius em produção — 15/10/2026

Logs e APM do Datadog sobre envio, reenvio e retorno de lotes da Genius. Base
da [tarefa 08](../tarefas/08-genius-reenvio-e-logs.md).

- Ambiente: `env:production`, serviços `platform-cessao` (API) e
  `platform-cessao-worker` (Celery e consumer do RabbitMQ).
- Janela: 30 dias até 15/10/2026, 21h UTC. A retenção dos logs começa em
  16/09; o que veio antes não aparece.
- As mensagens abaixo usam o nome análogo. Nas consultas do Datadog, troque
  por o nome real da administradora (minúsculo ou capitalizado, como no
  código).
- Fundos identificados por letra; os CNPJs ficam fora do repo.

## Resumo

| # | Problema | Número | Status |
|---|---|---|---|
| 1 | Retorno reprocessado em laço porque o consumer perde a conexão com o RabbitMQ antes do ack | 1 lote processado **4.160 vezes** em 7 dias; outros 4 lotes grandes, 7 a 42 vezes | [C] |
| 2 | Mesmo nome de arquivo usado por lotes diferentes (A2 e variações) | **31 nomes, 66 lotes** de liquidação; 3 nomes na cessão | [C] |
| 3 | Reenvio do mesmo lote reprocessa o retorno (A1) | **38 lotes** enviados mais de uma vez; **26** com mais de um retorno processado | [C] |
| 4 | Recusas que não casam com pagamento do lote | **18.281 avisos** | [C] |
| 5 | Lotes enviados sem retorno processado | **426 de 1.425** (411 de um envio em massa em 23/09); **11 de 11** com nome sem `_B_` | [C] número; [H] causa |
| 6 | `size mismatch` vem de envios simultâneos do mesmo nome | 5 lotes mandando o mesmo arquivo em 3 s | [C] |
| 7 | Falhas de envio sem diagnóstico | 65 avisos em 15 arquivos, todos com mensagem vazia | [C] |
| 8 | Reenvio por fora da tela | `/liquidacao/liquidar`: 223 chamadas (167 de scripts); `/cessao/cessionar`: 18 pelo navegador | [C] |
| 9 | Lambda sem logs no Datadog | nenhum log da Lambda encontrado | [C] |

## 1. Retorno reprocessado em laço

- Lote `4074b31d…` (14.522 linhas aprovadas): retorno processado **4.160
  vezes**, a cada ~2 min, de 24/09 16h19 a 01/10 21h20 UTC.
- No mesmo intervalo, exato: ~1.200 erros `Consumer Erro: Stream connection
  lost: ConnectionResetError(104, 'Connection reset by peer')`, mais
  `No activity or too many missed heartbeats in the last 60 seconds`.
- Outros lotes grandes repetem o padrão: 42 vezes (5.667 linhas), 15 vezes
  (5.961), 7 vezes (7.101 recusas), 2 vezes (7.072).
- Mecanismo [C] no código: o consumer do RabbitMQ roda em segundo plano em
  **cada pod do worker Celery** (`entrypoint.sh:16`; o `busconsumer` é o
  consumer de SQS). Ele usa `pika.BlockingConnection` (pika 1.1.0) com os
  parâmetros da URI `RABBITMQ_CESSAO_AMQP`, sem heartbeat próprio no código
  (`cessao/consumer/messaging/consumer.py:9-12`). O intervalo efetivo é de
  **60 s**, como mostra o erro `too many missed heartbeats in the last 60
  seconds`. O callback processa o arquivo inteiro antes do ack
  (`consumer/__init__.py:54-65`), e durante o callback a conexão não troca
  heartbeat. Num retorno grande, a conexão cai, a mensagem volta para a fila e
  outro pod reprocessa.
- O retorno do laço foi processado por **215 pods diferentes** (14 hosts).
- Duração do callback `listener_liquidacao_retorno_adm` (APM, de 02/10 a
  15/10, fora do laço): 342 execuções, p50 de 0,3 s, p90 de 2,6 s, p99 de 16
  min, máximo de 40 min. **13 execuções (3,8%) passaram de 60 s.**
- Efeito: no lote com 7.101 recusas (`4e48dd7c…`), as 7 passadas aplicaram
  **49.616** recusas no total, cerca de 7.088 por passada. No mesmo período
  houve 4 erros `Consumer liquidacao_retorno_adm error 'NoneType' object has
  no attribute 'parcela'`. **[H]** Passadas concorrentes do mesmo retorno: cada
  uma reverte a parcela (`reverter_valores_parcela`) e apaga o pagamento.
  Validar no banco se `contrato_parcela.valor_aberto` desses lotes foi
  revertido mais de uma vez.
- Correção decidida em 15/10: D17 (retorno direto no worker do Celery).

## 2. Mesmo nome de arquivo em lotes diferentes

Liquidação, 30 dias: 1.464 envios registrados, 1.425 lotes, 1.398 nomes
distintos. **31 nomes foram usados por mais de um lote (66 lotes).**
Classificação de cada colisão pelo histórico de envio do lote:

| Mecanismo | Nomes | Exemplo |
|---|---|---|
| **A2 como mapeado:** reenvio de lote de outro dia sai com a data de hoje e o `NNN` antigo, e colide com lote novo do dia | 7 | 08/10: 4 lotes de 06–07/10 reenviados às 19h11 com `…_20261008_B_002/004/009/015`, iguais aos de lotes criados às 17h; 13/10: 2 lotes de 09/10 reenviados às 18h34 |
| **Dois lotes novos no mesmo dia com o mesmo número** | 21 | fundo A, 23/09: 501 lotes às 14h BRT (`B_001` a `B_501`) e 17 lotes novos às 17h com `B_001` a `B_017` de novo |
| **Repasse: um arquivo do parceiro para vários lotes** (B13) | 3 | fundo B, 09/10: o mesmo arquivo, datado de 08/10, enviado por 5 lotes entre 17h00m52 e 17h00m55 |

- O segundo mecanismo não sai do código do contador (maior número do fundo
  no dia + 1). **[H]** Dois cadastros de fundo com o mesmo CNPJ (o contador é
  por `fundo_id`; o nome, por CNPJ) ou reserva apagada. Validar em
  `liquidacao_lote_arquivo` e `fundo`.
- Cessão: 242 envios, 237 lotes; 3 nomes em mais de um lote; 5 nomes
  reenviados pelo mesmo lote.

## 3. Reenvio do mesmo lote reprocessa o retorno (A1)

| Envios do lote | Retornos processados | Lotes |
|---|---|---|
| 1 | 1 | 954 |
| 1 | 0 | 426 |
| mais de 1 | mais de 1 | 26 |
| mais de 1 | 1 | 7 |
| 1 | mais de 1 | 7 |
| mais de 1 | 0 | 5 |

- 08/10: 21 lotes do fundo A seguiram a mesma sequência. Envio às 18h50,
  retorno às 19h00, reenvio às 19h11 com o mesmo nome e retorno de novo às
  19h15. Os dois retornos têm os mesmos números (0 aprovadas, 1 ou 2
  recusadas).
- **Não dá para saber se o retorno das 19h15 foi o antigo ou o novo.** A
  Genius pode responder em poucos minutos: nos 961 lotes com um único envio,
  o retorno foi processado em menos de 5 min em 44 casos (mínimo de 1 min),
  em 5–10 min em 138, em 10–15 min em 425, em 15–30 min em 300 e acima de
  30 min em 54. O tempo inclui a espera pela rodada da Lambda, a cada 15
  min. Isso é o A1.2: o reenvio reabre a busca, e nada distingue o `.RET`
  antigo do novo (a Lambda não loga a data do arquivo, e o S3 grava os dois na
  mesma chave).
- Para verificar um caso: comparar as versões do objeto no S3 (se o bucket
  tiver versionamento), ou o header do `.RET` com o do `.REM` enviado (G7).
- 05/10: reenvio por `/liquidacao/liquidar` às 15h14; retornos processados às
  15h15 e 15h30. Mesma ressalva.
- Correção decidida: D15 (filtro por data na Lambda, I2), com um só item
  `pendente` por lote no reenvio. Não cobre o reenvio antes do primeiro
  retorno (A1.3) nem a colisão com outro lote (A2).
- Lote `50c142cd…`: enviado 2 vezes em 08/10 (19h04 e 19h12) e reenviado em
  13/10 com o mesmo `NNN` e data nova. Dois retornos, 1.516 recusas cada,
  **nenhuma** casou com pagamento do lote (3.032 avisos).

## 4. Recusas sem pagamento correspondente

`Liquidação rejeitada sem pagamento correspondente no lote`: **18.281
avisos** em 30 dias. Concentrados nos casos acima: 8.316 no lote do laço,
4.760 em outro reprocessado 42 vezes, 3.032 no lote reenviado da seção 3,
307 num lote reenviado em 13/10 que colidiu com outro, e 65 a 96 em cada um
dos lotes do repasse de 09/10. É o sinal de retorno aplicado ao lote
errado ou reaplicado.

## 5. Lotes sem retorno processado

Dos 1.425 lotes de liquidação enviados na janela, 426 não tiveram retorno
processado.

- 411 são do envio em massa de 23/09 (fundo A, 501 lotes em uma hora). Nos
  outros dias, 0 a 6 por dia.
- **11 lotes de liquidação foram enviados com nome sem `_B_`** (arquivos
  `_R_` de renegociação, no repasse): **todos** sem retorno. A Lambda bloqueia
  item da liquidação sem a marca `_B_` (`genius_sftp_listener.py:717-760`).
- **[H]** Para o resto: a Genius não processou, a Lambda não achou ou estourou
  o tempo. Sem logs da Lambda no Datadog (item 9), não dá para separar.

## 6. `size mismatch` vem de envios simultâneos

O único `size mismatch in put! 0 != 49660` da janela foi em 09/10 17h00m53,
no arquivo que 5 lotes enviaram entre 17h00m52 e 17h00m55. Um `putfo`
trunca o arquivo enquanto outro confere o tamanho. Muda a leitura do B3 da
tarefa: a causa provável não é o servidor recusar sobrescrever.

## 7. Falhas de envio sem diagnóstico

`Falha ao enviar arquivo para o SFTP da genius`: 65 avisos em 15 arquivos
(23/09 a 14/10), todos com `error_message` vazio, exceto o `size mismatch`. 31
chegaram à segunda tentativa; a terceira falha sobe sem log (C2). Com a
mensagem vazia, não dá para saber se é permissão, arquivo existente ou
conexão.

## 8. Chamadas às rotas de reenvio (APM, 30 dias)

| Rota | Chamador (`http.useragent`) | 200 | 400 |
|---|---|---|---|
| `POST /liquidacao/liquidar` | `python-requests` (duas versões) | 167 | 19 |
| `POST /liquidacao/liquidar` | navegador | 37 | — |
| `POST /liquidacao/reenviar` | BFF (`python-httpx`) | 31 | — |
| `POST /liquidacao/reenviar` | navegador | — | 3 |
| `POST /cessao/cessionar` | navegador | 18 | — |

- A rota `/liquidar` vale para todas as administradoras; o número não é só
  da Genius.
- Erro de 05/10 15h14 num reenvio por `/liquidar`: `O nome do arquivo de
  liquidação não está no padrão correto`, com um arquivo de renegociação do
  parceiro (`…_RENEG_002.REM.ret`).
- **[H]** Quem chama `/liquidar` por `python-requests`: script de operação ou
  outro serviço. Conferir o IP de origem nos spans.

## 9. Lambda sem logs no Datadog

Nenhum log com os padrões da Lambda (`not on sftp yet`, `blocked:`,
`done |`) nos últimos 3 dias. Os logs dela ficam só no CloudWatch, o que
esconde itens bloqueados, falhas e itens pulados por tempo.

## Consultas para repetir

Logs (troque o nome análogo pelo real nas mensagens):

- Envios registrados: `env:production service:platform-cessao* "Arquivo de
  liquidação registrado em cache Redis"`, colunas `@liquidacao_lote_id`,
  `@nome_arquivo`. Cessão: `"Arquivo registrado em cache Redis"`, colunas
  `@cessao_id`, `@nome_arquivo`.
- Retornos processados: `"Retorno de liquidação Genius processado"`, colunas
  `@lote_uuid`, `@aprovadas`, `@rejeitadas`, `@processos_rejeitados`.
- Recusas sem pagamento: `"Liquidação rejeitada sem pagamento correspondente
  no lote"`, coluna `@lote_uuid`.
- Conexão do consumer: `status:error ("Consumer Erro" OR "StreamLost" OR
  "heartbeat")`.
- Falhas de envio: `"Falha ao enviar arquivo para o SFTP da genius"`, colunas
  `@error_message`, `@caminho_completo`, `@tentativa`.

SQL usado (em `analyze_datadog_logs`):

```sql
-- nomes usados por mais de um lote
SELECT "@nome_arquivo", COUNT(*) AS envios,
       COUNT(DISTINCT "@liquidacao_lote_id") AS lotes
  FROM logs GROUP BY "@nome_arquivo"
 HAVING COUNT(DISTINCT "@liquidacao_lote_id") > 1;

-- lotes com retorno processado mais de uma vez e o intervalo médio
SELECT "@lote_uuid", COUNT(*) AS processamentos,
       MIN(timestamp), MAX(timestamp),
       ROUND((EXTRACT(EPOCH FROM MAX(timestamp))
            - EXTRACT(EPOCH FROM MIN(timestamp))) / 60 / (COUNT(*) - 1)) AS min_entre
  FROM logs GROUP BY "@lote_uuid" HAVING COUNT(*) > 1;
```

APM: `env:production service:platform-cessao operation_name:flask.request
resource_name:("POST /liquidacao/liquidar" OR "POST /liquidacao/reenviar" OR
"POST /cessao/cessionar")`, agrupado por `resource_name`,
`@http.status_code` e `@http.useragent`.
